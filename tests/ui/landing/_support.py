from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page

# What the landing page (nginx/index.html) is expected to contain. It is the
# front door to every service in the stack.


@dataclass(frozen=True)
class ServiceRow:
    """One entry in the landing page's service list."""

    title: str
    href: str
    # The route the page pings to decide if the service is up. Not always the
    # row's own link -- Marva links to its login page but pings the app.
    probe: str


# In the order the page lists them.
SERVICE_ROWS: tuple[ServiceRow, ...] = (
    ServiceRow("Search", "/api/search", "/api/"),
    ServiceRow("Sinopia", "/sinopia/", "/sinopia/"),
    ServiceRow("Marva", "/marva-login/", "/marva/"),
    ServiceRow("Graph Toolbox", "/toolbox/", "/toolbox/"),
    ServiceRow("API Endpoints", "/api/docs", "/api/"),
    ServiceRow("Keycloak", "/keycloak/", "/keycloak/"),
    ServiceRow("Workflows", "/workflows/", "/workflows/"),
)

FOOTER_LINKS: tuple[tuple[str, str], ...] = (
    ("OpenAPI JSON", "/api/openapi.json"),
    ("Workflows Health", "/workflows/api/v2/monitor/health"),
)

# Files the page pulls in. A missing one still leaves the page returning 200.
PAGE_ASSETS = ("/assets/styles.css", "/assets/health.js", "/assets/bluecore-small.png")

# What the badge says before the check finishes.
CHECKING_LABEL = "Checking…"

# Set by checkGateway() once both probes settle.
GATEWAY_STATES = {
    "status-ok": "Gateway reachable (API OK)",
    "status-warn": None,  # one of two wordings, depending on which probe failed
    "status-down": "Gateway unreachable",
}

MOBILE_VIEWPORT = {"width": 420, "height": 860}


def open_landing(page: Page, base_url: str, timeout: int) -> None:
    page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=timeout)


def row_locator(page: Page, title: str):
    """The service row carrying a given title."""
    return page.locator("a.row").filter(has=page.locator("span.title", has_text=title))


def collect_responses(page: Page) -> list[tuple[str, int]]:
    seen: list[tuple[str, int]] = []
    page.on("response", lambda response: seen.append((response.url, response.status)))
    return seen


def probe_is_reachable(page: Page, probe: str, base_url: str) -> bool:
    """Work out for ourselves whether a service is up, the same way the page
    does: only a 502/503/504 or a dead connection counts as down."""
    try:
        response = page.request.get(f"{base_url}{probe}", timeout=20_000)
    except Exception:  # noqa: BLE001 - a failed request is exactly "down"
        return False
    return response.status not in (502, 503, 504)
