#!/usr/bin/env python3
"""
ツールを1本 tools テーブルに登録する。
生産パイプライン（ナレッジ E）でデプロイ直後に呼ぶ想定のミニCLI。

使い方の例:
    python register_tool.py \
        --tool-id wari-calc \
        --url "https://hub.example.com/tools/wari-calc/" \
        --title "割り勘電卓（端数調整つき）" \
        --target-query "割り勘 計算 端数" \
        --spec-path specs/wari-calc.yaml \
        --launched-at 2026-06-09

--launched-at を省くと今日の日付になる。
同じ tool_id を再登録すると内容を更新する（URL差し替え等に使える）。
"""
import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH


def register_tool(tool_id, url, title, target_query=None,
                  spec_path=None, launched_at=None, note=None):
    launched_at = launched_at or date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO tools (tool_id, url, title, target_query, spec_path,
                               launched_at, status, status_updated_at, note)
            VALUES (?, ?, ?, ?, ?, ?, 'observing', NULL, ?)
            ON CONFLICT(tool_id) DO UPDATE SET
                url          = excluded.url,
                title        = excluded.title,
                target_query = excluded.target_query,
                spec_path    = excluded.spec_path,
                launched_at  = excluded.launched_at,
                note         = excluded.note
            """,
            (tool_id, url, title, target_query, spec_path, launched_at, note),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"OK: 登録/更新 -> {tool_id} ({url})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ツールを1本登録する")
    p.add_argument("--tool-id", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--target-query", default=None)
    p.add_argument("--spec-path", default=None)
    p.add_argument("--launched-at", default=None, help="YYYY-MM-DD（省略で今日）")
    p.add_argument("--note", default=None)
    a = p.parse_args()
    register_tool(a.tool_id, a.url, a.title, a.target_query,
                  a.spec_path, a.launched_at, a.note)
