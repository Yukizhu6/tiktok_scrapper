import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json

# 1. 配置浏览器选项
def setup_driver():
    options = Options()
    options.add_argument("--headless")  # 无头模式，不弹窗
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    return driver

# 2. 打开页面并等待加载
def fetch_explore_page_html(driver, url="https://www.tiktok.com/explore?lang=cn"):
    driver.get(url)
    time.sleep(6)  # 视网速和反爬机制调整等待时间
    return driver.page_source

# 3. 解析视频链接和信息
def parse_tiktok_explore(html):
    soup = BeautifulSoup(html, "lxml")
    result = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/video/" in href:
            # 提取标题（有时可能为空）
            title_tag = a.find("div", attrs={"data-e2e": "video-title"})
            title = title_tag.get_text(strip=True) if title_tag else "No title"
            result.append({
                "url": href,
                "title": title
            })
    # 去重
    seen = set()
    clean_result = []
    for item in result:
        if item["url"] not in seen:
            seen.add(item["url"])
            clean_result.append(item)
    return clean_result

# 4. 主程序
def main():
    driver = setup_driver()
    html = fetch_explore_page_html(driver)
    videos = parse_tiktok_explore(html)
    driver.quit()

    print(f"✅ 抓取到 {len(videos)} 个视频链接：")
    for v in videos[:10]:  # 只展示前 10 个
        print(f"🎬 {v['title']} -> {v['url']}")

if __name__ == "__main__":
    driver = setup_driver()
    html = fetch_explore_page_html(driver)
    videos = parse_tiktok_explore(html)
    driver.quit()
    print(json.dumps(videos, ensure_ascii=False, indent=2))
