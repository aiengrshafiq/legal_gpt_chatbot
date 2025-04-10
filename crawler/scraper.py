import sys
import os
import re
import yaml
import time
import json
import requests
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from azure_blob import upload_file

CRAWLED_RECORD_PATH = os.path.join(os.path.dirname(__file__), "crawled_sites.json")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "crawler_config.yaml")
TEMP_SAVE_DIR = "crawler/temp"
os.makedirs(TEMP_SAVE_DIR, exist_ok=True)

EXCLUDE_PATHS = ["/media/", "/login/", "/Userfiles/"]
MAX_DEPTH = 2

def load_crawled_sites():
    if os.path.exists(CRAWLED_RECORD_PATH):
        with open(CRAWLED_RECORD_PATH, "r") as f:
            return json.load(f)
    return {}

def save_crawled_sites(sites):
    with open(CRAWLED_RECORD_PATH, "w") as f:
        json.dump(sites, f, indent=2)

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {"sites": []}

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)

def is_valid_url(url):
    if not url.startswith("http"):
        return False
    if any(ex in url for ex in EXCLUDE_PATHS):
        return False
    if any(ext in url for ext in [".jpg", ".png", ".gif", ".css", ".js", "#"]):
        return False
    return True

def normalize_url(url):
    parsed = urlparse(url)
    # Remove duplicate segments like /en/en/en/ to /en/
    path_parts = parsed.path.split('/')
    seen = set()
    normalized_parts = []
    for part in path_parts:
        if part and (part not in seen or part == 'en'):
            seen.add(part)
            normalized_parts.append(part)
    normalized_path = '/' + '/'.join(normalized_parts)
    normalized = urlunparse((parsed.scheme, parsed.netloc, normalized_path, '', '', ''))
    return normalized

def sanitize_filename(url):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', url)

def crawl_recursive(start_url, name, driver, visited, depth=0):
    if depth > MAX_DEPTH:
        return []

    domain_root = urlparse(start_url).netloc
    to_visit = [start_url]
    blob_paths = []

    while to_visit:
        url = to_visit.pop()
        norm_url = normalize_url(url)
        if norm_url in visited or not is_valid_url(norm_url):
            print(f"[SKIP LOOPING] {url}")
            continue

        visited.add(norm_url)

        try:
            driver.get(url)
            time.sleep(1.5)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            filename = sanitize_filename(norm_url)[:100] + ".html"
            local_path = os.path.join(TEMP_SAVE_DIR, filename)
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- SOURCE_URL: {url} -->\n" + soup.prettify())
            blob_path = f"crawled/html/{filename}"
            upload_file(local_path, blob_path)
            blob_paths.append(blob_path)
            print(f"[Saved HTML] {url}")

            for a_tag in soup.find_all("a", href=True):
                href = a_tag['href']
                if href.lower().endswith(".pdf"):
                    pdf_url = urljoin(url, href)
                    if not is_valid_url(pdf_url):
                        continue
                    try:
                        pdf_resp = requests.get(pdf_url, timeout=10)
                        if pdf_resp.status_code == 200:
                            pdf_name = sanitize_filename(pdf_url.split("/")[-1])
                            pdf_path = os.path.join(TEMP_SAVE_DIR, pdf_name)
                            with open(pdf_path, "wb") as f:
                                f.write(pdf_resp.content)
                            upload_file(pdf_path, f"crawled/pdfs/{pdf_name}")
                            blob_paths.append(f"crawled/pdfs/{pdf_name}")
                            print(f"[Saved PDF] {pdf_url}")
                    except Exception as e:
                        print(f"Failed to fetch PDF: {pdf_url} — {e}")

            for a_tag in soup.find_all("a", href=True):
                link = urljoin(url, a_tag['href'])
                if is_valid_url(link) and urlparse(link).netloc == domain_root:
                    to_visit.append(link)

        except Exception as e:
            print(f"[ERROR] Failed to crawl {url}: {e}")

    return blob_paths

def crawl_site(name, url):
    print(f"[CRAWL] Crawling full site: {name} at {url} ...")
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        driver = webdriver.Chrome(options=options)

        visited = set()
        blob_paths = crawl_recursive(url, name, driver, visited, depth=0)

        driver.quit()
        return blob_paths

    except Exception as e:
        print(f"[ERROR] Failed to crawl site {url}: {e}")
        return []

def crawl_all_sites(force=False):
    config = load_config()
    crawled_sites = load_crawled_sites()
    updated = False
    new_files = []

    for site in config.get("sites", []):
        name = site.get("name")
        url = site.get("url")
        last_crawled = site.get("last_crawled")

        if not force and url in crawled_sites:
            print(f"[SKIP] Already crawled: {url} at {crawled_sites[url]}")
            continue

        blob_paths = crawl_site(name, url)
        new_files.extend(blob_paths)

        if blob_paths:
            timestamp = datetime.utcnow().isoformat()
            site["last_crawled"] = timestamp
            crawled_sites[url] = timestamp
            updated = True

    if updated:
        save_config(config)
        save_crawled_sites(crawled_sites)
        print("[✅] Updated crawl metadata.")

    return new_files

if __name__ == "__main__":
    crawl_all_sites(force=False)
