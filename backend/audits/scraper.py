import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def discover_urls_from_sitemap(homepage: str) -> list:
    """Fetch sitemap.xml and return up to 4 same-domain URLs (homepage excluded)."""
    try:
        resp = requests.get(f"{homepage.rstrip('/')}/sitemap.xml", timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'lxml-xml')
        root = urlparse(homepage)
        results = []
        for loc in soup.find_all('loc'):
            url = loc.text.strip()
            parsed = urlparse(url)
            if parsed.netloc != root.netloc:
                continue
            if url.rstrip('/') == homepage.rstrip('/'):
                continue
            results.append(url)
            if len(results) >= 4:
                break
        return results
    except Exception as e:
        logger.warning(f"Sitemap fetch failed for {homepage}: {e}")
        return []


def extract_same_domain_links(html: str, base_url: str, limit: int = 4) -> list:
    """Return unique same-domain absolute links found in html, up to limit."""
    root = urlparse(base_url)
    soup = BeautifulSoup(html, 'lxml')
    seen = set()
    links = []
    for a in soup.find_all('a', href=True):
        href = urljoin(base_url, a['href'])
        parsed = urlparse(href)
        if parsed.netloc == root.netloc and href not in seen:
            seen.add(href)
            links.append(href)
            if len(links) >= limit:
                break
    return links


def extract_page_data(html: str, url: str) -> dict:
    """Parse html and return structured page data dict. No network I/O."""
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup(['script', 'style']):
        tag.decompose()

    root = urlparse(url)
    meta_desc_tag = soup.find('meta', attrs={'name': 'description'})

    seen_links = set()
    internal_links = []
    for a in soup.find_all('a', href=True):
        href = urljoin(url, a['href'])
        if urlparse(href).netloc == root.netloc and href not in seen_links:
            seen_links.add(href)
            internal_links.append(href)

    return {
        'meta_title': soup.title.get_text(strip=True) if soup.title else '',
        'meta_description': meta_desc_tag.get('content', '') if meta_desc_tag else '',
        'h1_tags': [h.get_text(strip=True) for h in soup.find_all('h1')],
        'h2_tags': [h.get_text(strip=True) for h in soup.find_all('h2')],
        'image_alts': [img.get('alt', '') for img in soup.find_all('img')],
        'extracted_text': ' '.join(soup.get_text(separator=' ').split()),
        'internal_links': internal_links,
    }
