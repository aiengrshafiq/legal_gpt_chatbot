import os
import re
import yaml
import time
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from azure_blob import upload_file

CRAWLED_RECORD_PATH = os.path.join(os.path.dirname(__file__), "crawled_sites.json")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "crawler_config.yaml")
TEMP_SAVE_DIR = "crawler/temp"
os.makedirs(TEMP_SAVE_DIR, exist_ok=True)

MAX_DEPTH = 4

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

def is_valid_url(url):
    exclude_extensions = [".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".ico", ".svg", "#", "?"]
    parsed_url = urlparse(url.lower())
    return parsed_url.scheme.startswith("http") and not any(ext in parsed_url.path for ext in exclude_extensions)

def normalize_url(url):
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split('/') if part]

    # Remove consecutive repeating parts (e.g., /en/en/en → /en)
    cleaned_parts = []
    for i, part in enumerate(path_parts):
        if i == 0 or part != path_parts[i - 1]:
            cleaned_parts.append(part)

    # Optionally, remove over-repetition of common locale indicators (like 'en', 'ar')
    # Only keep the first occurrence of any language code
    language_tags = {"en", "ar"}
    seen_langs = set()
    final_parts = []
    for part in cleaned_parts:
        if part in language_tags:
            if part in seen_langs:
                continue
            seen_langs.add(part)
        final_parts.append(part)

    normalized_path = '/' + '/'.join(final_parts)
    final_deduped = []
    for part in final_parts:
        if not final_deduped or part != final_deduped[-1]:
            final_deduped.append(part)

    normalized_path = '/' + '/'.join(final_deduped)
    return urlunparse((parsed.scheme, parsed.netloc, normalized_path, '', '', ''))



def sanitize_filename(url):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', url)

def detect_and_download_pdf(driver, url, blob_paths):
    pdf_content = None
    for request in driver.requests:
        if request.response and 'application/pdf' in request.response.headers.get('Content-Type', ''):
            pdf_content = request.response.body
            break

    if pdf_content:
        filename = sanitize_filename(url)[:100] + ".pdf"
        local_pdf_path = os.path.join(TEMP_SAVE_DIR, filename)
        with open(local_pdf_path, "wb") as f:
            f.write(pdf_content)
        blob_path = f"crawled/pdfs/{filename}"
        upload_file(local_pdf_path, blob_path)
        blob_paths.append(blob_path)
        print(f"[📄 PDF saved via Selenium Wire] {url}")
    else:
        print(f"[⚠️ PDF not intercepted] {url}")


def crawl_recursive(url, driver, visited, blob_paths, depth=0):
    if depth > MAX_DEPTH:
        return

    norm_url = normalize_url(url)
    if norm_url in visited or not is_valid_url(norm_url):
        print(f"[SKIP LOOPING] {url}")
        return

    visited.add(norm_url)  

    try:
        driver.get(url)
        time.sleep(2) 

        if url.lower().endswith(".pdf.aspx"):
            detect_and_download_pdf(driver, url, blob_paths)
            return

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        filename = sanitize_filename(url)[:100] + ".html"
        local_path = os.path.join(TEMP_SAVE_DIR, filename)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- SOURCE_URL: {url} -->\n{soup.prettify()}")

        blob_path = f"crawled/html/{filename}"
        upload_file(local_path, blob_path)
        blob_paths.append(blob_path)
        print(f"[📄 HTML saved] {url}")

        for a_tag in soup.find_all("a", href=True):
            link = urljoin(url, a_tag['href'].strip())
            norm_link = normalize_url(link)
            if is_valid_url(norm_link) and norm_link not in visited:
                crawl_recursive(norm_link, driver, visited, blob_paths, depth + 1)

    except Exception as e:
        print(f"[ERROR] Failed to crawl {url}: {e}")


def crawl_site(name, url):
    print(f"[CRAWL START] {name} at {url}")
    options = Options()
    options.headless = True
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')

    driver = webdriver.Chrome(options=options)
    visited = set()
    blob_paths = []

    crawl_recursive(url, driver, visited, blob_paths)

    driver.quit()
    print(f"[CRAWL END] {name}")
    return blob_paths

def crawl_all_sites(force=False):
    config = load_config()
    crawled_sites = load_crawled_sites()
    updated = False
    new_files = []

    for site in config.get("sites", []):
        url = site["url"]
        if not force and url in crawled_sites:
            print(f"[SKIP] Already crawled: {url}")
            continue

        blob_paths = crawl_site(site["name"], url)
        if blob_paths:
            new_files.extend(blob_paths)
            crawled_sites[url] = datetime.utcnow().isoformat()
            updated = True

    if updated:
        save_crawled_sites(crawled_sites)
        print("[✅ Metadata updated]")

    return new_files


if __name__ == "__main__":
    crawl_all_sites()
