import sys
import os
import re
import yaml
import time
import json
import requests
from datetime import datetime
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from azure_blob import upload_file

# Constants and paths
CRAWLED_RECORD_PATH = os.path.join(os.path.dirname(__file__), "crawled_sites.json")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "crawler_config.yaml")
TEMP_SAVE_DIR = "crawler/temp"
os.makedirs(TEMP_SAVE_DIR, exist_ok=True)

# === Helpers for config and crawled sites ===

def load_crawled_sites():
    if os.path.exists(CRAWLED_RECORD_PATH):
        with open(CRAWLED_RECORD_PATH, "r") as f:
            return set(json.load(f))
    return set()

def save_crawled_sites(sites):
    with open(CRAWLED_RECORD_PATH, "w") as f:
        json.dump(sorted(list(sites)), f)


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {"sites": []}

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)

def is_valid_url(url):
    return url.startswith("http") and not any(ext in url for ext in [".jpg", ".png", ".gif", ".css", ".js", "#"])

def sanitize_filename(url):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', url)

def crawl_page(url, visited, driver, domain_root):
    if url in visited:
        return []
    visited.add(url)

    try:
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Save full HTML to blob
        html_filename = sanitize_filename(url)[:100] + ".html"
        local_path = os.path.join(TEMP_SAVE_DIR, html_filename)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        upload_file(local_path, f"crawled/html/{html_filename}")
        print(f"[Saved HTML] {url}")

        # Find PDFs and upload them
        for a_tag in soup.find_all("a", href=True):
            href = a_tag['href']
            if href.lower().endswith(".pdf"):
                pdf_url = urljoin(url, href)
                try:
                    pdf_resp = requests.get(pdf_url, timeout=10)
                    if pdf_resp.status_code == 200:
                        pdf_name = sanitize_filename(pdf_url.split("/")[-1])
                        pdf_path = os.path.join(TEMP_SAVE_DIR, pdf_name)
                        with open(pdf_path, "wb") as f:
                            f.write(pdf_resp.content)
                        upload_file(pdf_path, f"crawled/pdfs/{pdf_name}")
                        print(f"[Saved PDF] {pdf_url}")
                except Exception as e:
                    print(f"Failed to fetch PDF: {pdf_url} — {e}")

        # Recursively crawl other links
        next_links = []
        for a_tag in soup.find_all("a", href=True):
            link = urljoin(url, a_tag['href'])
            if is_valid_url(link) and urlparse(link).netloc == domain_root:
                next_links.append(link)

        return next_links

    except Exception as e:
        print(f"Error crawling {url}: {e}")
        return []



# === Core crawling logic ===
def crawl_site(name, url):
    print(f"[CRAWL] Crawling {name} at {url} ...")
    try:
        options = Options()
        options.add_argument('--headless')
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        html = driver.page_source
        driver.quit()

        filename = f"{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
        full_path = os.path.join(TEMP_SAVE_DIR, filename)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- SOURCE_URL: {url} -->\n" + html)

        upload_file(full_path, f"crawled/html/{filename}")
        print(f"[✅] Crawled and saved {filename}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to crawl {url}: {e}")
        return False


# === Run full crawl ===
def crawl_all_sites(force=False):
    config = load_config()
    crawled_sites = load_crawled_sites()
    updated = False

    for site in config.get("sites", []):
        name = site.get("name")
        url = site.get("url")
        last_crawled = site.get("last_crawled")

        if not force and url in crawled_sites:
            print(f"[SKIP] Already crawled: {url} at {crawled_sites[url]}")
            continue

        success = crawl_site(name, url)
        if success:
            timestamp = datetime.utcnow().isoformat()
            site["last_crawled"] = timestamp
            crawled_sites[url] = timestamp
            updated = True

    if updated:
        save_config(config)
        save_crawled_sites(crawled_sites)
        print("[✅] Updated crawl metadata.")
    else:
        print("[ℹ️] No new sites crawled.")


if __name__ == "__main__":
    crawl_all_sites(force=False)
