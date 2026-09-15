import time

import httpx

from app.core.config import get_settings


settings = get_settings()


class LLMDisabled(RuntimeError):
    """Raised when no LLM provider is configured."""

    pass


async def answer_with_context(
    question: str,
    docs: list[dict],
) -> str:
    """
    Generate an English Bitcoin answer grounded in retrieved chunks.
    """

    if not (
        settings.llm_base_url
        and settings.llm_model
    ):
        raise LLMDisabled(
            "LLM provider is not configured"
        )

    # ---------------------------------------------------------------
    # Build RAG context
    # ---------------------------------------------------------------

    sources = []

    for index, doc in enumerate(docs, 1):
        # Prefer the exact chunk selected by the retriever.
        content = (
            doc.get("excerpt")
            or doc.get("clean_text")
            or ""
        )[:1800]

        sources.append(
            f"[SOURCE {index}]\n"
            f"Document ID: {doc.get('id')}\n"
            f"Chunk ID: {doc.get('chunk_id')}\n"
            f"Chunk Index: {doc.get('chunk_index')}\n"
            f"Title: {doc.get('title')}\n"
            f"URL: {doc.get('canonical_url')}\n"
            f"Content:\n{content}"
        )

    context = "\n\n".join(sources)

    # ---------------------------------------------------------------
    # System prompt
    # ---------------------------------------------------------------

    system_prompt = (
        "You are Bitcoin Intelligence API, a technical knowledge "
        "assistant specialized exclusively in Bitcoin. "
        "\n\n"
        "Answer in English. "
        "Use the supplied sources as the primary evidence for your answer. "
        "Base factual claims on the supplied source excerpts. "
        "Do not invent facts that are unsupported by the sources. "
        "Do not claim that information is missing when it is present "
        "in the supplied excerpts. "
        "\n\n"
        "If the supplied sources do not contain enough evidence to answer "
        "the question reliably, clearly say that the available knowledge "
        "base does not provide enough information. "
        "\n\n"
        "Do not confuse Bitcoin with unrelated cryptocurrencies, tokens, "
        "or blockchain projects. "
        "\n\n"
        "Cite supporting sources using [1], [2], [3], etc. "
        "Only cite source numbers that were actually supplied. "
        "Keep the answer concise, technically accurate, and complete."
    )

    user_prompt = (
        f"QUESTION:\n{question}\n\n"
        f"SOURCES:\n{context}"
    )

    # ---------------------------------------------------------------
    # Ollama endpoint
    # ---------------------------------------------------------------

    # Convert:
    #
    # http://host.docker.internal:11434/v1
    #
    # to:
    #
    # http://host.docker.internal:11434/api/chat

    base_url = settings.llm_base_url.rstrip("/")

    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    url = f"{base_url}/api/chat"

    # ---------------------------------------------------------------
    # Ollama request
    # ---------------------------------------------------------------

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],

        # Qwen3 reasoning is disabled for this RAG API.
        "think": False,

        # Return one complete response.
        "stream": False,

        "options": {
            "temperature": 0.1,
            "num_predict": 350,
        },
    }

    # ---------------------------------------------------------------
    # Generate answer and measure Ollama latency
    # ---------------------------------------------------------------

    start_time = time.perf_counter()

    async with httpx.AsyncClient(
        timeout=settings.llm_timeout_seconds
    ) as client:
        response = await client.post(
            url,
            json=payload,
        )

        response.raise_for_status()
        data = response.json()

    elapsed = time.perf_counter() - start_time

    print(
        f"[LLM] Ollama request completed in "
        f"{elapsed:.2f} seconds",
        flush=True,
    )

    # Ollama also exposes internal timing information.
    total_duration = data.get("total_duration")
    prompt_eval_duration = data.get("prompt_eval_duration")
    eval_duration = data.get("eval_duration")
    prompt_eval_count = data.get("prompt_eval_count")
    eval_count = data.get("eval_count")

    if total_duration is not None:
        print(
            "[LLM] "
            f"total={total_duration / 1_000_000_000:.2f}s "
            f"prompt_eval="
            f"{(prompt_eval_duration or 0) / 1_000_000_000:.2f}s "
            f"generation="
            f"{(eval_duration or 0) / 1_000_000_000:.2f}s "
            f"prompt_tokens={prompt_eval_count} "
            f"generated_tokens={eval_count}",
            flush=True,
        )

    # ---------------------------------------------------------------
    # Extract generated answer
    # ---------------------------------------------------------------

    message = data.get("message") or {}
    content = message.get("content")

    if not content:
        raise RuntimeError(
            "LLM provider returned an empty response"
        )

    return content.strip()