from app.services.citations import (
    extract_citations,
    validate_citations,
)
from app.services.domain import is_bitcoin_question
from app.services.evidence import has_sufficient_evidence


# -------------------------------------------------------------------
# Domain guard
# -------------------------------------------------------------------


def test_utxo_question_is_bitcoin():
    assert is_bitcoin_question(
        "What is a UTXO?"
    )


def test_full_node_question_is_bitcoin():
    assert is_bitcoin_question(
        "What is a full node?"
    )


def test_bitcoin_ethereum_comparison_is_allowed():
    assert is_bitcoin_question(
        "How is Bitcoin proof of work different "
        "from Ethereum staking?"
    )


def test_ethereum_only_question_is_rejected():
    assert not is_bitcoin_question(
        "How does Ethereum staking work?"
    )


def test_unrelated_question_is_rejected():
    assert not is_bitcoin_question(
        "How do I bake a chocolate cake?"
    )


# -------------------------------------------------------------------
# Evidence guard
# -------------------------------------------------------------------


def test_utxo_evidence_is_sufficient():
    docs = [
        {
            "title": "Glossary — Bitcoin",
            "excerpt": (
                "An unspent transaction output (UTXO) "
                "can be spent as an input in a new transaction."
            ),
        }
    ]

    assert has_sufficient_evidence(
        "What is a UTXO?",
        docs,
    )


def test_multiple_terms_have_sufficient_evidence():
    docs = [
        {
            "title": "Bitcoin Mining",
            "excerpt": (
                "Bitcoin mining difficulty adjusts "
                "according to network conditions."
            ),
        }
    ]

    assert has_sufficient_evidence(
        "How does Bitcoin mining difficulty work?",
        docs,
    )


def test_unrelated_semantic_result_is_insufficient():
    docs = [
        {
            "title": "Bitcoin Cryptography",
            "excerpt": (
                "Bitcoin uses cryptographic signatures "
                "and the secp256k1 elliptic curve."
            ),
        }
    ]

    assert not has_sufficient_evidence(
        "What is Bitcoin's position on "
        "post-quantum signature migration?",
        docs,
    )


def test_empty_evidence_is_insufficient():
    assert not has_sufficient_evidence(
        "What is a UTXO?",
        [],
    )


# -------------------------------------------------------------------
# Citation extraction
# -------------------------------------------------------------------


def test_extract_citations():
    answer = (
        "Bitcoin uses UTXOs [1] and "
        "digital signatures [3]."
    )

    assert extract_citations(answer) == [1, 3]


# -------------------------------------------------------------------
# Citation validation
# -------------------------------------------------------------------


def test_valid_citations_are_accepted():
    assert validate_citations(
        "Bitcoin uses UTXOs [1] and signatures [3].",
        4,
    )


def test_out_of_range_citation_is_rejected():
    assert not validate_citations(
        "Bitcoin uses proof of work [7].",
        4,
    )


def test_zero_citation_is_rejected():
    assert not validate_citations(
        "Bitcoin uses proof of work [0].",
        4,
    )


def test_answer_without_citation_is_rejected():
    assert not validate_citations(
        "Bitcoin uses proof of work.",
        4,
    )


def test_citations_without_sources_are_rejected():
    assert not validate_citations(
        "Bitcoin uses proof of work [1].",
        0,
    )