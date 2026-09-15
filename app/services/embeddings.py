import httpx
from app.core.config import get_settings

settings = get_settings()

class EmbeddingsDisabled(RuntimeError):
    pass

def _base_url() -> str:
    return (settings.embedding_base_url or settings.llm_base_url).rstrip("/")

def embeddings_enabled() -> bool:
    return bool(_base_url() and settings.embedding_model)

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not embeddings_enabled():
        raise EmbeddingsDisabled("Embedding provider is not configured")
    headers = {"Content-Type": "application/json"}
    key = settings.embedding_api_key or settings.llm_api_key
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": settings.embedding_model, "input": texts}
    with httpx.Client(timeout=settings.embedding_timeout_seconds) as client:
        r = client.post(_base_url() + "/embeddings", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    return [row["embedding"] for row in sorted(data["data"], key=lambda x: x["index"])]

def embed_query(text: str) -> list[float] | None:
    if not embeddings_enabled():
        return None
    return embed_texts([text])[0]
