#!/usr/bin/env python3
"""
DBを初期化する（テーブルを作る）。既存データは消さない（IF NOT EXISTS）。

使い方:
    python db/init_db.py

これを一度だけ実行すれば db/factory.db ができる。
"""
import sqlite3
import sys
from pathlib import Path

# プロジェクトルートを import パスに追加して config を読む
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, SCHEMA_PATH


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
    print(f"OK: DBを初期化しました -> {DB_PATH}")


if __name__ == "__main__":
    init_db()
