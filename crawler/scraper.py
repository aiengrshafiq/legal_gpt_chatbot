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
    exclude_extensions = [".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".ico", ".svg", ".pdf", "#", "?"]
    exclude_paths = ["/media/", "/login/", "/Userfiles/", "/javascript:"]

    parsed_url = urlparse(url.lower())

    if not parsed_url.scheme.startswith("http"):
        return False

    if any(ext in parsed_url.path for ext in exclude_extensions):
        return False

    if any(exclude in parsed_url.path for exclude in exclude_paths):
        return False

    return True

def normalize_url(url):
    parsed = urlparse(url)
    parts = parsed.path.split('/')
    new_parts = []

    # Remove repeating segments immediately
    for part in parts:
        if part and (len(new_parts) == 0 or part != new_parts[-1]):
            new_parts.append(part)

    normalized_path = '/' + '/'.join(new_parts)
    normalized = urlunparse((parsed.scheme, parsed.netloc, normalized_path, '', '', ''))
    return normalized.rstrip('/')


def sanitize_filename(url):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', url)


def crawl_recursive(start_url, name, driver, visited, depth=0):
    if depth > MAX_DEPTH:
        return []

    domain_root = urlparse(start_url).netloc
    to_visit = [(start_url, 0)]  # Queue with depth
    blob_paths = []

    while to_visit:
        url, current_depth = to_visit.pop(0)

        if url in visited or current_depth > MAX_DEPTH:
            continue

        visited.add(url)

        try:
            driver.get(url)
            time.sleep(1.5)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            filename = sanitize_filename(url)[:100] + ".html"
            local_path = os.path.join(TEMP_SAVE_DIR, filename)
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- SOURCE_URL: {url} -->\n{soup.prettify()}")

            blob_path = f"crawled/html/{filename}"
            upload_file(local_path, blob_path)
            blob_paths.append(blob_path)
            print(f"[Saved HTML] {url}")

            domain_root = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(start_url))

            for a_tag in soup.find_all("a", href=True):
                href = a_tag['href'].strip()
                # Join with domain_root instead of current URL to avoid repetition
                full_link = urljoin(domain_root, href)
                norm_full_link = normalize_url(full_link)

                if (is_valid_url(norm_full_link)
                    and urlparse(norm_full_link).netloc == urlparse(domain_root).netloc
                    and norm_full_link not in visited
                    and norm_full_link not in [x[0] for x in to_visit]):
                    to_visit.append((norm_full_link, current_depth + 1))

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
