"""检索层（RAG 召回）测试"""

from backend.services.retrieval import retrieve_laws


def _top_names(query, k=5):
    return [f"{r['law_name']} {r['article']}" for r in retrieve_laws(query, k=k)]


def test_retrieve_fake_goods():
    names = _top_names("我在拼多多买耳机收到是假货要求退一赔三")
    assert any("消费者权益保护法" in n and "55" in n for n in names), names


def test_retrieve_food_safety():
    names = _top_names("外卖吃到蟑螂要求退一赔十")
    assert any("食品安全法" in n and "148" in n for n in names), names


def test_retrieve_prepaid_card():
    names = _top_names("健身房办卡跑路关门不退费")
    assert any("预付卡" in n or "民法典" in n for n in names), names


def test_retrieve_false_ad():
    names = _top_names("直播间夸大宣传护肤品没效果")
    assert any("广告法" in n for n in names), names


def test_retrieve_logistics():
    names = _top_names("快递丢件没收到要求赔偿")
    assert any("快递" in n for n in names), names


def test_retrieve_price_fraud():
    names = _top_names("先涨价后降价价格欺诈")
    assert any("价格" in n for n in names), names


def test_retrieve_returns_sorted_scores():
    results = retrieve_laws("买的东西坏了不退款", k=5)
    assert results
    scores = [r["_score"] for r in results]
    assert scores == sorted(scores, reverse=True), "应按相关度降序"


def test_retrieve_kb_expanded():
    """知识库应已扩充（>=60 条）"""
    from backend.database import get_legal_knowledge
    assert len(get_legal_knowledge()) >= 60, "知识库未扩充"
