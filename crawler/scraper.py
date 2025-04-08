import sys
import os
# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import re
import yaml
import time
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from azure_blob import upload_file
from datetime import datetime
import requests

import json

CRAWLED_RECORD_PATH = os.path.join(os.path.dirname(__file__), "crawled_sites.json")

def load_crawled_sites():
    if os.path.exists(CRAWLED_RECORD_PATH):
        with open(CRAWLED_RECORD_PATH, "r") as f:
            return set(json.load(f))
    return set()

def save_crawled_sites(sites):
    with open(CRAWLED_RECORD_PATH, "w") as f:
        json.dump(sorted(list(sites)), f)



CONFIG_PATH = os.path.join(os.path.dirname(__file__), "crawler_config.yaml")
TEMP_SAVE_DIR = "crawler/temp"
os.makedirs(TEMP_SAVE_DIR, exist_ok=True)

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



def crawl_site(site_config, force=False):
    start_url = site_config["url"]
    domain = urlparse(start_url).netloc
    visited = set()

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        to_visit = [start_url]
        while to_visit:
            current = to_visit.pop()
            new_links = crawl_page(current, visited, driver, domain)
            to_visit.extend([link for link in new_links if link not in visited])

        site_config["last_crawled"] = datetime.utcnow().isoformat()
        print(f"[✅ Completed] Crawled {len(visited)} pages from {domain}")
        return domain

    finally:
        driver.quit()


def crawl_all_sites(force=False):
    config = load_config()
    crawled_sites = load_crawled_sites()

    for site in config["sites"]:
        domain = urlparse(site["url"]).netloc
        if not force and domain in crawled_sites:
            print(f"[SKIP] {domain} already crawled.")
            continue

        result = crawl_site(site, force=force)
        if result:
            crawled_sites.add(result)

    save_config(config)
    save_crawled_sites(crawled_sites)


if __name__ == "__main__":
    crawl_all_sites(force=False)
