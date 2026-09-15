import re


CITATION_PATTERN = re.compile(
    r"\[(\d+)\]"
)


def extract_citations(
    answer: str,
) -> list[int]:
    """
    Extract numeric source citations from an LLM answer.

    Example:
        "Bitcoin uses UTXOs [1] and signatures [3]."

    Returns:
        [1, 3]
    """

    citations = []

    for match in CITATION_PATTERN.findall(answer):
        try:
            citations.append(int(match))
        except ValueError:
            continue

    return citations


def validate_citations(
    answer: str,
    source_count: int,
) -> bool:
    """
    Validate that every citation in the generated answer refers to
    a source that was actually supplied to the LLM.

    Citation numbering starts at 1.
    """

    if source_count <= 0:
        return False

    citations = extract_citations(answer)

    if not citations:
        return False

    return all(
        1 <= citation <= source_count
        for citation in citations
    )