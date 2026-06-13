"""
道具屋 / 心臓 — 共通設定
========================

校正のつまみ（閾値）と、リポジトリ内のパスを一元管理する。
パイロットを回したあと、CONFIG の数値をいじるだけで判定が変わる。
"""
import os
from pathlib import Path

# --- パス（リポジトリのルートを基準に解決） ---------------------------------
ENGINE = Path(__file__).resolve().parent          # tools-hub/engine
ROOT = ENGINE.parent                               # tools-hub (リポジトリ直下)
DB_PATH = ENGINE / "db" / "factory.db"             # CIでは毎回作り直す一時DB
SCHEMA_PATH = ENGINE / "db" / "schema.sql"
SPECS_DIR = ROOT / "specs"
PUBLIC = ROOT / "public"                            # Cloudflare Pages が配信する場所
DASHBOARD_DATA = PUBLIC / "_status" / "data.json"   # compute_status.py が書き出す
SITEMAP_PATH = PUBLIC / "sitemap.xml"

# 公開サイトのベースURL（ツールURLの組み立てに使う）
BASE_URL = os.environ.get("BASE_URL", "https://dooguya.com")

# --- 判定の閾値（叩き台。パイロットで校正する） -----------------------------
CONFIG = {
    "observe_age_days": 14,       # ルール1: これより若いツールは観察待ち
    "imp_zero_eps": 1,            # 「表示ゼロ」とみなす上限
    "kill_age_days": 30,         # ルール2: これ以上たって28日表示ゼロなら退場
    "improve_imp_7d": 30,        # ルール3: 表示ゲート（7日表示がこれ以上でクリック0なら要改善）
    "winner_candidate_pos": 30,  # ルール4: 当たり候補とみなす順位の上限
    "winner_pos": 20,            # ルール5: 勝者と認める順位の天井
    "data_lag_days": 2,          # GSCの遅延（参照用メモ）
}

# --- 集計の窓（基本は変えない） ---------------------------------------------
WINDOW_SHORT_DAYS = 7
WINDOW_LONG_DAYS = 28
HALF_DAYS = 14
