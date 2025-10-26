from bs4 import BeautifulSoup
from utils.browser import get_page_content, create_page
from typing import List, Dict
import json
import re
import os
from playwright.sync_api import Page


def fetch_explore_page_html(url: str = "https://www.tiktok.com/explore?lang=cn") -> str:
    """打开 TikTok 发现页并返回 HTML（基于 Playwright）。"""
    return get_page_content(url=url, wait_ms=6000, headless=True)


def parse_tiktok_explore(html: str):
    """Parse explore HTML to extract video links and titles, de-duplicated."""
    soup = BeautifulSoup(html, "lxml")
    result = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/video/" in href:
            title_tag = (
                a.find("div", attrs={"data-e2e": "video-title"})
                or a.find("strong")
                or a.find("span")
            )
            title = title_tag.get_text(strip=True) if title_tag else "No title"
            result.append({"url": href, "title": title})

    seen = set()
    clean_result = []
    for item in result:
        if item["url"] not in seen:
            seen.add(item["url"])
            clean_result.append(item)
    return clean_result


def fetch_explore_links(wait_ms: int = 9000, headless: bool = False) -> List[Dict[str, str]]:
    """Use Playwright to extract explore video links and titles directly from the live DOM.

    - Waits for page load and a short delay
    - Performs a gentle scroll to trigger lazy content
    - Queries anchors with href containing '/video/' and attempts to read nearby title
    """
    url = "https://www.tiktok.com/explore?lang=cn"
    with create_page(headless=headless) as page:
        page.goto(url, wait_until="load", timeout=60_000)
        maybe_accept_cookies(page)
        page.wait_for_timeout(wait_ms)
        # Gentle scroll to trigger lazy loading
        for _ in range(3):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(800)

        js = """
        () => {
          const anchors = Array.from(document.querySelectorAll('a[href*="/video/"]'));
          const items = anchors.map(a => {
            const href = a.getAttribute('href');
            const titleEl = a.querySelector('[data-e2e="video-title"], strong, span');
            const title = (titleEl && titleEl.textContent) ? titleEl.textContent.trim() : '';
            return { url: href, title: title || 'No title' };
          });
          // de-duplicate by url
          const seen = new Set();
          const dedup = [];
          for (const it of items) {
            if (!it.url || seen.has(it.url)) continue;
            seen.add(it.url);
            dedup.push(it);
          }
          return dedup;
        }
        """
        data = page.evaluate(js)
        return data or []


def save_debug_html(html: str, path: str = "tiktok_explore_debug.html") -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.abspath(path)


def maybe_accept_cookies(page: Page) -> None:
    try:
        page.evaluate(
            """
            () => {
              const btn = document.querySelector('[data-e2e="cookie-banner-accept-button"]') ||
                          Array.from(document.querySelectorAll('button, div[role="button"]'))
                               .find(b => /accept all|同意|允许|同意所有/i.test(b.textContent || ''));
              if (btn) btn.click();
            }
            """
        )
    except Exception:
        pass


def wait_for_initial_data(page: Page, timeout_ms: int = 8000) -> None:
    try:
        page.wait_for_function(
            "() => (window.SIGI_STATE && window.SIGI_STATE.ItemModule) || document.querySelector('#__NEXT_DATA__') || document.querySelector('script[type=\"application/ld+json\"]')",
            timeout=timeout_ms,
        )
    except Exception:
        pass


if __name__ == "__main__":
    # Prefer rich metadata extraction. Fallback to HTML parse for debugging.
    try:
        items = collect_explore_items(number=5, headless=False)
        print(json.dumps(items, ensure_ascii=False, indent=2))
    except Exception as e:
        html = fetch_explore_page_html()
        path = save_debug_html(html)
        parsed = parse_tiktok_explore(html)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        print(f"Saved HTML for inspection: {path}")


def extract_video_metadata(page) -> Dict[str, object]:
    """Extract rich metadata from a TikTok video page using embedded JSON state.

    Returns a dict with keys:
      - authorMeta.avatar, authorMeta.name
      - text
      - diggCount, shareCount, playCount, commentCount, collectCount
      - videoMeta.duration
      - musicMeta.musicName, musicMeta.musicAuthor, musicMeta.musicOriginal
      - createTimeISO
      - webVideoUrl
      - downloadUrl (best-effort)
    """
    js = (
        """
        () => {
          function parseStateFromScript(txt) {
            if (!txt) return null;
            try { return JSON.parse(txt); } catch (e) {}
            try {
              const cleaned = txt
                .replace(/^\s*window\.(?:SIGI_STATE)\s*=\s*/i, '')
                .replace(/^\s*window\[["']SIGI_STATE["']\]\s*=\s*/i, '')
                .replace(/;\s*$/, '');
              return JSON.parse(cleaned);
            } catch (e) {}
            try { return (new Function('var window={}; return (' + txt + ')'))(); } catch (e) {}
            return null;
          }

          function fillFromItem(item, state, result) {
            if (!item) return false;
            result.webVideoUrl = location.href;
            result.text = item.desc || item.title || '';
            const stats = item.stats || {};
            result.diggCount = stats.diggCount || 0;
            result.shareCount = stats.shareCount || 0;
            result.playCount = stats.playCount || 0;
            result.commentCount = stats.commentCount || 0;
            result.collectCount = stats.collectCount || 0;
            const video = item.video || {};
            result["videoMeta.duration"] = (video && (video.duration || video.videoMeta?.duration)) ?? null;
            const music = item.music || {};
            result["musicMeta.musicName"] = music.title || music.musicName || '';
            result["musicMeta.musicAuthor"] = music.authorName || music.musicAuthor || '';
            result["musicMeta.musicOriginal"] = !!(music.original ?? music.musicOriginal);
            const authorName = item.author || item.author?.uniqueId || '';
            result["authorMeta.name"] = authorName || (item.author && (item.author.uniqueId || item.author.nickname)) || '';
            const users = (state && state.UserModule && state.UserModule.users) || {};
            const u = users[authorName] || (item.author || {}) || Object.values(users)[0];
            result["authorMeta.avatar"] = (u && (u.avatarLarger || u.avatarThumb || u.avatarMedium)) || '';
            if (item.createTime) {
              const ts = Number(item.createTime) * 1000;
              if (!Number.isNaN(ts)) { try { result.createTimeISO = new Date(ts).toISOString(); } catch {}
              }
            }
            // choose download url
            const bitrateInfo = Array.isArray(video.bitrateInfo) ? video.bitrateInfo : [];
            const bi0 = bitrateInfo[0] || {};
            let cand = video.downloadAddr || video.playAddr || bi0.PlayAddr || bi0.playAddr || '';
            const pickFromObj = (obj) => {
              if (!obj) return '';
              if (typeof obj === 'string') return obj;
              if (obj.UrlList && obj.UrlList.length) return obj.UrlList[0];
              if (obj.url_list && obj.url_list.length) return obj.url_list[0];
              if (Array.isArray(obj) && obj.length) return obj[0];
              return '';
            };
            if (typeof cand !== 'string') cand = pickFromObj(cand);
            if (!cand) cand = pickFromObj(video.downloadAddr) || pickFromObj(video.playAddr) || pickFromObj(bi0.PlayAddr) || pickFromObj(bi0.playAddr);
            result.downloadUrl = cand || '';
            if (!result.downloadUrl) {
              const v = document.querySelector('video');
              if (v && v.src) result.downloadUrl = v.src;
            }
            return true;
          }

          const result = {};
          // 1) Try SIGI_STATE
          let state = (window.SIGI_STATE) ? window.SIGI_STATE : null;
          if (!state) {
            const stateScript = document.querySelector('#SIGI_STATE') || document.querySelector('script[id*="SIGI"]');
            const jsonTxt = stateScript ? stateScript.textContent : '';
            state = parseStateFromScript(jsonTxt);
          }
          if (state && state.ItemModule) {
            const items = Object.values(state.ItemModule);
            if (items && items.length) {
              if (fillFromItem(items[0], state, result)) return result;
            }
          }

          // 2) Try Next.js data
          try {
            const nextEl = document.querySelector('#__NEXT_DATA__');
            if (nextEl && nextEl.textContent) {
              const next = JSON.parse(nextEl.textContent);
              const pp = next && next.props && next.props.pageProps;
              const item = (pp && pp.itemInfo && pp.itemInfo.itemStruct) || (pp && pp.videoData && pp.videoData.itemInfos) || null;
              if (item && fillFromItem(item, null, result)) return result;
            }
          } catch (e) {}

          // 3) Try LD+JSON
          try {
            const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
            const objs = scripts.map(s => { try { return JSON.parse(s.textContent); } catch(e) { return null; } }).filter(Boolean);
            const vid = objs.find(o => o['@type'] && (String(o['@type']).toLowerCase().includes('video')));
            if (vid) {
              result.webVideoUrl = location.href;
              result.text = vid.description || vid.name || '';
              // Basic counts if present
              if (Array.isArray(vid.interactionStatistic)) {
                for (const st of vid.interactionStatistic) {
                  const t = (st.interactionType && (st.interactionType['@type'] || st.interactionType.name || st.interactionType)) || '';
                  const c = Number(st.userInteractionCount || 0);
                  if (/like/i.test(t)) result.diggCount = c;
                  if (/comment/i.test(t)) result.commentCount = c;
                  if (/share/i.test(t)) result.shareCount = c;
                  if (/play|view/i.test(t)) result.playCount = c;
                }
              }
              result["videoMeta.duration"] = vid.duration || result["videoMeta.duration"] || null;
              if (vid.uploadDate) {
                try { result.createTimeISO = new Date(vid.uploadDate).toISOString(); } catch {}
              }
              result["authorMeta.name"] = (vid.author && (vid.author.name || vid.author)) || result["authorMeta.name"] || '';
              result.downloadUrl = vid.contentUrl || vid.embedUrl || result.downloadUrl || '';
              return result;
            }
          } catch (e) {}

          // 4) Minimal OG fallback
          try {
            result.webVideoUrl = location.href;
            const og = (p) => (document.querySelector(`meta[property="${p}"]`) || {}).content || '';
            const name = og('og:title') || '';
            const desc = (document.querySelector('meta[name="description"]') || {}).content || '';
            result.text = desc || name;
            result.downloadUrl = og('og:video') || og('og:video:secure_url') || '';
          } catch (e) {}

          return result;
        }
        """
    )
    return page.evaluate(js)


def collect_explore_items(number: int = 10, headless: bool = True) -> List[Dict[str, object]]:
    """Open explore page, collect video URLs, then visit and extract rich metadata.

    - number: max number of videos to return
    - headless: pass to Playwright
    """
    url = "https://www.tiktok.com/explore?lang=cn"
    items: List[Dict[str, object]] = []
    with create_page(headless=headless) as page:
        page.goto(url, wait_until="load", timeout=60_000)
        maybe_accept_cookies(page)
        page.wait_for_timeout(6000)
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
        links: List[str] = page.eval_on_selector_all(
            'a[href*="/video/"]',
            'els => Array.from(new Set(els.map(e => e.href).filter(Boolean)))',
        )
        links = links[:number]

        for href in links:
            try:
                page.goto(href, wait_until="load", timeout=60_000)
                maybe_accept_cookies(page)
                # Wait for SIGI state or other data scripts to load
                wait_for_initial_data(page, timeout_ms=9000)
                page.wait_for_timeout(3000)
                meta = extract_video_metadata(page)
                # Ensure webVideoUrl and fallback if missing
                if not meta.get("webVideoUrl"):
                    meta["webVideoUrl"] = href
                items.append(meta)
            except Exception:
                items.append({"webVideoUrl": href})
    return items
