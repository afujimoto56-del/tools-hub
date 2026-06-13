#!/usr/bin/env python3
"""
fetch_gsc.py — Google Search Console 日次取り込み（page次元）
===========================================================

GSC Search Analytics API から page+date 次元の clicks/impressions/ctr/position を
取得し、tools テーブルのURLに一致する行だけ gsc_daily に upsert する。

★ 認証情報は本人側のものを差し込む（下の「設定」2か所）。
  セットアップ手順は README.md「GSC接続の手順」を参照（どこをクリックするかまで記載）。

依存:
    pip install -r requirements.txt
    （google-api-python-client / google-auth）

使い方:
    # 直近30日を取得（既定）
    python ingest/fetch_gsc.py

    # 範囲指定（初回バックフィルなど）。GSC履歴は最長16ヶ月。
    python ingest/fetch_gsc.py --start 2026-01-01 --end 2026-06-07

GSCデータは約2日遅れ。直近1〜2日は薄い/空でも正常。
生死判定を page 次元で行うのは、query 次元より欠落が少ないから（ナレッジD）。
"""
import argparse
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, CONFIG

# ============================================================================
# 設定（ここ2か所を自分の値に差し替える）
# ============================================================================
# 1) サービスアカウントの鍵JSONへのパス。
#    Google Cloud で作ったサービスアカウントの鍵をダウンロードして置く。
SERVICE_ACCOUNT_FILE = str(Path(__file__).resolve().parent / "service_account.json")

# 2) GSCのプロパティ。CIでは環境変数 GSC_PROPERTY で渡す。
#    - ドメインプロパティなら "sc-domain:dooguya.com"
#    - URLプレフィックスプロパティなら "https://dooguya.com/"（末尾スラッシュ含む）
import os as _os
GSC_PROPERTY = _os.environ.get("GSC_PROPERTY", "sc-domain:dooguya.com")
# ============================================================================

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
ROW_LIMIT = 25000  # GSC APIの1リクエスト上限


def _build_service():
    """google ライブラリを読み込み、Search Console サービスを作る。
    未インストールなら分かりやすく案内して終了。"""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "エラー: google ライブラリが入っていません。\n"
            "  pip install -r requirements.txt\n"
            "を実行してください。"
        )
    if not Path(SERVICE_ACCOUNT_FILE).exists():
        sys.exit(
            f"エラー: 鍵JSONが見つかりません -> {SERVICE_ACCOUNT_FILE}\n"
            "README.md「GSC接続の手順」に従ってサービスアカウントの鍵を置いてください。"
        )
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    # searchconsole v1（webmasters の後継）。query は同じ。
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def _normalize(url):
    """URLマッチ用の正規化（末尾スラッシュ・大文字小文字の揺れを吸収）。"""
    return url.strip().rstrip("/").lower()


def _load_url_map(conn):
    """gsc の page URL -> tool_id の対応表を作る。"""
    m = {}
    for tool_id, url in conn.execute("SELECT tool_id, url FROM tools"):
        m[_normalize(url)] = tool_id
    return m


def fetch_rows(service, start, end):
    """指定期間の date+page 次元行を、ページネーションしながら全部取る。"""
    rows = []
    start_row = 0
    while True:
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["date", "page"],
            "rowLimit": ROW_LIMIT,
            "startRow": start_row,
            "dataState": "final",  # 確定値のみ（速報を混ぜたいなら "all"）
        }
        resp = service.searchanalytics().query(siteUrl=GSC_PROPERTY, body=body).execute()
        batch = resp.get("rows", [])
        rows.extend(batch)
        if len(batch) < ROW_LIMIT:
            break
        start_row += ROW_LIMIT
    return rows


def upsert(conn, url_map, gsc_rows):
    """GSC行を gsc_daily に upsert。tools にURLが無いページは無視。"""
    matched = unmatched = 0
    for r in gsc_rows:
        the_date, page = r["keys"][0], r["keys"][1]
        tool_id = url_map.get(_normalize(page))
        if tool_id is None:
            unmatched += 1
            continue
        conn.execute(
            """
            INSERT INTO gsc_daily (tool_id, date, clicks, impressions, ctr, position)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tool_id, date) DO UPDATE SET
                clicks      = excluded.clicks,
                impressions = excluded.impressions,
                ctr         = excluded.ctr,
                position    = excluded.position
            """,
            (tool_id, the_date,
             int(r.get("clicks", 0)), int(r.get("impressions", 0)),
             float(r.get("ctr", 0.0)), float(r.get("position", 0.0))),
        )
        matched += 1
    conn.commit()
    return matched, unmatched


def main():
    today = date.today()
    default_start = (today - timedelta(days=30)).isoformat()
    default_end = today.isoformat()

    p = argparse.ArgumentParser(description="GSC日次をgsc_dailyに取り込む（page次元）")
    p.add_argument("--start", default=default_start, help="開始日 YYYY-MM-DD（既定: 30日前）")
    p.add_argument("--end", default=default_end, help="終了日 YYYY-MM-DD（既定: 今日）")
    a = p.parse_args()

    print(f"GSC取得: {GSC_PROPERTY}  {a.start} 〜 {a.end}（約{CONFIG['data_lag_days']}日遅延あり）")
    service = _build_service()
    gsc_rows = fetch_rows(service, a.start, a.end)
    print(f"  取得行数（date×page）: {len(gsc_rows)}")

    conn = sqlite3.connect(DB_PATH)
    try:
        url_map = _load_url_map(conn)
        if not url_map:
            sys.exit("エラー: tools テーブルが空です。先に register_tool.py でツールを登録してください。")
        matched, unmatched = upsert(conn, url_map, gsc_rows)
    finally:
        conn.close()

    print(f"  取り込み: {matched} 行 / 未一致(tools未登録ページ): {unmatched} 行")
    print("  次に: python compute_status.py")


if __name__ == "__main__":
    main()
