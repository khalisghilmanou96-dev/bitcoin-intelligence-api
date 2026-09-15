from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embeddings import embed_query


def _vec(values: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in values) + "]"


def search_documents(
    db: Session,
    query: str,
    limit: int = 8,
) -> list[dict]:
    """
    Hybrid RAG retrieval:
    - semantic/vector search
    - lexical/full-text search
    - fusion of both result sets
    - returns the exact chunk that matched
    """

    qvec = None

    try:
        qvec = embed_query(query)
    except Exception as exc:
        print(f"[retriever] embedding unavailable: {exc}")
        qvec = None

    # ---------------------------------------------------------
    # RAG V2: HYBRID CHUNK RETRIEVAL
    # ---------------------------------------------------------
    if qvec:
        sql = text("""
            WITH vector_candidates AS (
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    1 - (
                        c.embedding <=> CAST(:e AS vector)
                    ) AS vector_rank
                FROM document_chunks c
                WHERE c.embedding IS NOT NULL
                ORDER BY
                    c.embedding <=> CAST(:e AS vector)
                LIMIT :candidate_limit
            ),

            text_candidates AS (
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    ts_rank_cd(
                        to_tsvector(
                            'simple',
                            c.content
                        ),
                        websearch_to_tsquery(
                            'simple',
                            :q
                        )
                    ) AS text_rank
                FROM document_chunks c
                WHERE
                    to_tsvector(
                        'simple',
                        c.content
                    )
                    @@ websearch_to_tsquery(
                        'simple',
                        :q
                    )
                ORDER BY text_rank DESC
                LIMIT :candidate_limit
            ),

            combined AS (
                SELECT
                    COALESCE(
                        v.chunk_id,
                        t.chunk_id
                    ) AS chunk_id,

                    COALESCE(
                        v.document_id,
                        t.document_id
                    ) AS document_id,

                    COALESCE(
                        v.vector_rank,
                        0
                    ) AS vector_rank,

                    COALESCE(
                        t.text_rank,
                        0
                    ) AS text_rank

                FROM vector_candidates v

                FULL OUTER JOIN text_candidates t
                    ON v.chunk_id = t.chunk_id
            )

            SELECT
                d.id,
                d.title,
                d.canonical_url,
                d.updated_at,
                d.clean_text,

                c.chunk_id,

                dc.chunk_index,

                dc.content AS excerpt,

                c.vector_rank,

                c.text_rank,

                (
                    0.60 * GREATEST(
                        c.vector_rank,
                        0
                    )
                    +
                    0.40 * LEAST(
                        c.text_rank * 5,
                        1
                    )
                ) AS rank

            FROM combined c

            JOIN document_chunks dc
                ON dc.id = c.chunk_id

            JOIN documents d
                ON d.id = c.document_id

            ORDER BY rank DESC

            LIMIT :limit
        """)

        rows = db.execute(
            sql,
            {
                "q": query,
                "e": _vec(qvec),
                "limit": limit,
                "candidate_limit": max(
                    limit * 12,
                    60,
                ),
            },
        ).mappings().all()

        if rows:
            return [
                dict(row)
                for row in rows
            ]

    # ---------------------------------------------------------
    # FALLBACK 1: CHUNK FULL-TEXT SEARCH
    # ---------------------------------------------------------
    sql = text("""
        SELECT
            d.id,
            d.title,
            d.canonical_url,
            d.updated_at,
            d.clean_text,

            c.id AS chunk_id,

            c.chunk_index,

            c.content AS excerpt,

            ts_rank_cd(
                to_tsvector(
                    'simple',
                    c.content
                ),
                websearch_to_tsquery(
                    'simple',
                    :q
                )
            ) AS rank

        FROM document_chunks c

        JOIN documents d
            ON d.id = c.document_id

        WHERE
            to_tsvector(
                'simple',
                c.content
            )
            @@ websearch_to_tsquery(
                'simple',
                :q
            )

        ORDER BY
            rank DESC,
            d.updated_at DESC

        LIMIT :limit
    """)

    rows = db.execute(
        sql,
        {
            "q": query,
            "limit": limit,
        },
    ).mappings().all()

    if rows:
        return [
            dict(row)
            for row in rows
        ]

    # ---------------------------------------------------------
    # FALLBACK 2: KEYWORD SEARCH INSIDE CHUNKS
    # ---------------------------------------------------------
    words = [
        word.strip(
            " ?!.,:;()[]{}'\""
        ).lower()
        for word in query.split()
    ]

    stop = {
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

    words = [
        word
        for word in words
        if len(word) >= 4
        and word not in stop
    ][:6]

    if not words:
        return []

    params = {
        "limit": limit,
    }

    conditions = []

    for index, word in enumerate(words):
        params[f"w{index}"] = f"%{word}%"

        conditions.append(
            f"(lower(d.title) LIKE :w{index} "
            f"OR lower(c.content) LIKE :w{index})"
        )

    fallback = text(f"""
        SELECT
            d.id,
            d.title,
            d.canonical_url,
            d.updated_at,
            d.clean_text,

            c.id AS chunk_id,

            c.chunk_index,

            c.content AS excerpt,

            0.10 AS rank

        FROM document_chunks c

        JOIN documents d
            ON d.id = c.document_id

        WHERE {' OR '.join(conditions)}

        ORDER BY d.updated_at DESC

        LIMIT :limit
    """)

    rows = db.execute(
        fallback,
        params,
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def latest_documents(
    db: Session,
    limit: int = 20,
) -> list[dict]:
    """
    Return the most recently updated documents.
    """

    sql = text("""
        SELECT
            id,
            title,
            canonical_url,
            updated_at,
            left(
                clean_text,
                400
            ) AS excerpt

        FROM documents

        ORDER BY updated_at DESC

        LIMIT :limit
    """)

    return [
        dict(row)
        for row in db.execute(
            sql,
            {
                "limit": limit,
            },
        ).mappings().all()
    ]


def knowledge_updated_at(
    db: Session,
):
    """
    Return the timestamp of the most recently updated document.
    """

    return db.execute(
        text(
            "SELECT max(updated_at) "
            "FROM documents"
        )
    ).scalar()