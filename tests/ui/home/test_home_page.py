from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.integration.support.logging import log_expected_actual, log_header
from tests.ui._support import (
    KEYCLOAK_AUTH_PATH,
    bluecore_url,
    full_stack_enabled,
    keycloak_password,
    keycloak_username,
)

# Browser tests for the homepage (nginx/index.html).
pytestmark = pytest.mark.skipif(
    not full_stack_enabled(),
    reason="Homepage UI tests require the full stack (Nginx + apps + Keycloak)",
)

APPS = ["Search", "Marva", "Sinopia", "Graph Toolbox", "API", "Keycloak", "Workflows"]
PARTNERS = [
    "Cornell University Library",
    "Stanford University Libraries",
    "Library of Congress",
    "University of California Davis Library",
    "University of Pennsylvania Library",
]


def home_url() -> str:
    return f"{bluecore_url()}/"


def _fill_login(page: Page, password: str, app: str = "Sinopia") -> None:
    page.locator("#home-login-username").fill(keycloak_username())
    page.locator("#home-login-password").fill(password)
    page.locator("#home-login-app").select_option(label=app)
    page.get_by_role("button", name="Login", exact=True).click()


def _record_keycloak_pages(page: Page) -> list[str]:
    """Keycloak login pages the browser visits."""
    seen: list[str] = []
    page.on(
        "framenavigated",
        lambda frame: (
            seen.append(frame.url)
            if frame == page.main_frame and KEYCLOAK_AUTH_PATH in frame.url
            else None
        ),
    )
    return seen


# ========================================================================
# Header: logo plus Applications / Community / About, which scroll to each section.
# ------------------------------------------------------------------------
def test_header_has_logo_and_section_links(page: Page, ui_timeout_ms: int):
    log_header("Homepage header")
    page.goto(home_url(), timeout=ui_timeout_ms)

    header = page.locator("header.bluecore-header")
    expect(header).to_be_visible()
    expect(header.locator(".bluecore-header-app-name")).to_have_count(0)
    expect(header.get_by_role("link")).to_have_text(
        ["", "Applications", "Community", "About"]
    )
    expect(header.get_by_role("button")).to_have_count(0)
    for name, section in (
        ("Applications", "applications"),
        ("Community", "community"),
        ("About", "about"),
    ):
        link = header.get_by_role("link", name=name, exact=True)
        expect(link).to_have_attribute("href", f"/#{section}")
        link.click()
        page.wait_for_url(f"{home_url()}#{section}", timeout=ui_timeout_ms)
        expect(page.locator(f"#{section}-heading")).to_be_in_viewport()
        # heading just below the header, previous section not showing
        page.wait_for_function(
            """(id) => {
                const header = document.querySelector('header.bluecore-header');
                const headerBottom = header.getBoundingClientRect().bottom;
                const top = document.getElementById(id).getBoundingClientRect().top;
                const heading = document.getElementById(id + '-heading');
                const atBottom = window.innerHeight + window.scrollY
                    >= document.documentElement.scrollHeight - 1;
                return (top <= headerBottom + 1 || atBottom)
                    && heading.getBoundingClientRect().top >= headerBottom;
            }""",
            arg=section,
            timeout=ui_timeout_ms,
        )
    expect(page.locator("footer.bluecore-footer")).to_be_visible()


# ========================================================================
# Apps keep their own header and footer (only the homepage changed).
# ------------------------------------------------------------------------
def test_apps_keep_their_header_and_footer(page: Page, ui_timeout_ms: int):
    log_header("App header and footer on the Marva login page")
    page.goto(f"{bluecore_url()}/marva-login/", timeout=ui_timeout_ms)
    header = page.locator("header.bluecore-header")
    expect(header).not_to_have_class(re.compile("bluecore-header-home"))
    expect(header.locator(".bluecore-header-nav-link")).to_have_count(0)
    expect(header.get_by_role("link", name="Contact", exact=True)).to_be_visible()
    expect(header.get_by_role("button", name="Switch applications")).to_be_visible()

    footer = page.locator("footer.bluecore-footer")
    expect(footer).not_to_have_class(re.compile("bluecore-footer-home"))
    expect(footer.locator(".bluecore-footer-app-list a")).to_have_text(APPS)
    box = footer.bounding_box()
    assert box and box["height"] == 157


# ========================================================================
# The apps' header and footer fit smaller screens: nothing overlapping or off
# the side, the app menu, Logout and the footer's app list all still there.
# ------------------------------------------------------------------------
@pytest.mark.parametrize("slim", [False, True], ids=["full", "slim"])
@pytest.mark.parametrize("width", [1100, 900, 600, 390, 320])
def test_app_header_and_footer_fit_smaller_screens(
    page: Page, ui_timeout_ms: int, width: int, slim: bool
):
    log_header(f"App header and footer at {width}px ({'slim' if slim else 'full'})")
    page.set_viewport_size({"width": width, "height": 800})
    page.goto(f"{bluecore_url()}/marva-login/", timeout=ui_timeout_ms)
    page.evaluate(
        """slim => {
            const h = document.querySelector('bluecore-header');
            h.setAttribute('app-name', 'DCTAP DANCER');
            h.setAttribute('username', 'developer');
            h.setAttribute('logout', '');
            document.querySelectorAll('bluecore-header, bluecore-footer')
                .forEach(e => e.toggleAttribute('slim', slim));
        }""",
        slim,
    )
    header = page.locator("header.bluecore-header")
    expect(header.get_by_role("button", name="Switch applications")).to_be_visible()
    expect(header.get_by_role("button", name="Logout")).to_be_visible()

    result = page.evaluate(
        """() => {
            const header = document.querySelector('header.bluecore-header');
            const brand = header.querySelector('.bluecore-header-brand');
            const links = header.querySelector('.bluecore-header-links');
            const footer = document.querySelector('footer.bluecore-footer');
            return {
                scrollWidth: document.documentElement.scrollWidth,
                gap: links.getBoundingClientRect().left - brand.getBoundingClientRect().right,
                header: header.getBoundingClientRect().height,
                footer: footer.getBoundingClientRect().height,
            };
        }"""
    )
    log_expected_actual("header and footer", "fit, same heights", result)
    assert result["scrollWidth"] <= width
    assert result["gap"] >= 0
    assert result["header"] == (23 if slim else 57)
    if slim:
        assert result["footer"] == 23
    else:
        # the footer grows on phones to fit its wrapping app list
        assert result["footer"] >= 157
        expect(page.locator(".bluecore-footer-app-list a")).to_have_text(APPS)
        for link in page.locator(".bluecore-footer-app-list a").all():
            expect(link).to_be_visible()


# ========================================================================
# Header options: custom links, Contact, and the app menu.
# ------------------------------------------------------------------------
def test_header_options(page: Page, ui_timeout_ms: int):
    log_header("Header links, contact and app-switcher attributes")
    page.goto(home_url(), timeout=ui_timeout_ms)
    element = page.locator("bluecore-header")
    header = page.locator("header.bluecore-header")

    element.evaluate(
        """h => {
            h.setAttribute('links', JSON.stringify([{label: 'Help', href: '/help/'}]));
            h.setAttribute('contact', '');
            h.setAttribute('app-switcher', '');
            h.setAttribute('current-app', 'marva');
        }"""
    )
    expect(header.locator(".bluecore-header-nav-link")).to_have_text(["Help"])
    expect(header.get_by_role("link", name="Contact", exact=True)).to_have_attribute(
        "href", "mailto:contact@bluecore.info"
    )
    menu = page.locator("#bluecore-app-menu")
    expect(menu).to_be_hidden()
    header.get_by_role("button", name="Switch applications").click()
    expect(menu.get_by_role("link")).to_have_text([a for a in APPS if a != "Marva"])
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()

    element.evaluate("h => h.setAttribute('links', '[]')")
    expect(header.locator(".bluecore-header-nav-link")).to_have_count(0)


# ========================================================================
# The logo links to the homepage.
# ------------------------------------------------------------------------
def test_logo_links_home(page: Page, ui_timeout_ms: int):
    log_header("Blue Core logo links home")
    page.goto(f"{bluecore_url()}/marva-login/", timeout=ui_timeout_ms)
    for element in ("bluecore-header", "bluecore-footer"):
        expect(
            page.locator(element).get_by_role("link", name="Blue Core home")
        ).to_have_attribute("href", "/")

    page.locator("bluecore-header").get_by_role("link", name="Blue Core home").click()
    page.wait_for_url(home_url(), timeout=ui_timeout_ms)
    log_expected_actual("URL", home_url(), page.url)
    assert page.url == home_url()


# ========================================================================
# Footer matches Figma; outside links open in a new tab.
# ------------------------------------------------------------------------
def test_footer_matches_the_design(page: Page, ui_timeout_ms: int):
    log_header("Footer sections")
    page.goto(home_url(), timeout=ui_timeout_ms)
    footer = page.locator("footer.bluecore-footer")

    expect(footer.get_by_role("link", name="Contact us")).to_have_attribute(
        "href", "mailto:contact@bluecore.info"
    )
    expect(footer.locator(".bluecore-footer-heading")).to_have_text(
        ["Partners", "Community"]
    )
    partners = footer.get_by_role("navigation", name="Partners").get_by_role("link")
    expect(partners).to_have_text(PARTNERS)
    expect(partners.first).to_have_attribute("target", "_blank")
    community = footer.get_by_role("navigation", name="Community").get_by_role("link")
    expect(community).to_have_text(["Publications", "Presentations", "Events"])

    box = footer.bounding_box()
    log_expected_actual("footer height", 221, box and box["height"])
    assert box and box["height"] == 221


# ========================================================================
# Footer columns can be swapped; bad JSON falls back to the defaults.
# ------------------------------------------------------------------------
def test_home_footer_sections(page: Page, ui_timeout_ms: int):
    log_header("Home footer sections attribute")
    page.goto(home_url(), timeout=ui_timeout_ms)
    element = page.locator("bluecore-footer")
    footer = page.locator("footer.bluecore-footer")

    element.evaluate(
        """f => f.setAttribute('sections', JSON.stringify([{heading: 'Help',
            links: [{label: 'User guide', href: '/docs/'}]}]))"""
    )
    expect(footer.locator(".bluecore-footer-heading")).to_have_text(["Help"])
    expect(footer.get_by_role("link", name="User guide")).to_have_attribute(
        "href", "/docs/"
    )

    element.evaluate("f => f.setAttribute('sections', '{')")
    expect(footer.locator(".bluecore-footer-heading")).to_have_text(
        ["Partners", "Community"]
    )


# ========================================================================
# Header sticks to the top; the footer is at the end of the page.
# ------------------------------------------------------------------------
def test_header_sticks_and_footer_is_at_the_end(page: Page, ui_timeout_ms: int):
    log_header("Sticky header, footer at the end of the page")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(home_url(), timeout=ui_timeout_ms)
    page.evaluate("window.scrollTo(0, 1500)")
    page.wait_for_function("window.scrollY >= 1500", timeout=ui_timeout_ms)

    header = page.locator("bluecore-header").bounding_box()
    log_expected_actual("header top", 0, header and header["y"])
    assert header and header["y"] == 0
    expect(page.locator("bluecore-footer")).not_to_be_in_viewport()

    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_function(
        "window.innerHeight + window.scrollY"
        " >= document.documentElement.scrollHeight - 1",
        timeout=ui_timeout_ms,
    )
    footer = page.locator("bluecore-footer").bounding_box()
    log_expected_actual("footer bottom", 900, footer and footer["y"] + footer["height"])
    assert footer and abs(footer["y"] + footer["height"] - 900) <= 1
    expect(page.locator("#about")).to_be_in_viewport()


# ========================================================================
# Application cards link to each app.
# ------------------------------------------------------------------------
def test_application_cards(page: Page, ui_timeout_ms: int):
    log_header("Homepage application cards")
    page.goto(home_url(), timeout=ui_timeout_ms)

    expected = {
        "#catalogers-heading": [
            ("Sinopia", "/sinopia/"),
            ("Marva", "/marva-login/"),
            ("Graph Toolbox", "/toolbox/"),
        ],
        "#developers-heading": [
            ("API", "/api/docs"),
            ("Keycloak", "/keycloak/"),
            ("Workflows", "/workflows/"),
        ],
    }
    for heading, apps in expected.items():
        group = page.locator(".home-app-group", has=page.locator(heading))
        cards = group.locator("a.home-app")
        expect(cards.locator(".home-app-name")).to_have_text([n for n, _ in apps])
        for index, (name, href) in enumerate(apps):
            log_expected_actual(
                f"{name} link", href, cards.nth(index).get_attribute("href")
            )
            expect(cards.nth(index)).to_have_attribute("href", href)


# ========================================================================
# Search opens the API's search page.
# ------------------------------------------------------------------------
def test_search_band(page: Page, ui_timeout_ms: int):
    log_header("Homepage search")
    page.goto(home_url(), timeout=ui_timeout_ms)

    search = page.get_by_role("search", name="Search Blue Core")
    expect(search).to_be_visible()
    search.get_by_label("Search Blue Core").fill("cats")
    search.get_by_role("button", name="Search").click()
    page.wait_for_url(f"{bluecore_url()}/api/search?q=cats", timeout=ui_timeout_ms)
    log_expected_actual("search page", f"{bluecore_url()}/api/search?q=cats", page.url)


# ========================================================================
# The login panel starts hidden so the login form doesn't flash.
# ------------------------------------------------------------------------
def test_login_panel_starts_hidden(page: Page, ui_timeout_ms: int):
    log_header("Homepage login panel starts hidden")
    html = page.request.get(home_url(), timeout=ui_timeout_ms).text()
    tag = re.search(r'<div[^>]*id="home-login"[^>]*>', html)
    assert tag, "no #home-login panel in the page"
    log_expected_actual("panel", 'aria-busy="true"', tag.group(0))
    assert 'aria-busy="true"' in tag.group(0)

    page.goto(home_url(), timeout=ui_timeout_ms)
    expect(page.locator("#home-login")).not_to_have_attribute(
        "aria-busy", "true", timeout=ui_timeout_ms
    )
    expect(page.locator("#home-login-form")).to_be_visible()


# ========================================================================
# A slow login check shows "Checking your login…", then the form.
# ------------------------------------------------------------------------
def test_slow_login_check_shows_loading(page: Page, ui_timeout_ms: int):
    log_header("Homepage login panel, slow login check")
    page.route(
        "**/protocol/openid-connect/auth?*",
        lambda route: (page.wait_for_timeout(1500), route.continue_()),
    )
    page.goto(home_url(), timeout=ui_timeout_ms)
    loading = page.get_by_role("status").filter(has_text="Checking your login")
    expect(loading).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator("#home-login-form")).not_to_be_visible()

    expect(loading).to_be_hidden(timeout=ui_timeout_ms)
    expect(page.locator("#home-login-form")).to_be_visible()


# ========================================================================
# Empty login fields are flagged.
# ------------------------------------------------------------------------
def test_empty_login_is_flagged(page: Page, ui_timeout_ms: int):
    log_header("Homepage login, empty form")
    page.goto(home_url(), timeout=ui_timeout_ms)
    page.get_by_role("button", name="Login", exact=True).click()

    expect(page.locator(".home-login-error")).to_have_text(
        "Enter your username and password."
    )
    expect(page.locator("#home-login-username")).to_have_attribute(
        "aria-invalid", "true"
    )
    assert page.url == home_url()


# ========================================================================
# The eye button shows and hides the password.
# ------------------------------------------------------------------------
def test_password_can_be_shown(page: Page, ui_timeout_ms: int):
    log_header("Homepage login, show password")
    page.goto(home_url(), timeout=ui_timeout_ms)
    password = page.locator("#home-login-password")
    expect(password).to_have_attribute("type", "password")
    page.get_by_role("button", name="Show password").click()
    expect(password).to_have_attribute("type", "text")
    page.get_by_role("button", name="Hide password").click()
    expect(password).to_have_attribute("type", "password")


# ========================================================================
# A wrong password shows an error on the homepage.
# ------------------------------------------------------------------------
def test_wrong_password_shows_error_inline(page: Page, ui_timeout_ms: int):
    log_header("Homepage login, wrong password")
    keycloak_pages = _record_keycloak_pages(page)
    page.goto(home_url(), timeout=ui_timeout_ms)
    _fill_login(page, "not-the-password")

    error = page.locator(".home-login-error")
    expect(error).to_be_visible(timeout=ui_timeout_ms)
    expect(error).to_contain_text("Invalid username or password")
    expect(page.locator("#home-login-password")).to_have_value("")
    log_expected_actual("URL", home_url(), page.url)
    assert page.url == home_url()
    assert keycloak_pages == []


# ========================================================================
# Logging in opens the chosen app without Keycloak's login page.
# ------------------------------------------------------------------------
def test_login_opens_sinopia_signed_in(page: Page, ui_timeout_ms: int):
    log_header("Homepage login to Sinopia")
    keycloak_pages = _record_keycloak_pages(page)
    page.goto(home_url(), timeout=ui_timeout_ms)
    _fill_login(page, keycloak_password(), app="Sinopia")

    page.wait_for_url(f"{bluecore_url()}/sinopia/**", timeout=ui_timeout_ms)
    expect(page.get_by_text("Logout", exact=True).first).to_be_visible(
        timeout=ui_timeout_ms
    )
    log_expected_actual("Keycloak login pages shown", [], keycloak_pages)
    assert keycloak_pages == []


def test_login_opens_marva_signed_in(page: Page, ui_timeout_ms: int):
    log_header("Homepage login to Marva")
    keycloak_pages = _record_keycloak_pages(page)
    page.goto(home_url(), timeout=ui_timeout_ms)
    _fill_login(page, keycloak_password(), app="Marva")

    page.wait_for_url(f"{bluecore_url()}/marva/**", timeout=ui_timeout_ms)
    page.wait_for_function(
        "() => !!window.localStorage.getItem('marva_jwt')", timeout=ui_timeout_ms
    )
    log_expected_actual("Keycloak login pages shown", [], keycloak_pages)
    assert keycloak_pages == []


# ========================================================================
# The footer fits smaller screens without overlapping.
# ------------------------------------------------------------------------
@pytest.mark.parametrize("width", [1440, 1100, 900, 600, 390])
def test_footer_fits_narrower_windows(page: Page, ui_timeout_ms: int, width: int):
    log_header(f"Footer at {width}px")
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(home_url(), timeout=ui_timeout_ms)
    footer = page.locator("footer.bluecore-footer")
    expect(footer).to_be_visible()

    result = page.evaluate(
        """() => {
            const boxes = [...document.querySelectorAll(
                'footer.bluecore-footer :is(.bluecore-footer-logo, .bluecore-footer-contact,'
                + ' .bluecore-footer-heading, .bluecore-footer-links a)'
            )].map(e => e.getBoundingClientRect());
            const overlaps = boxes.some((a, i) => boxes.slice(i + 1).some(b =>
                a.left < b.right - 1 && b.left < a.right - 1
                && a.top < b.bottom - 1 && b.top < a.bottom - 1));
            const footer = document.querySelector('footer.bluecore-footer');
            return {
                overlaps,
                scrollWidth: document.documentElement.scrollWidth,
                height: Math.round(footer.getBoundingClientRect().height),
                heightVar: getComputedStyle(document.documentElement)
                    .getPropertyValue('--bluecore-footer-height'),
            };
        }"""
    )
    log_expected_actual("footer", "no overlap, no sideways scroll", result)
    assert not result["overlaps"]
    assert result["scrollWidth"] <= width
    assert result["heightVar"] == f"{result['height']}px"
    if width >= 1024:
        assert result["height"] == 221


def _login_from_home(page: Page, ui_timeout_ms: int, app: str = "Sinopia") -> None:
    page.goto(home_url(), timeout=ui_timeout_ms)
    _fill_login(page, keycloak_password(), app=app)
    page.wait_for_url(f"{bluecore_url()}/sinopia/**", timeout=ui_timeout_ms)


# ========================================================================
# Logged-in users see Welcome back, and the app links open without logging in.
# ------------------------------------------------------------------------
def test_signed_in_user_is_shown_as_signed_in(page: Page, ui_timeout_ms: int):
    log_header("Homepage, signed in")
    _login_from_home(page, ui_timeout_ms)

    page.goto(home_url(), timeout=ui_timeout_ms)
    panel = page.locator("#home-signed-in")
    expect(panel).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator("#home-login-form")).to_be_hidden()
    expect(panel.get_by_role("heading")).to_have_text(
        re.compile(r"^Welcome back, .+!$")
    )
    expect(panel.get_by_text("You are logged in to:")).to_be_visible()
    expect(panel.get_by_role("listitem")).to_have_text(
        ["Sinopia", "Marva", "Graph Toolbox"]
    )
    expect(panel.get_by_role("button", name="Logout")).to_be_visible()

    header = page.locator("header.bluecore-header")
    expect(header.locator(".bluecore-header-user")).to_have_count(0)
    expect(header.get_by_role("button", name="Logout")).to_be_visible()

    keycloak_pages = _record_keycloak_pages(page)
    panel.get_by_role("link", name="Marva").click()
    page.wait_for_url(f"{bluecore_url()}/marva/**", timeout=ui_timeout_ms)
    page.wait_for_function(
        "() => !!window.localStorage.getItem('marva_jwt')", timeout=ui_timeout_ms
    )
    assert keycloak_pages == []


# ========================================================================
# Logout (header or card) logs out and shows the login form again.
# ------------------------------------------------------------------------
@pytest.mark.parametrize(
    "where", ["header.bluecore-header", "#home-signed-in"], ids=["header", "card"]
)
def test_logout_from_the_homepage(page: Page, ui_timeout_ms: int, where: str):
    log_header(f"Homepage logout ({where})")
    _login_from_home(page, ui_timeout_ms)
    page.goto(home_url(), timeout=ui_timeout_ms)
    expect(page.locator("#home-signed-in")).to_be_visible(timeout=ui_timeout_ms)

    page.locator(where).get_by_role("button", name="Logout").click()
    expect(page.locator("#home-login-form")).to_be_visible(timeout=ui_timeout_ms)
    expect(page.locator(".bluecore-header-user")).to_have_count(0)
    log_expected_actual("URL", home_url(), page.url)
    assert page.url == home_url()

    page.reload()
    expect(page.locator("#home-login")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#home-login-form")).to_be_visible()
    expect(page.locator("#home-signed-in")).to_be_hidden()


# ========================================================================
# Forgot password opens the reset form; Back to login returns.
# ------------------------------------------------------------------------
def test_forgot_password_form(page: Page, ui_timeout_ms: int):
    log_header("Homepage forgot password form")
    page.goto(home_url(), timeout=ui_timeout_ms)
    page.locator("#home-login-username").fill("someone")
    page.get_by_role("button", name="Forgot password?").click()

    reset = page.locator("#home-reset-form")
    expect(reset).to_be_visible()
    expect(page.locator("#home-login-form")).to_be_hidden()
    expect(page.locator("#home-reset-username")).to_have_value("someone")

    page.locator("#home-reset-username").fill("")
    reset.get_by_role("button", name="Send reset link").click()
    expect(reset.locator(".home-reset-message")).to_have_text(
        "Enter your username or e-mail address."
    )

    reset.get_by_role("button", name="Back to login").click()
    expect(page.locator("#home-login-form")).to_be_visible()
    expect(reset).to_be_hidden()
