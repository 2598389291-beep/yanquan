"""法律溯源工具：为匹配的法律条文生成官方来源链接"""

from urllib.parse import quote


def law_source_url(law_name: str) -> str:
    """生成国家法律法规数据库（flk.npc.gov.cn）的官方检索链接"""
    return f"https://flk.npc.gov.cn/search.html?keyword={quote(law_name)}"


def build_legal_details(matched_laws: list) -> list:
    """把匹配的法律条文转为带全文与官方来源的结构化列表"""
    details = []
    for law in matched_laws:
        details.append({
            "law_name": law.get("law_name", ""),
            "article": law.get("article", ""),
            "content": law.get("content", ""),
            "source_url": law_source_url(law.get("law_name", "")),
        })
    return details
