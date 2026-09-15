import asyncio
import hashlib
from sqlalchemy import text
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.embeddings import embed_texts, embeddings_enabled

settings = get_settings()

def chunk_text(value: str, size: int, overlap: int) -> list[str]:
    value = " ".join((value or "").split())
    if not value:
        return []
    chunks, start = [], 0
    while start < len(value):
        end = min(len(value), start + size)
        chunk = value[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(value):
            break
        start = max(start + 1, end - overlap)
    return chunks

def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in values) + "]"

def index_document(db, doc: dict) -> int:
    chunks = chunk_text(doc["clean_text"], settings.chunk_size_chars, settings.chunk_overlap_chars)
    hashes = [hashlib.sha256(c.encode("utf-8")).hexdigest() for c in chunks]
    existing = db.execute(text("SELECT chunk_index, content_hash FROM document_chunks WHERE document_id=:d ORDER BY chunk_index"), {"d": doc["id"]}).mappings().all()
    if len(existing) == len(hashes) and all(existing[i]["content_hash"] == hashes[i] for i in range(len(hashes))):
        return 0
    db.execute(text("DELETE FROM document_chunks WHERE document_id=:d"), {"d": doc["id"]})
    vectors = embed_texts(chunks) if chunks and embeddings_enabled() else [None] * len(chunks)
    for i, (chunk, digest, emb) in enumerate(zip(chunks, hashes, vectors)):
        if emb is None:
            db.execute(text("INSERT INTO document_chunks(document_id,chunk_index,content,content_hash) VALUES(:d,:i,:c,:h)"), {"d": doc["id"], "i": i, "c": chunk, "h": digest})
        else:
            db.execute(text("INSERT INTO document_chunks(document_id,chunk_index,content,content_hash,embedding) VALUES(:d,:i,:c,:h,CAST(:e AS vector))"), {"d": doc["id"], "i": i, "c": chunk, "h": digest, "e": vector_literal(emb)})
    db.commit()
    return len(chunks)

def run_once():
    db = SessionLocal()
    try:
        docs = db.execute(text("SELECT id, clean_text FROM documents ORDER BY updated_at ASC")).mappings().all()
        indexed = 0
        for doc in docs:
            try:
                indexed += index_document(db, doc)
            except Exception as exc:
                db.rollback()
                print(f"[indexer] document {doc['id']}: {type(exc).__name__}: {exc}")
        print(f"[indexer] indexed_chunks={indexed} documents={len(docs)} embeddings={embeddings_enabled()}")
    finally:
        db.close()

async def main():
    while True:
        run_once()
        await asyncio.sleep(settings.index_interval_seconds)

if __name__ == "__main__":
    asyncio.run(main())
