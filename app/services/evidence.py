import re


QUESTION_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "bitcoin",
    "can",
    "could",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "the",
    "their",
    "to",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
    "work",
    "works",
    "would",
}


def _tokens(text: str) -> set[str]:
    """
    Extract normalized English terms from text.
    """

    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            text.lower(),
        )
        if len(token) >= 3
    }


def question_terms(question: str) -> set[str]:
    """
    Return meaningful lexical terms from a Bitcoin question.
    """

    return {
        token
        for token in _tokens(question)
        if token not in QUESTION_STOP_WORDS
    }


def has_sufficient_evidence(
    question: str,
    docs: list[dict],
) -> bool:
    """
    Determine whether retrieved chunks contain enough direct lexical
    evidence to justify sending the question to the LLM.

    This complements semantic retrieval. Vector similarity alone is
    not considered proof that the knowledge base answers the question.
    """

    if not docs:
        return False

    terms = question_terms(question)

    if not terms:
        return False

    best_overlap = 0
    total_matches = set()

    for doc in docs:
        excerpt = (
            doc.get("excerpt")
            or ""
        )

        title = (
            doc.get("title")
            or ""
        )

        document_terms = _tokens(
            f"{title} {excerpt}"
        )

        matches = terms & document_terms

        best_overlap = max(
            best_overlap,
            len(matches),
        )

        total_matches.update(matches)

    # A single meaningful concept is sufficient for short questions
    # such as:
    #
    # "What is a UTXO?"
    #
    # For questions containing multiple meaningful concepts, require
    # evidence for at least two of them somewhere in the retrieved
    # context.
    if len(terms) == 1:
        return best_overlap >= 1

    return (
        best_overlap >= 2
        or len(total_matches) >= 2
    )