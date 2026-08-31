"""pytest 全局配置：演示模式 + 临时数据库"""

import os
import tempfile

# 必须在导入 backend 之前设置环境变量
_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="yanquan_test_"), "test.db")
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ENVIRONMENT"] = "test"

import pytest

from backend.database import DB_PATH, init_db


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前重建数据库表，保证用例隔离"""
    init_db()
    conn = __import__("backend.database", fromlist=["get_connection"]).get_connection()
    conn.execute("DELETE FROM complaints")
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM feedback")
    conn.execute("DELETE FROM usage_stats")
    conn.commit()
    conn.close()
    yield


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        yield c
