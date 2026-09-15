from app.crawler.relevance import relevance_score

def test_bitcoin_is_relevant():
    assert relevance_score("Bitcoin Core uses UTXOs. Bitcoin Taproot and SegWit are protocol upgrades.") > 0.2

def test_unrelated_is_rejected():
    assert relevance_score("This is a cooking article about bread, tomatoes and olive oil.") == 0.0
