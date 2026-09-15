from datetime import datetime

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request payload for a Bitcoin knowledge question."""

    question: str = Field(
        min_length=2,
        max_length=4000,
        description="Bitcoin-related question in English.",
    )

    max_sources: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Maximum number of sources used to answer the question.",
    )


class SourceCitation(BaseModel):
    """Source used to generate an answer."""

    document_id: int

    chunk_id: int | None = None

    chunk_index: int | None = None

    title: str | None = None

    url: str

    updated_at: datetime | None = None

    rank: float | None = None


class AskResponse(BaseModel):
    """RAG-generated answer with supporting sources."""

    answer: str

    generated: bool

    sources: list[SourceCitation]

    knowledge_updated_at: datetime | None = None


class SearchResult(BaseModel):
    """Single hybrid-search result."""

    document_id: int

    chunk_id: int | None = None

    chunk_index: int | None = None

    title: str | None = None

    url: str

    excerpt: str

    updated_at: datetime | None = None

    rank: float | None = None