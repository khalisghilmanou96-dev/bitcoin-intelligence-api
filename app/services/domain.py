import re


# Terms that strongly indicate a Bitcoin-related question.
BITCOIN_TERMS = {
    "bitcoin",
    "btc",
    "satoshi",
    "satoshis",
    "utxo",
    "utxos",
    "lightning",
    "taproot",
    "segwit",
    "mempool",
    "mining",
    "miner",
    "miners",
    "hashrate",
    "halving",
    "block",
    "blocks",
    "blockchain",
    "transaction",
    "transactions",
    "wallet",
    "wallets",
    "address",
    "addresses",
    "private key",
    "private keys",
    "public key",
    "public keys",
    "seed phrase",
    "recovery phrase",
    "full node",
    "node",
    "nodes",
    "proof of work",
    "proof-of-work",
    "difficulty",
    "block reward",
    "block subsidy",
    "coinbase transaction",
    "script",
    "scriptpubkey",
    "scriptSig",
    "witness",
    "bech32",
    "bech32m",
    "p2pkh",
    "p2sh",
    "p2wpkh",
    "p2wsh",
    "p2tr",
    "bip",
    "bips",
    "bitcoin core",
}


# Other cryptocurrency ecosystems that should not be treated as
# Bitcoin questions unless Bitcoin is explicitly part of the query.
NON_BITCOIN_CRYPTO_TERMS = {
    "ethereum",
    "ether",
    "eth",
    "solana",
    "cardano",
    "ripple",
    "xrp",
    "dogecoin",
    "litecoin",
    "monero",
    "avalanche",
    "polkadot",
    "polygon",
    "bnb",
    "binance",
    "tron",
    "stablecoin",
    "stablecoins",
    "usdt",
    "usdc",
    "staking",
    "proof of stake",
    "proof-of-stake",
    "smart contract",
    "smart contracts",
    "erc20",
    "erc-20",
    "nft",
    "nfts",
}


def _normalize(text: str) -> str:
    """Normalize user text for lightweight domain classification."""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s\-]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _contains_term(text: str, term: str) -> bool:
    """
    Match complete words or phrases instead of arbitrary substrings.

    Example:
        "eth" should match "eth"
        but should not match "method".
    """

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(term)
        + r"(?![a-z0-9])"
    )

    return re.search(
        pattern,
        text,
    ) is not None


def is_bitcoin_question(question: str) -> bool:
    """
    Return True when the question appears to belong to the Bitcoin domain.

    This is intentionally a conservative first-stage guard, not a
    semantic replacement for the RAG retriever.
    """

    normalized = _normalize(question)

    if not normalized:
        return False

    bitcoin_matches = {
        term
        for term in BITCOIN_TERMS
        if _contains_term(
            normalized,
            term,
        )
    }

    non_bitcoin_matches = {
        term
        for term in NON_BITCOIN_CRYPTO_TERMS
        if _contains_term(
            normalized,
            term,
        )
    }

    # Explicit Bitcoin terminology takes precedence.
    #
    # This allows legitimate comparative questions such as:
    #
    # "How is Bitcoin proof of work different from Ethereum staking?"
    if bitcoin_matches:
        return True

    # Explicit references to another cryptocurrency ecosystem without
    # any Bitcoin signal are outside the API's scope.
    if non_bitcoin_matches:
        return False

    # No recognizable Bitcoin signal.
    return False