import hashlib
from urllib.parse import urljoin, urlparse, urldefrag
from bs4 import BeautifulSoup
import trafilatura

def normalize_url(url: str) -> str:
    clean, _ = urldefrag(url)
    return clean.strip()

def same_domain(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()

def extract_document(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    clean = trafilatura.extract(html, url=url, include_links=False, include_images=False, favor_precision=True)
    if not clean:
        clean = soup.get_text("\n", strip=True)
    clean = clean.strip()
    digest = hashlib.sha256(clean.encode("utf-8", errors="ignore")).hexdigest()
    links = []
    for a in soup.find_all("a", href=True):
        candidate = normalize_url(urljoin(url, a["href"]))
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"}:
            links.append(candidate)
    return {"title": title[:1000], "text": clean, "hash": digest, "links": list(dict.fromkeys(links))}
