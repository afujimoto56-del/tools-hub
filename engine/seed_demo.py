#!/usr/bin/env python3
"""
seed_demo.py — デモ用の合成データを入れる
=========================================

GSCの認証がまだでも、ダッシュボードを今すぐ動かして確認するための種データ。
全判定分岐（張る/当たり候補/要改善/失速/退場/観察）を1本ずつ網羅する。

実行（init_db のあと）:
    python seed_demo.py
    python compute_status.py
    # dashboard/index.html をブラウザで開く

注意: 既存の gsc_daily と tools の DEMO-* 行を一度消してから入れ直す。
本番データ（GSCから入れたもの）には触れない（tool_id が 'demo-' で始まるものだけ操作）。
"""
import sqlite3
import sys
import random
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH

random.seed(42)
TODAY = date.today()


def d(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def make_daily(tool_id, days, gen):
    """gen(i) -> (impressions, clicks, position) で日次行を作る。
    i は「何日前か」(0=今日)。表示0の日は position=None。"""
    out = []
    for i in range(days):
        imp, clk, pos = gen(i)
        ctr = (clk / imp) if imp > 0 else 0.0
        out.append((tool_id, d(i), clk, imp, round(ctr, 4),
                    pos if imp > 0 else None))
    return out


# --- 各ツールの「実トラフィックの形」を関数で定義 ---------------------------
def winner(i):
    # 直近ほど表示・クリックが増え、順位が上がる（=数値が下がる）勝者。
    # i=0(今日)で約9位、i=27(28日前)で約25位。直近の表示が重いので
    # 表示重み付き平均順位は20位を割る。
    base_imp = max(0, int(70 - i * 1.6 + random.randint(-4, 4)))
    pos = 25 - (27 - i) * 0.60
    pos = max(7.0, pos + random.uniform(-0.8, 0.8))
    clk = int(base_imp * (0.05 + (27 - i) * 0.0025))  # 直近ほどCTRも上がる
    return base_imp, max(0, clk), round(pos, 1)


def candidate(i):
    # クリックは出ているが横ばい・順位は中位の当たり候補
    imp = max(0, int(35 + random.randint(-8, 8)))
    pos = 26 + random.uniform(-3, 3)
    clk = 1 if random.random() < 0.5 else 2
    return imp, clk, round(pos, 1)


def needs_improve(i):
    # 表示は十分あるがクリック0（タイトル/UXが弱い）
    imp = max(0, int(20 + random.randint(-4, 6)))
    pos = 18 + random.uniform(-2, 2)
    return imp, 0, round(pos, 1)


def stalled(i):
    # 一度生きて枯れた：古い期間は表示あり、直近7日は0
    if i < 7:
        return 0, 0, None
    imp = max(0, int(25 + random.randint(-6, 6)))
    pos = 22 + random.uniform(-3, 3)
    clk = 1 if (i > 14 and random.random() < 0.3) else 0
    return imp, clk, round(pos, 1)


def dead(i):
    # 離陸せず：ほぼ表示ゼロ（たまに1だけ拾う程度）
    imp = 1 if random.random() < 0.05 else 0
    return imp, 0, (40.0 if imp else None)


def lowsignal(i):
    # 観察中：表示が散発的でクリック0、判断材料不足
    imp = random.choice([0, 0, 0, 2, 5])
    return imp, 0, (33.0 if imp else None)


DEMO_TOOLS = [
    # (tool_id, title, target_query, launched_日数前, daily関数, 日数)
    ("demo-wari-calc",   "割り勘電卓（端数調整つき）",        "割り勘 端数 計算",      45, winner,       28),
    ("demo-unit-conv",   "尺貫法→メートル換算機",            "尺 メートル 換算",      60, candidate,    28),
    ("demo-furigana",    "ふりがな自動ふり機（印刷可）",        "ふりがな 印刷 プリント", 40, needs_improve,28),
    ("demo-noshi",       "のし袋 表書きジェネレーター",        "のし袋 書き方 印刷",    55, stalled,      28),
    ("demo-qr-batch",    "連番QR一括生成",                  "連番 QR 一括",         38, dead,          5),  # 古いが表示なし
    ("demo-newtool",     "干支カレンダー作成（新規）",         "干支 カレンダー 作成",   6, candidate,     6),  # 若い→観察待ち
    ("demo-lowsig",      "方位除け 早見表",                  "方位除け 早見",        50, lowsignal,    28),
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    try:
        # デモ行だけ消す（本番データは温存）
        conn.execute("DELETE FROM gsc_daily WHERE tool_id LIKE 'demo-%'")
        conn.execute("DELETE FROM tools     WHERE tool_id LIKE 'demo-%'")

        for tool_id, title, query, launched_days, gen, days in DEMO_TOOLS:
            url = f"https://hub.example.com/tools/{tool_id.replace('demo-', '')}/"
            conn.execute(
                "INSERT INTO tools (tool_id, url, title, target_query, spec_path, "
                "launched_at, status, note) VALUES (?,?,?,?,?,?, 'observing', 'demo')",
                (tool_id, url, title, query, f"specs/{tool_id}.yaml", d(launched_days)),
            )
            rows = make_daily(tool_id, days, gen)
            conn.executemany(
                "INSERT INTO gsc_daily (tool_id, date, clicks, impressions, ctr, position) "
                "VALUES (?,?,?,?,?,?)", rows,
            )
        conn.commit()
    finally:
        conn.close()
    print(f"OK: デモデータを投入しました（{len(DEMO_TOOLS)}本）")
    print("    次に: python compute_status.py  ->  dashboard/index.html を開く")


if __name__ == "__main__":
    seed()
