from contextlib import contextmanager
from playwright.sync_api import sync_playwright, Page


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/115.0 Safari/537.36"
)


@contextmanager
def create_page(headless: bool = True) -> Page:
    """Create a Playwright Chromium page with sensible defaults.

    - Headless by default
    - User-Agent spoofing and 1920x1080 viewport
    - Closes all resources automatically on exit
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(
            user_agent=DEFAULT_UA,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()


def get_page_content(url: str, wait_ms: int = 6000, headless: bool = True) -> str:
    """Open a URL and return final HTML content using Playwright."""
    with create_page(headless=headless) as page:
        page.goto(url, wait_until="load", timeout=60_000)
        page.wait_for_timeout(wait_ms)
        return page.content()


def collect_links(page: Page, css: str) -> list[str]:
    """Return unique absolute links for elements matching CSS."""
    return page.eval_on_selector_all(
        css, "els => Array.from(new Set(els.map(e => e.href).filter(Boolean)))"
    )


# Backward-compatibility stub for old Selenium initializer
def init_chrome_driver(*_args, **_kwargs):  # pragma: no cover
    raise RuntimeError(
        "Selenium 已被移除，请改用 Playwright。使用 utils.browser.create_page() 或 get_page_content()。"
    )


