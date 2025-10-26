import argparse
import json
import os
from utils.browser import create_page
from scrapers.tiktok_base import maybe_accept_cookies, wait_for_initial_data


def diagnose(url: str, headless: bool = False, save: bool = False) -> dict:
    with create_page(headless=headless) as page:
        page.goto(url, wait_until="load", timeout=60_000)
        maybe_accept_cookies(page)
        wait_for_initial_data(page, timeout_ms=10_000)
        page.wait_for_timeout(1500)

        diag = page.evaluate(
            """
            () => {
              const og = (p) => (document.querySelector(`meta[property="${p}"]`) || {}).content || '';
              const stateScript = document.querySelector('#SIGI_STATE') || document.querySelector('script[id*="SIGI"]');
              let stateLen = 0;
              try { stateLen = (stateScript && stateScript.textContent && stateScript.textContent.length) || 0; } catch(e) {}
              const nextEl = document.querySelector('#__NEXT_DATA__');
              let nextLen = 0;
              try { nextLen = (nextEl && nextEl.textContent && nextEl.textContent.length) || 0; } catch(e) {}
              const ld = document.querySelectorAll('script[type="application/ld+json"]')?.length || 0;
              const hasVerify = !!(document.querySelector('#tiktok-verify-ele, [data-e2e*="captcha"], [id*="captcha"], #captcha-verify-image') || Array.from(document.querySelectorAll('*')).some(el => /verify you|access denied/i.test(el.textContent || '')));
              const cookieBanner = !!document.querySelector('[data-e2e="cookie-banner-accept-button"]');
              const hasVideo = !!document.querySelector('video');
              const sigiWindow = !!(window.SIGI_STATE && window.SIGI_STATE.ItemModule);
              const keys = sigiWindow ? Object.keys(window.SIGI_STATE.ItemModule || {}) : [];
              return {
                url: location.href,
                title: document.title,
                ogTitle: og('og:title') || '',
                hasWindowSIGI: sigiWindow,
                hasSIGIScript: !!stateScript,
                sigiScriptLength: stateLen,
                hasNextData: !!nextEl,
                nextScriptLength: nextLen,
                ldJsonCount: ld,
                hasVerifyPage: hasVerify,
                hasCookieBanner: cookieBanner,
                hasVideoTag: hasVideo,
                sigiItemKeys: keys,
              };
            }
            """
        )

        if save:
            html_path = os.path.abspath("video_debug.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            diag["savedHtml"] = html_path

        return diag


def main():
    ap = argparse.ArgumentParser(description="Diagnose TikTok video page data availability")
    ap.add_argument("--url", required=True, help="TikTok video URL")
    ap.add_argument("--headless", type=int, default=0, help="1=headless, 0=headful")
    ap.add_argument("--save", action="store_true", help="Save page HTML to video_debug.html")
    args = ap.parse_args()

    out = diagnose(args.url, headless=bool(args.headless), save=args.save)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

