import asyncio
import hashlib
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
import yaml
from bs4 import BeautifulSoup
import trafilatura
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.crawler.relevance import relevance_score

settings = get_settings()
SEEDS = Path("config/seed_sources.yaml")

def normalize_url(url: str) -> str:
    clean, _ = urldefrag(url)
    return clean.strip()

def same_domain(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()

def extract_document(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    clean = trafilatura.extract(html, url=url, include_links=False, include_images=False, favor_precision=True) or soup.get_text("\n", strip=True)
    clean = clean.strip()
    digest = hashlib.sha256(clean.encode("utf-8", errors="ignore")).hexdigest()
    links = []
    for a in soup.find_all("a", href=True):
        candidate = normalize_url(urljoin(url, a["href"]))
        if urlparse(candidate).scheme in {"http", "https"}:
            links.append(candidate)
    return {"title": title[:1000], "text": clean, "hash": digest, "links": list(dict.fromkeys(links))}

def load_seeds() -> list[dict]:
    return yaml.safe_load(SEEDS.read_text(encoding="utf-8")).get("sources", [])

def ensure_source(db, cfg: dict) -> int:
    row = db.execute(text("SELECT id FROM sources WHERE base_url=:u"), {"u": cfg["url"]}).first()
    if row:
        return row[0]
    return db.execute(text("INSERT INTO sources(name,base_url,trust_level) VALUES(:n,:u,:t) RETURNING id"), {"n": cfg["name"], "u": cfg["url"], "t": cfg.get("trust_level", "discovered")}).scalar_one()

def upsert_document(db, source_id: int, url: str, title: str, clean_text: str, content_hash: str, score: float) -> bool:
    row = db.execute(text("SELECT id, content_hash FROM documents WHERE canonical_url=:u"), {"u": url}).mappings().first()
    now = datetime.now(timezone.utc)
    if not row:
        doc_id = db.execute(text("""
            INSERT INTO documents(source_id,canonical_url,title,content_hash,clean_text,metadata,first_seen_at,last_seen_at,updated_at)
            VALUES(:s,:u,:t,:h,:c,jsonb_build_object('relevance_score',:r),:n,:n,:n) RETURNING id
        """), {"s": source_id, "u": url, "t": title, "h": content_hash, "c": clean_text, "r": score, "n": now}).scalar_one()
        db.execute(text("INSERT INTO document_versions(document_id,content_hash,clean_text,metadata) VALUES(:d,:h,:c,jsonb_build_object('relevance_score',:r))"), {"d": doc_id, "h": content_hash, "c": clean_text, "r": score})
        db.commit()
        return True
    db.execute(text("UPDATE documents SET last_seen_at=:n WHERE id=:d"), {"n": now, "d": row["id"]})
    if row["content_hash"] == content_hash:
        db.commit()
        return False
    db.execute(text("UPDATE documents SET title=:t,content_hash=:h,clean_text=:c,metadata=jsonb_build_object('relevance_score',:r),updated_at=:n,last_seen_at=:n WHERE id=:d"), {"t": title, "h": content_hash, "c": clean_text, "r": score, "n": now, "d": row["id"]})
    db.execute(text("INSERT INTO document_versions(document_id,content_hash,clean_text,metadata) VALUES(:d,:h,:c,jsonb_build_object('relevance_score',:r)) ON CONFLICT DO NOTHING"), {"d": row["id"], "h": content_hash, "c": clean_text, "r": score})
    db.commit()
    return True

async def crawl_source(cfg: dict):
    db = SessionLocal()
    source_id = ensure_source(db, cfg)
    run_id = db.execute(text("INSERT INTO crawl_runs(source_id,status) VALUES(:s,'running') RETURNING id"), {"s": source_id}).scalar_one()
    db.commit()
    max_depth = int(cfg.get("max_depth", 0))
    queue = deque([(normalize_url(cfg["url"]), 0)])
    seen, fetched, changed, errors = set(), 0, 0, 0
    try:
        async with httpx.AsyncClient(timeout=settings.crawl_request_timeout_seconds, follow_redirects=True, headers={"User-Agent": settings.crawl_user_agent}) as client:
            while queue and fetched < settings.crawl_max_pages_per_source:
                url, depth = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                try:
                    response = await client.get(url)
                    ctype = response.headers.get("content-type", "")
                    if response.status_code >= 400 or "text/html" not in ctype:
                        continue
                    fetched += 1
                    doc = extract_document(response.text, str(response.url))
                    if len(doc["text"]) < 150:
                        continue
                    score = relevance_score(doc["text"])
                    if score < 0.20:
                        continue
                    changed += int(upsert_document(db, source_id, normalize_url(str(response.url)), doc["title"], doc["text"], doc["hash"], score))
                    if depth < max_depth:
                        for link in doc["links"]:
                            if same_domain(cfg["url"], link) and link not in seen:
                                queue.append((link, depth + 1))
                except Exception as exc:
                    errors += 1
                    print(f"[crawler] {url}: {type(exc).__name__}: {exc}")
        now = datetime.now(timezone.utc)
        db.execute(text("UPDATE sources SET last_crawled_at=:n WHERE id=:s"), {"n": now, "s": source_id})
        db.execute(text("UPDATE crawl_runs SET status='completed',finished_at=:n,fetched_count=:f,changed_count=:c,error_count=:e WHERE id=:r"), {"n": now, "f": fetched, "c": changed, "e": errors, "r": run_id})
        db.commit()
    except Exception as exc:
        db.execute(text("UPDATE crawl_runs SET status='failed',finished_at=:n,error_count=:e,notes=:m WHERE id=:r"), {"n": datetime.now(timezone.utc), "e": errors+1, "m": f"{type(exc).__name__}: {exc}"[:2000], "r": run_id})
        db.commit()
        raise
    finally:
        db.close()

async def crawl_once():
    for cfg in load_seeds():
        try:
            await crawl_source(cfg)
        except Exception as exc:
            print(f"[crawler] source failed: {cfg.get('name')}: {exc}")

async def main():
    while True:
        print(f"[crawler] pass started at {datetime.now(timezone.utc).isoformat()}")
        await crawl_once()
        print(f"[crawler] sleeping {settings.crawl_interval_seconds}s")
        await asyncio.sleep(settings.crawl_interval_seconds)

if __name__ == "__main__":
    asyncio.run(main())
