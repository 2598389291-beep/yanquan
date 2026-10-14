"""SQLite 数据库管理（WAL 模式 + 索引 + 法律知识库种子数据）"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import settings

# 允许测试通过直接覆盖 DB_PATH
# 每位用户免费生成投诉信的次数上限
FREE_GENERATION_LIMIT = 10
DB_PATH = settings.database_url.replace("sqlite:///", "", 1)
if DB_PATH == ":memory:":
    _db_file = ":memory:"
else:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表（幂等）"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            email TEXT UNIQUE,
            openid TEXT UNIQUE,
            nickname TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            password_hash TEXT DEFAULT '',
            token TEXT,
            token_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS legal_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            law_name TEXT NOT NULL,
            article TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default_user',
            raw_text TEXT NOT NULL,
            complaint_letter TEXT NOT NULL,
            legal_basis TEXT DEFAULT '[]',
            action_path TEXT DEFAULT '[]',
            category TEXT DEFAULT '',
            order_info TEXT DEFAULT '{}',
            status TEXT DEFAULT 'generated',
            evidence TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_complaints_user_created
            ON complaints(user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL DEFAULT 0,
            user_id TEXT NOT NULL DEFAULT '',
            rating TEXT NOT NULL DEFAULT 'helpful',
            comment TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS usage_stats (
            user_id TEXT PRIMARY KEY,
            used_count INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        );
    """)

    # 老库迁移：补充 evidence 列
    _migrate(conn)

    _seed_legal_knowledge(cursor)
    conn.commit()
    conn.close()


def _migrate(conn: sqlite3.Connection):
    """对已存在的旧数据库补充新增列（幂等）"""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(complaints)").fetchall()]
    if "evidence" not in cols:
        conn.execute("ALTER TABLE complaints ADD COLUMN evidence TEXT DEFAULT '[]'")

    # users 表升级：新增 email / password_hash，phone 放开唯一约束（微信/邮箱用户可无手机号）
    user_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "email" not in user_cols:
        # 注意：必须用 executescript —— sqlite3 的 execute 一次只能执行一条语句，
        # 旧库触发这条迁移分支时若用 execute 会直接抛错、导致服务启动失败。
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                email TEXT UNIQUE,
                openid TEXT UNIQUE,
                nickname TEXT DEFAULT '',
                avatar TEXT DEFAULT '',
                password_hash TEXT DEFAULT '',
                token TEXT,
                token_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO users_new (id, phone, openid, nickname, avatar, token, token_expires_at, created_at)
                SELECT id, phone, openid, nickname, avatar, token, token_expires_at, created_at FROM users;
            DROP TABLE users;
            ALTER TABLE users_new RENAME TO users;
        """)
        conn.commit()


def _seed_legal_knowledge(cursor):
    """预置法律条文（覆盖消费者权益全场景，来自公开法律法规）

    按「法律名称 + 条号」补齐缺失条文，而不是"表非空就跳过"：
    否则知识库后续扩充（例如 21 条 → 108 条）时，老库永远拿不到新增条文。
    """
    from .services.law_seed import LAW_SEED

    cursor.execute("SELECT law_name, article FROM legal_knowledge")
    existing = {(row[0], row[1]) for row in cursor.fetchall()}

    added = 0
    for law_name, article, content, tags in LAW_SEED:
        if (law_name, article) in existing:
            continue
        tag_list = json.dumps([t.strip() for t in tags.split(",") if t.strip()], ensure_ascii=False)
        cursor.execute(
            "INSERT INTO legal_knowledge (law_name, article, content, tags) VALUES (?, ?, ?, ?)",
            (law_name, article, content, tag_list),
        )
        added += 1
    if added:
        import logging
        logging.getLogger(__name__).info("法律知识库补齐 %s 条（现共 %s 条）", added, len(existing) + added)


def get_legal_knowledge(tags: Optional[list] = None) -> list:
    """获取法律知识库（可按标签过滤）"""
    conn = get_connection()
    cursor = conn.cursor()
    if tags:
        cursor.execute("SELECT * FROM legal_knowledge")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            row_tags = json.loads(row["tags"])
            if any(t in row_tags for t in tags):
                result.append(dict(row))
        conn.close()
        return result
    cursor.execute("SELECT * FROM legal_knowledge")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- 投诉记录 ----------

# ---------- 免费生成次数 ----------

def get_usage(user_id: str) -> int:
    """返回用户已使用的免费生成次数"""
    conn = get_connection()
    row = conn.execute("SELECT used_count FROM usage_stats WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["used_count"] if row else 0

def increment_usage(user_id: str) -> int:
    """成功生成一次后计数 +1，返回最新使用次数"""
    conn = get_connection()
    conn.execute(
        """INSERT INTO usage_stats (user_id, used_count) VALUES (?, 1)
           ON CONFLICT(user_id) DO UPDATE SET used_count = used_count + 1,
           updated_at = datetime('now','localtime')""",
        (user_id,),
    )
    conn.commit()
    row = conn.execute("SELECT used_count FROM usage_stats WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["used_count"] if row else 1

def save_complaint(
    user_id: str,
    raw_text: str,
    complaint_letter: str,
    legal_basis: list,
    action_path: list,
    category: str,
    order_info: Optional[dict] = None,
    evidence: Optional[list] = None,
) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO complaints
           (user_id, raw_text, complaint_letter, legal_basis, action_path, category, order_info, evidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, raw_text, complaint_letter, json.dumps(legal_basis, ensure_ascii=False),
         json.dumps(action_path, ensure_ascii=False), category,
         json.dumps(order_info or {}, ensure_ascii=False),
         json.dumps(evidence or [], ensure_ascii=False)),
    )
    conn.commit()
    complaint_id = cursor.lastrowid
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_complaints(user_id: str, limit: int = 20, offset: int = 0, status: Optional[str] = None) -> tuple[list, int]:
    conn = get_connection()
    cursor = conn.cursor()
    where = "user_id = ?"
    params: list = [user_id]
    if status and status != "all":
        where += " AND status = ?"
        params.append(status)
    cursor.execute(
        f"SELECT id, category, raw_text, status, created_at FROM complaints WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    rows = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) FROM complaints WHERE {where}", params)
    total = cursor.fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_complaint_stats(user_id: str) -> dict:
    """用户投诉统计（我的页 / 首页使用）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS total, COUNT(DISTINCT category) AS categories FROM complaints WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    total = row["total"]
    cursor.execute(
        "SELECT COUNT(*) FROM complaints WHERE user_id = ? AND status IN ('resolved','following_up')",
        (user_id,),
    )
    in_progress = cursor.fetchone()[0]
    conn.close()
    return {"total": total, "categories": row["categories"], "in_progress": in_progress}


def get_complaint_by_id(complaint_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- 状态管理 ----------

VALID_STATUSES = (
    "generated", "copied", "submitted", "following_up", "resolved", "abandoned",
)

STATUS_LABELS = {
    "generated": "已生成",
    "copied": "已复制",
    "submitted": "已提交",
    "following_up": "跟进中",
    "resolved": "已解决",
    "abandoned": "已放弃",
}


def update_complaint_status(complaint_id: int, user_id: str, new_status: str) -> Optional[dict]:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"无效状态：{new_status}，有效值：{', '.join(VALID_STATUSES)}")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM complaints WHERE id = ? AND user_id = ?", (complaint_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    cursor.execute("UPDATE complaints SET status = ? WHERE id = ?", (new_status, complaint_id))
    conn.commit()
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    updated = cursor.fetchone()
    conn.close()
    return dict(updated) if updated else None


def delete_complaint(complaint_id: int, user_id: str) -> bool:
    """删除投诉记录（归属校验）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM complaints WHERE id = ? AND user_id = ?", (complaint_id, user_id))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


# ---------- 用户认证 ----------

TOKEN_TTL_DAYS = 30


def _new_token() -> str:
    return uuid.uuid4().hex


def create_or_update_user(phone: str = "", openid: str = "", email: str = "", password_hash: str = "",
                         nickname: str = "", avatar: str = "") -> dict:
    """邮箱 / 微信 openid / 手机号登录：存在则更新 token，不存在则创建"""
    conn = get_connection()
    cursor = conn.cursor()
    token = _new_token()
    expires_at = (datetime.now() + timedelta(days=TOKEN_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")

    if openid:
        cursor.execute("SELECT * FROM users WHERE openid = ?", (openid,))
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE users SET token = ?, token_expires_at = ?, nickname = ?, avatar = ? WHERE id = ?",
                (token, expires_at, nickname or row["nickname"], avatar or row["avatar"], row["id"]),
            )
            cursor.execute("SELECT * FROM users WHERE id = ?", (row["id"],))
            user = cursor.fetchone()
        else:
            cursor.execute(
                "INSERT INTO users (openid, nickname, avatar, token, token_expires_at) VALUES (?, ?, ?, ?, ?)",
                (openid, nickname, avatar, token, expires_at),
            )
            uid = cursor.lastrowid
            cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
            user = cursor.fetchone()
    elif email:
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE users SET token = ?, token_expires_at = ?, nickname = ?, avatar = ? WHERE id = ?",
                (token, expires_at, nickname or row["nickname"], avatar or row["avatar"], row["id"]),
            )
            cursor.execute("SELECT * FROM users WHERE id = ?", (row["id"],))
            user = cursor.fetchone()
        else:
            cursor.execute(
                "INSERT INTO users (email, password_hash, nickname, avatar, token, token_expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (email, password_hash, nickname, avatar, token, expires_at),
            )
            uid = cursor.lastrowid
            cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
            user = cursor.fetchone()
    else:
        cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE users SET token = ?, token_expires_at = ?, nickname = ?, avatar = ? WHERE id = ?",
                (token, expires_at, nickname or row["nickname"], avatar or row["avatar"], row["id"]),
            )
            cursor.execute("SELECT * FROM users WHERE id = ?", (row["id"],))
            user = cursor.fetchone()
        else:
            cursor.execute(
                "INSERT INTO users (phone, nickname, avatar, token, token_expires_at) VALUES (?, ?, ?, ?, ?)",
                (phone, nickname, avatar, token, expires_at),
            )
            cursor.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
            user = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(user)


def get_user_by_token(token: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE token = ? AND token_expires_at > datetime('now')", (token,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_phone(phone: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- 用户反馈 ----------

def save_feedback(
    complaint_id: int,
    user_id: str,
    rating: str = "helpful",
    comment: str = "",
) -> dict:
    """保存用户对生成结果的反馈（helpful / unhelpful）"""
    if rating not in ("helpful", "unhelpful"):
        rating = "helpful"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO feedback (complaint_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
        (complaint_id, user_id, rating, comment or ""),
    )
    conn.commit()
    fid = cursor.lastrowid
    cursor.execute("SELECT * FROM feedback WHERE id = ?", (fid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_feedback_stats() -> dict:
    """反馈统计（供运营/展示使用）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM feedback")
    total = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'helpful'")
    helpful = cursor.fetchone()[0]
    conn.close()
    return {"total": total, "helpful": helpful, "unhelpful": total - helpful}
