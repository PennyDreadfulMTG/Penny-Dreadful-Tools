"""
Browser smoke tests: load real pages in headless Chromium and check what a user would see.

The server-side smoke tests stop at the HTTP status code. These go further: the React live tables must actually fill
with rows, no request the page makes may fail, no JavaScript may throw, and the navigation submenu must be genuinely
visible (on screen, at the top, not clipped, not covered) at mobile, medium and wide widths, with a mouse and with touch.
Both of the September 2026 production regressions (invisible submenu, empty /decks/) fail here.

Two modes:

- Local (default): PD_BROWSER_TESTS=1. Starts the Flask app in-process against the seeded test database.
- Canary: PD_BROWSER_BASE_URL=https://pennydreadfulmagic.com. Runs the same read-only checks against a live site.

Both need `uv run playwright install chromium` once. Set PD_BROWSER_CHANNEL=chrome to use an installed Google Chrome instead.
Not part of the default pytest run: `python dev.py browser`, or in CI the separate `browser` job.
"""
import os
import re
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from shared.container import Container

BASE_URL = os.environ.get('PD_BROWSER_BASE_URL', '').rstrip('/')
ENABLED = bool(BASE_URL) or os.environ.get('PD_BROWSER_TESTS') == '1'

pytestmark = [pytest.mark.browser, pytest.mark.skipif(not ENABLED, reason='Set PD_BROWSER_TESTS=1 or PD_BROWSER_BASE_URL to run browser tests')]

if ENABLED:
    from playwright.sync_api import Browser, Locator, Page, expect, sync_playwright

# Fixed entry points. More pages are discovered from the links on these so the test needs no knowledge of what data the site has.
PAGES = ['/', '/decks/', '/people/', '/cards/', '/metagame/', '/competitions/', '/tournaments/leaderboards/', '/resources/', '/about/']
# Links in tables may carry a /seasons/N/ prefix, so match anywhere in the href.
DISCOVER = [('/decks/', '.decktable a[href*="/people/"]'), ('/decks/', '.decktable a[href*="/archetypes/"]'), ('/decks/', '.decktable a[href*="/competitions/"]'), ('/decks/', '.decktable a[href*="/decks/"]'), ('/cards/', '.cardtable a[href*="/cards/"]')]
LIVE_TABLE_CLASSES = ['decktable', 'cardtable', 'persontable', 'matchtable', 'leaderboardtable', 'headtoheadtable']
LOAD_TIMEOUT = 15_000
VIEWPORTS = {'mobile': (400, 800), 'medium': (1200, 800), 'wide': (1700, 900)}  # Either side of the 900px and 1600px breakpoints in pd.css.


@pytest.fixture(scope='module')
def browser() -> Iterator['Browser']:
    with sync_playwright() as playwright:
        b = playwright.chromium.launch(channel=os.environ.get('PD_BROWSER_CHANNEL') or None)
        yield b
        b.close()


@pytest.fixture
def site(request: pytest.FixtureRequest) -> Iterator[Container]:
    if BASE_URL:
        yield Container({'base_url': BASE_URL, 'seed': None})
        return
    from werkzeug.serving import make_server

    from decksite.main import APP
    seed = request.getfixturevalue('seeded_db')
    server = make_server('127.0.0.1', 0, APP, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Container({'base_url': f'http://127.0.0.1:{server.server_port}', 'seed': seed})
    finally:
        server.shutdown()
        thread.join(timeout=5)


class ProblemCollector:
    """Everything a user would experience as breakage but that never shows up in an HTTP status: JS exceptions, console errors, failed same-origin requests."""

    def __init__(self, page: 'Page', base_url: str) -> None:
        self.problems: list[str] = []
        page.on('pageerror', lambda e: self.problems.append(f'uncaught exception: {e}'))
        page.on('console', lambda m: self.problems.append(f'console.error: {m.text}') if m.type == 'error' else None)
        page.on('response', lambda r: self.problems.append(f'HTTP {r.status} from {r.url}') if r.status >= 400 and r.url.startswith(base_url) else None)
        page.on('requestfailed', lambda r: self.problems.append(f'request failed: {r.url} ({r.failure})') if r.url.startswith(base_url) else None)


def new_page(browser: 'Browser', site: Container, viewport: tuple[int, int] = VIEWPORTS['medium'], **context_args: Any) -> tuple['Page', ProblemCollector]:
    context = browser.new_context(viewport={'width': viewport[0], 'height': viewport[1]}, base_url=site.base_url, **context_args)
    page = context.new_page()
    return page, ProblemCollector(page, site.base_url)


def wait_for_live_tables(page: 'Page') -> list[str]:
    """Wait for every live table/grid on the page to finish loading and return a problem per one that is empty or errored."""
    problems = []
    for css_class in [*LIVE_TABLE_CLASSES, 'metagamegrid']:
        for i in range(page.locator(f'div.{css_class}').count()):
            root = page.locator(f'div.{css_class}').nth(i)
            rows = root.locator('.metagame-grid > *' if css_class == 'metagamegrid' else 'table tbody tr')
            try:
                expect(rows.first).to_be_attached(timeout=LOAD_TIMEOUT)
            except AssertionError:
                error = root.locator('.message.error')
                detail = error.first.text_content() if error.count() else ('still loading' if root.locator('.loading').count() else 'no rows')
                problems.append(f'{page.url}: {css_class} #{i} is empty ({detail})')
    return problems


def discover_pages(page: 'Page') -> list[str]:
    found = []
    for source, selector in DISCOVER:
        page.goto(source)
        wait_for_live_tables(page)
        href = page.locator(selector).first.get_attribute('href') if page.locator(selector).count() else None
        if href and href.startswith('/') and href not in found:
            found.append(href)
    return found


def test_pages_render_with_data_and_without_errors(browser: 'Browser', site: Container) -> None:
    page, collector = new_page(browser, site)
    pages = PAGES + discover_pages(page)
    if site.seed:
        # Only the seeded database has this person, so a server answering from any other database (the dev one, say) turns this into a 404 below.
        pages.append(f'/people/{site.seed.person}/')
    problems = list(collector.problems)
    for path in pages:
        collector.problems.clear()
        response = page.goto(path)
        assert response is not None
        if response.status != 200:
            problems.append(f'{path}: HTTP {response.status}')
            continue
        problems.extend(wait_for_live_tables(page))
        problems.extend(f'{path}: {p}' for p in collector.problems)
    if site.seed:
        assert any('/people/' in p and p != '/people/' for p in pages) and any('/cards/' in p and p != '/cards/' for p in pages), f'Discovery found no person/card pages in {pages}'
    assert not problems, '\n'.join(problems)


def submenu_items(page: 'Page') -> 'Locator':
    return page.locator('.menu > li:has(.submenu):visible')


def open_nav_if_drawer(page: 'Page') -> None:
    if page.locator('.hamburger').is_visible():
        page.locator('.hamburger').click()
        expect(page.locator('nav')).to_have_class(re.compile(r'\bshowing\b'))


def assert_submenu_usable(page: 'Page', item: 'Locator', label: str) -> None:
    """The submenu must be fully on screen, start at the top of the viewport, and its links must be the thing under the cursor (so neither clipped by a scroll container nor covered by another element)."""
    submenu = item.locator('.submenu')
    expect(submenu).to_have_css('opacity', '1', timeout=3000)
    expect(submenu).to_have_css('visibility', 'visible')
    viewport = page.viewport_size
    assert viewport
    box = submenu.bounding_box()
    assert box, f'{label}: submenu has no box'
    assert box['height'] > 0 and box['width'] > 0, f'{label}: submenu has no size {box}'
    assert abs(box['y']) <= 1, f'{label}: submenu should start at the top of the viewport but its top is at y={box["y"]}'
    assert box['x'] >= 0 and box['x'] + box['width'] <= viewport['width'] + 1, f'{label}: submenu is horizontally off screen {box} in {viewport}'
    assert box['y'] + box['height'] <= viewport['height'] + 1, f'{label}: submenu runs off the bottom {box} in {viewport}'
    links = submenu.locator('a.item')
    assert links.count() > 0, f'{label}: submenu has no links'
    for i in [0, links.count() - 1]:
        link = links.nth(i)
        link_box = link.bounding_box()
        assert link_box, f'{label}: submenu link {i} has no box'
        x, y = link_box['x'] + link_box['width'] / 2, link_box['y'] + link_box['height'] / 2
        under_cursor = page.evaluate('([x, y]) => { const e = document.elementFromPoint(x, y); return e ? (e.closest("a.item")?.textContent ?? e.outerHTML.slice(0, 120)) : null; }', [x, y])
        assert under_cursor == link.text_content(), f'{label}: submenu link {link.text_content()!r} is covered or clipped; the element at its centre is {under_cursor!r}'


@pytest.mark.parametrize('viewport_name', list(VIEWPORTS))
def test_submenu_opens_on_hover(browser: 'Browser', site: Container, viewport_name: str) -> None:
    page, collector = new_page(browser, site, VIEWPORTS[viewport_name])
    page.goto('/')
    open_nav_if_drawer(page)
    items = submenu_items(page)
    assert items.count() >= 2
    # The first item is near the top so it can look right even when submenus are wrongly anchored to their own menu item. The last one cannot.
    for index in [0, items.count() - 1]:
        item = items.nth(index)
        item.locator(':scope > a.item').hover()
        expect(item).to_have_class(re.compile(r'\bsubmenu-open\b'), timeout=3000)
        assert_submenu_usable(page, item, f'{viewport_name} item {index}')
        page.mouse.move(0, page.viewport_size['height'] - 1) if page.viewport_size else None
        expect(item).not_to_have_class(re.compile(r'\bsubmenu-open\b'), timeout=3000)
    assert not collector.problems, '\n'.join(collector.problems)


def test_submenu_opens_on_tap_and_stays_open(browser: 'Browser', site: Container) -> None:
    page, collector = new_page(browser, site, VIEWPORTS['mobile'], has_touch=True, is_mobile=True)
    page.goto('/')
    assert page.evaluate('matchMedia("(hover: none)").matches'), 'Touch emulation should report (hover: none)'
    open_nav_if_drawer(page)
    items = submenu_items(page)
    item = items.nth(items.count() - 1)
    link = item.locator(':scope > a.item')
    link.tap()
    expect(item).to_have_class(re.compile(r'\bsubmenu-open\b'), timeout=3000)
    assert_submenu_usable(page, item, 'touch')
    expect(page).to_have_url(re.compile(r'/$'))  # First tap opens the submenu without following the link.
    other = items.nth(0)
    other.locator(':scope > a.item').tap()
    expect(other).to_have_class(re.compile(r'\bsubmenu-open\b'), timeout=3000)
    expect(item).not_to_have_class(re.compile(r'\bsubmenu-open\b'))
    href = other.locator(':scope > a.item').get_attribute('href')
    assert href and href != '/'
    other.locator(':scope > a.item').tap()  # Second tap on the open item follows its link.
    expect(page).to_have_url(re.compile(re.escape(href) + '$'), timeout=LOAD_TIMEOUT)
    assert not collector.problems, '\n'.join(collector.problems)


def test_current_submenu_shown_in_flow_when_wide(browser: 'Browser', site: Container) -> None:
    page, collector = new_page(browser, site, VIEWPORTS['wide'])
    page.goto('/decks/')
    item = page.locator('.menu > li:has(> a.item.current):has(.submenu)')
    expect(item).to_have_count(1)
    assert_submenu_usable(page, item, 'wide current')
    submenu_box = item.locator('.submenu').bounding_box()
    main_box = page.locator('main').bounding_box()
    assert submenu_box and main_box
    assert main_box['x'] >= submenu_box['x'] + submenu_box['width'] - 1, f'Page content at x={main_box["x"]} is under the in-flow submenu ending at {submenu_box["x"] + submenu_box["width"]}'
    assert not collector.problems, '\n'.join(collector.problems)
