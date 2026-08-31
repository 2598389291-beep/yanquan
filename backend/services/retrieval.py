"""轻量检索层（RAG 召回）

基于字符 n-gram 余弦相似度 + 标签加权，从法律知识库中召回最相关的候选条文，
再交给 LLM 精排引用。零外部依赖，离线可用，检索结果全部来自本地知识库，
保证可溯源、不幻觉。
"""

import json
import re
from collections import Counter

from ..database import get_legal_knowledge


def _grams(text: str, n: int) -> list:
    """按字符生成 n-gram（中文场景比分词更稳）"""
    text = re.sub(r"\s+", "", text or "")
    return [text[i:i + n] for i in range(max(len(text) - n + 1, 0))]


def _vector(text: str) -> Counter:
    counter: Counter = Counter()
    for n in (2, 3):
        for g in _grams(text, n):
            counter[g] += 1
    return counter


def _cosine(a: Counter, b: Counter) -> float:
    inter = set(a) & set(b)
    if not inter:
        return 0.0
    num = sum(a[k] * b[k] for k in inter)
    da = sum(v * v for v in a.values()) ** 0.5
    db = sum(v * v for v in b.values()) ** 0.5
    return num / (da * db) if da and db else 0.0


def retrieve_laws(query: str, k: int = 8, tag_weight: float = 0.25) -> list[dict]:
    """按相关度召回法律条文，返回 [{law_name, article, content, tags, _score}]"""
    if not query:
        return []
    qv = _vector(query)
    laws = get_legal_knowledge()
    scored = []
    for law in laws:
        text = f"{law['law_name']} {law['article']} {law['content']}"
        tags = law["tags"] if isinstance(law["tags"], list) else json.loads(law["tags"])
        sim = _cosine(qv, _vector(text))
        tag_hits = sum(1 for t in tags if t and t in query)
        score = sim + tag_weight * tag_hits
        scored.append((score, law))
    scored.sort(key=lambda x: -x[0])
    return [{**dict(law), "_score": round(score, 4)} for score, law in scored[:k]]
