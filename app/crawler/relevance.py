import re

KEYWORDS = {
    "bitcoin": 8, "bitcoin core": 8, "btc": 2, "satoshi": 3, "bip": 4,
    "utxo": 5, "taproot": 5, "segwit": 5, "mempool": 4,
    "lightning network": 4, "psbt": 5, "bitcoin script": 6,
    "blockchain": 1, "proof of work": 2,
}

def relevance_score(text: str) -> float:
    sample = text[:150000].lower()
    score = 0
    for keyword, weight in KEYWORDS.items():
        count = len(re.findall(re.escape(keyword), sample))
        score += min(count, 10) * weight
    explicit = "bitcoin" in sample
    highly_specific = any(k in sample for k in ("utxo", "taproot", "segwit", "psbt", "bitcoin script"))
    if not explicit and not highly_specific:
        return 0.0
    return min(score / 45.0, 1.0)
