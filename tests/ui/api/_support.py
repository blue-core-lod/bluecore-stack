from __future__ import annotations

from playwright.sync_api import Page

# Helpers used by more than one of the API view tests. Anything only one file
# needs lives in that file.

def open_search(page: Page, api_base_url: str, timeout: int, query: str = "", **params) -> None:
    """Open the HTML search view.

    NOTE the path has NO trailing slash: `GET /search/` returns JSON and
    `GET /search` returns HTML. They are separate routes, and the HTML one is
    include_in_schema=False, so the OpenAPI test cannot see it.
    """
    parts = [f"q={query}"] + [f"{key}={value}" for key, value in params.items()]
    page.goto(
        f"{api_base_url}/search?{'&'.join(parts)}",
        wait_until="domcontentloaded",
        timeout=timeout,
    )


def open_resource(
    page: Page, api_base_url: str, resource_type: str, uuid: str, timeout: int
) -> None:
    page.goto(
        f"{api_base_url}/{resource_type}/{uuid}",
        wait_until="domcontentloaded",
        timeout=timeout,
    )


def field_labels(page: Page) -> list[str]:
    """Data-field headings, in the order the page lays them out.

    Excludes .bc-formats: alt_formats reuses the bc-field class for the trailing
    "Alternative Formats" / "Blue Core Editors" block, which is page furniture
    rather than record data.
    """
    return [
        text.strip()
        for text in page.locator("div.bc-field:not(.bc-formats) > h2").all_inner_texts()
    ]


def field_values(page: Page, label: str) -> list[str]:
    """Visible values under one field heading, however that field renders them."""
    field = page.locator("div.bc-field:not(.bc-formats)").filter(
        has=page.locator("h2", has_text=label)
    )
    if field.count() == 0:
        return []
    values = field.first.locator("li.bc-list-value, p.bc-value")
    return [text.strip() for text in values.all_inner_texts()]


def result_count(page: Page) -> int:
    """The 'N results for ...' line as a number."""
    return int(page.locator("p.bc-result-num").inner_text().strip().split()[0])


def result_hrefs(page: Page) -> list[str]:
    links = page.locator("ul.bc-results li a")
    return [
        href
        for href in (links.nth(i).get_attribute("href") for i in range(links.count()))
        if href
    ]
