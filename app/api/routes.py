from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.schemas import (
    AskRequest,
    AskResponse,
    SearchResult,
    SourceCitation,
)
from app.services.citations import validate_citations
from app.services.domain import is_bitcoin_question
from app.services.evidence import has_sufficient_evidence
from app.services.llm import (
    LLMDisabled,
    answer_with_context,
)
from app.services.retriever import (
    knowledge_updated_at,
    latest_documents,
    search_documents,
)


router = APIRouter(prefix="/v1")
settings = get_settings()


# -------------------------------------------------------------------
# Health
# -------------------------------------------------------------------

@router.get("/health")
def health(
    db: Session = Depends(get_db),
):
    db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "ok",
    }


# -------------------------------------------------------------------
# Sources
# -------------------------------------------------------------------

@router.get("/sources")
def sources(
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text("""
            SELECT
                id,
                name,
                base_url,
                source_type,
                trust_level,
                enabled,
                last_crawled_at
            FROM sources
            ORDER BY trust_level, name
        """)
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


# -------------------------------------------------------------------
# Latest documents
# -------------------------------------------------------------------

@router.get("/latest")
def latest(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):
    return latest_documents(
        db,
        limit,
    )


# -------------------------------------------------------------------
# Search
# -------------------------------------------------------------------

@router.get(
    "/search",
    response_model=list[SearchResult],
)
def search(
    q: str = Query(
        min_length=2,
        max_length=1000,
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
    ),
    db: Session = Depends(get_db),
):
    docs = search_documents(
        db,
        q,
        limit,
    )

    return [
        SearchResult(
            document_id=doc["id"],
            chunk_id=doc.get("chunk_id"),
            chunk_index=doc.get("chunk_index"),
            title=doc.get("title"),
            url=doc["canonical_url"],
            excerpt=doc.get("excerpt") or "",
            updated_at=doc.get("updated_at"),
            rank=(
                float(doc["rank"])
                if doc.get("rank") is not None
                else None
            ),
        )
        for doc in docs
    ]


# -------------------------------------------------------------------
# Ask
# -------------------------------------------------------------------

@router.post(
    "/ask",
    response_model=AskResponse,
)
async def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
):
    """
    Answer an English Bitcoin question using the local RAG knowledge base.

    Pipeline:
        English question
            -> Bitcoin domain guard
            -> hybrid retrieval
            -> evidence guard
            -> candidate reranking
            -> document deduplication
            -> LLM generation
            -> citation validation
            -> cited answer
    """

    # ---------------------------------------------------------------
    # Bitcoin domain guard
    # ---------------------------------------------------------------

    if not is_bitcoin_question(
        payload.question
    ):
        return AskResponse(
            answer=(
                "This API only answers questions about Bitcoin."
            ),
            generated=False,
            sources=[],
            knowledge_updated_at=knowledge_updated_at(db),
        )

    # ---------------------------------------------------------------
    # Hybrid retrieval
    # ---------------------------------------------------------------

    # Retrieve more chunks than the final number of sources so the
    # reranker and document deduplication stages have enough candidates.
    candidate_limit = max(
        payload.max_sources * 3,
        12,
    )

    docs = search_documents(
        db,
        payload.question,
        candidate_limit,
    )

    # ---------------------------------------------------------------
    # No knowledge found
    # ---------------------------------------------------------------

    if not docs:
        return AskResponse(
            answer=(
                "No sufficiently relevant source was found "
                "in the current Bitcoin knowledge base."
            ),
            generated=False,
            sources=[],
            knowledge_updated_at=knowledge_updated_at(db),
        )

    # ---------------------------------------------------------------
    # Evidence guard
    # ---------------------------------------------------------------

    if not has_sufficient_evidence(
        payload.question,
        docs,
    ):
        return AskResponse(
            answer=(
                "The available Bitcoin knowledge base does not contain "
                "enough evidence to answer this question reliably."
            ),
            generated=False,
            sources=[],
            knowledge_updated_at=knowledge_updated_at(db),
        )

    # ---------------------------------------------------------------
    # Extract meaningful English query terms
    # ---------------------------------------------------------------

    stop_words = {
        "about",
        "after",
        "also",
        "and",
        "are",
        "bitcoin",
        "can",
        "could",
        "does",
        "for",
        "from",
        "have",
        "how",
        "into",
        "its",
        "that",
        "the",
        "their",
        "there",
        "these",
        "this",
        "what",
        "when",
        "where",
        "which",
        "why",
        "with",
        "would",
        "your",
    }

    question_terms = set()

    for word in payload.question.split():
        normalized = word.strip(
            " ?!.,:;()[]{}'\""
        ).lower()

        if (
            len(normalized) >= 3
            and normalized not in stop_words
        ):
            question_terms.add(
                normalized
            )

    # ---------------------------------------------------------------
    # Candidate reranking
    # ---------------------------------------------------------------

    def relevance_score(
        doc: dict,
    ):
        excerpt = (
            doc.get("excerpt")
            or ""
        ).lower()

        title = (
            doc.get("title")
            or ""
        ).lower()

        excerpt_matches = sum(
            1
            for term in question_terms
            if term in excerpt
        )

        title_matches = sum(
            1
            for term in question_terms
            if term in title
        )

        original_rank = float(
            doc.get("rank")
            or 0
        )

        return (
            excerpt_matches,
            title_matches,
            original_rank,
        )

    ranked_docs = sorted(
        docs,
        key=relevance_score,
        reverse=True,
    )

    # ---------------------------------------------------------------
    # Deduplicate by document
    # ---------------------------------------------------------------

    # The retriever works at chunk level, so several chunks from the
    # same document may appear in the candidate set.
    #
    # Keep only the highest-ranked chunk from each document so the
    # final context contains more diverse evidence.
    unique_docs = []
    seen_document_ids = set()

    for doc in ranked_docs:
        document_id = doc["id"]

        if document_id in seen_document_ids:
            continue

        seen_document_ids.add(
            document_id
        )

        unique_docs.append(
            doc
        )

        if len(unique_docs) >= payload.max_sources:
            break

    docs = unique_docs

    # ---------------------------------------------------------------
    # Citations
    # ---------------------------------------------------------------

    citations = [
        SourceCitation(
            document_id=doc["id"],
            chunk_id=doc.get("chunk_id"),
            chunk_index=doc.get("chunk_index"),
            title=doc.get("title"),
            url=doc["canonical_url"],
            updated_at=doc.get("updated_at"),
            rank=(
                float(doc["rank"])
                if doc.get("rank") is not None
                else None
            ),
        )
        for doc in docs
    ]

    # ---------------------------------------------------------------
    # LLM generation
    # ---------------------------------------------------------------

    try:
        answer = await answer_with_context(
            payload.question,
            docs,
        )

        generated = True

    except LLMDisabled:
        answer = (
            "The LLM provider is not configured. "
            "Retrieval is working and the relevant "
            "sources are returned."
        )

        generated = False

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "LLM provider error: "
                f"{type(exc).__name__}"
            ),
        ) from exc

    # ---------------------------------------------------------------
    # Citation validation
    # ---------------------------------------------------------------

    # Validate citations only when an answer was actually generated by
    # the LLM. Retrieval-only responses do not require inline citations.
    if generated and not validate_citations(
        answer,
        len(docs),
    ):
        return AskResponse(
            answer=(
                "The generated answer could not be reliably linked "
                "to the supplied Bitcoin sources."
            ),
            generated=False,
            sources=[],
            knowledge_updated_at=knowledge_updated_at(db),
        )

    # ---------------------------------------------------------------
    # Response
    # ---------------------------------------------------------------

    return AskResponse(
        answer=answer,
        generated=generated,
        sources=citations,
        knowledge_updated_at=knowledge_updated_at(db),
    )


# -------------------------------------------------------------------
# Model information
# -------------------------------------------------------------------

@router.get("/model/info")
def model_info(
    db: Session = Depends(get_db),
):
    return {
        "name": "bitcoin-intelligence-v2.1",
        "language": "en",
        "rag": True,
        "retrieval": "hybrid-pgvector-full-text",
        "chunk_citations": True,
        "domain_guard": True,
        "evidence_guard": True,
        "citation_validation": True,
        "vector_extension_ready": True,
        "llm_configured": bool(
            settings.llm_base_url
            and settings.llm_model
        ),
        "knowledge_updated_at": knowledge_updated_at(db),
    }