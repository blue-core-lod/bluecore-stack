from __future__ import annotations

import time

from playwright.sync_api import APIRequestContext
from playwright.sync_api import APIResponse
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.integration.support.logging import color


# ========================================================================
# Convert timeout seconds into Playwright timeout milliseconds.
# ------------------------------------------------------------------------
def timeout_ms(timeout_seconds: float | int) -> int:
    return max(1, int(float(timeout_seconds) * 1000))


# ========================================================================
# Assert API response status against expected int or set of statuses.
# ------------------------------------------------------------------------
def assert_status(response: APIResponse, expected: int | set[int]) -> None:
    if isinstance(expected, set):
        assert response.status in expected, response.text()
        return
    assert response.status == expected, response.text()


# ========================================================================
# Send API request with normalized options used across test modules.
# ------------------------------------------------------------------------
def send_request(
    request_context: APIRequestContext,
    method: str,
    url: str,
    request_timeout: float,
    **kwargs,
) -> APIResponse:
    request_options: dict = {
        "method": method,
        "timeout": timeout_ms(request_timeout),
        "fail_on_status_code": False,
    }

    if "headers" in kwargs:
        request_options["headers"] = kwargs["headers"]
    if "params" in kwargs:
        request_options["params"] = kwargs["params"]
    if "json" in kwargs:
        request_options["data"] = kwargs["json"]
    if "data" in kwargs:
        request_options["data"] = kwargs["data"]
    if "files" in kwargs:
        files = kwargs["files"]
        multipart_payload = {}
        for field_name, file_tuple in files.items():
            filename, file_bytes, mime_type = file_tuple
            multipart_payload[field_name] = {
                "name": filename,
                "mimeType": mime_type,
                "buffer": file_bytes,
            }
        request_options["multipart"] = multipart_payload

    return request_context.fetch(url, **request_options)


# ========================================================================
# Perform GET requests with shared timeout/header/query behavior.
# ------------------------------------------------------------------------
def get(
    request_context: APIRequestContext,
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    params: dict | None = None,
    max_redirects: int | None = None,
    fail_on_status_code: bool | None = None,
) -> APIResponse:
    request_options: dict = {
        "headers": headers,
        "params": params,
        "timeout": timeout_ms(timeout_seconds),
    }
    if max_redirects is not None:
        request_options["max_redirects"] = max_redirects
    if fail_on_status_code is not None:
        request_options["fail_on_status_code"] = fail_on_status_code
    return request_context.get(url, **request_options)


# ========================================================================
# Perform POST requests with shared timeout and payload handling.
# ------------------------------------------------------------------------
def post(
    request_context: APIRequestContext,
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    json_payload: dict | None = None,
    form_payload: dict | None = None,
    data_payload: str | bytes | None = None,
) -> APIResponse:
    return request_context.fetch(
        url,
        method="POST",
        headers=headers,
        data=json_payload if json_payload is not None else data_payload,
        form=form_payload,
        timeout=timeout_ms(timeout_seconds),
        fail_on_status_code=False,
    )


# ========================================================================
# Retry GET requests while stack dependencies are still warming up.
# ------------------------------------------------------------------------
def get_with_retry(
    *,
    request_context: APIRequestContext,
    url: str,
    request_timeout: float,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 2.0,
) -> APIResponse:
    deadline = time.time() + timeout_seconds
    last_response: APIResponse | None = None
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = get(
                request_context,
                url,
                timeout_seconds=request_timeout,
            )
            last_response = response
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
            time.sleep(poll_interval_seconds)
            continue

        if response.status == 200:
            return response

        if response.status in {429, 500, 502, 503, 504}:
            time.sleep(poll_interval_seconds)
            continue

        return response

    if last_response is not None:
        return last_response
    raise AssertionError(f"Timed out waiting for GET {url}. Last error: {last_error!r}")


# ========================================================================
# Retry POST calls on transient 5xx/timeouts and log each attempt.
# ------------------------------------------------------------------------
def post_with_retry(
    *,
    request_context: APIRequestContext,
    url: str,
    json_payload: dict | None,
    headers: dict[str, str] | None,
    request_timeout: float,
    max_attempts: int = 4,
    retry_delay_seconds: float = 2.0,
) -> APIResponse:
    last_response: APIResponse | None = None
    last_error: Exception | None = None
    retry_statuses = {500, 502, 503, 504}

    for attempt in range(1, max_attempts + 1):
        print(color(f"POST attempt {attempt}/{max_attempts}: {url}", "2;37"))
        try:
            response = post(
                request_context,
                url,
                json_payload=json_payload,
                headers=headers,
                timeout_seconds=request_timeout,
            )
            last_response = response
            status_color = "1;32" if response.status not in retry_statuses else "1;31"
            print(color(f"Attempt {attempt}/{max_attempts} status code: {response.status}", status_color))
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
            print(
                color(
                    f"Attempt {attempt}/{max_attempts} transport error: {type(exc).__name__}: {exc}",
                    "1;31",
                )
            )
            if attempt < max_attempts:
                print(color(f"Retrying POST in {retry_delay_seconds:.1f}s after transport error...", "2;37"))
                time.sleep(retry_delay_seconds)
                continue
            raise AssertionError(
                f"POST {url} failed after {max_attempts} attempts. Last error: {last_error!r}"
            ) from exc

        if response.status not in retry_statuses:
            print(
                color(
                    f"PASS attempt {attempt}/{max_attempts}: status {response.status} is non-transient.",
                    "1;32",
                )
            )
            return response

        print(
            color(
                (
                    f"Transient status on attempt {attempt}/{max_attempts}: "
                    f"{response.status}. Retry statuses: {sorted(retry_statuses)}"
                ),
                "1;31",
            )
        )
        if attempt < max_attempts:
            print(color(f"Retrying POST in {retry_delay_seconds:.1f}s after transient status...", "2;37"))
            time.sleep(retry_delay_seconds)

    assert last_response is not None
    print(color(f"Exhausted retries for POST {url}. Returning last response.", "1;31"))
    return last_response

