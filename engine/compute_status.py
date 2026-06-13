#!/usr/bin/env python3
"""
compute_status.py — 心臓の判定エンジン
======================================

gsc_daily を集計し、全ツールを
  「張る(double_down) / 殺す(kill) / 要改善(improve) / 観察(watch)」
の4バケツに自動仕分けして、ダッシュボード用の data.json を書き出す。

実行:
    python compute_status.py
    python compute_status.py --ref-date 2026-06-09   # 参照日を固定（再現用）

判定ルール（ナレッジ D「判定ロジック」に対応。閾値は config.py）
----------------------------------------------------------------
集計値: imp_7d / imp_28d / clicks_28d / pos_28d(表示重み付き平均順位) / ctr_28d
       さらにトレンド用に直近14日と前14日でクリック数・順位を比較する。

評価は「最初に当てはまったものを採用」(first match wins)。優先順位は下記。

 P1 [仕様1] 年齢 < observe_age_days(14)            -> 観察待ち（新規）  bucket=watch
 P2 [仕様5] クリック増加 & 順位上昇 & pos_28d<=20  -> 勝者：張る推奨    bucket=double_down
 P3 [仕様6] 28日は表示あり & 直近7日が枯れた        -> 失速：退場       bucket=kill
 P4 [仕様4] clicks_28d>0 & pos_28d<=30             -> 当たり候補       bucket=watch
 P5 [仕様3] imp_7d>=30 & clicks_28d==0             -> 要改善           bucket=improve
 P6 [仕様2] 年齢>=30 & imp_28d~=0                  -> 退場（離陸せず）  bucket=kill
 P7 (どれにも該当しない)                            -> 観察中：シグナル不足 bucket=watch

【仕様からの変更点（正直に明記）】
(a) ナレッジは「上から順に」とあるが、仕様4(当たり候補)は仕様5(勝者)の上位集合の
    ため、厳密に上から当てると仕様5が永久に発火しない（勝者が全部「候補」に吸わ
    れる）。意図は「勝者を先に拾う」と読めるため、P2(=仕様5) を P4(=仕様4) より
    先に評価している。
(b) 仕様6(失速)も仕様4(当たり候補)より先に評価している。理由：直近7日の表示が
    枯れたツールは、過去のクリックが残っていると仕様4で「候補」に誤判定される。
    「枯れた」は退場シグナルなので候補より優先する。
両方とも校正時にこの順序でよいか確認すること。
"""
import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (CONFIG, DB_PATH, DASHBOARD_DATA,
                    WINDOW_SHORT_DAYS, WINDOW_LONG_DAYS, HALF_DAYS)


# --- バケツの表示名・キュー内の優先度（数字が小さいほど上に出す） -------------
BUCKET_LABEL = {
    "double_down": "張る候補",
    "kill": "殺す候補",
    "improve": "要改善",
    "watch": "観察中",
}
BUCKET_PRIORITY = {"double_down": 0, "kill": 1, "improve": 2, "watch": 3}

# 各カードに出す「次の一手」のラベル
ACTION_LABEL = {
    "double_down": "張る（広げる）",
    "kill": "退場させる",
    "improve": "直す（一度だけ）",
    "watch": "様子見",
}


def _daterange_sum(rows, start, end):
    """rows(date->dict) のうち start<=date<=end の clicks/impressions を合計し、
    表示重み付き平均順位を返す。"""
    clicks = imps = 0
    wpos_num = 0.0  # Σ position*impressions
    for d, r in rows.items():
        if start <= d <= end:
            clicks += r["clicks"]
            imps += r["impressions"]
            if r["position"] is not None and r["impressions"] > 0:
                wpos_num += r["position"] * r["impressions"]
    pos = (wpos_num / imps) if imps > 0 else None
    return clicks, imps, pos


def compute_for_tool(tool, daily_rows, ref_date):
    """1ツール分の集計と判定を行い、ダッシュボード用 dict を返す。"""
    cfg = CONFIG
    eps = cfg["imp_zero_eps"]

    launched = datetime.strptime(tool["launched_at"], "%Y-%m-%d").date()
    age_days = (ref_date - launched).days

    # 窓の境界（ref_date を含む後ろ向き窓）
    short_start = ref_date - timedelta(days=WINDOW_SHORT_DAYS - 1)
    long_start = ref_date - timedelta(days=WINDOW_LONG_DAYS - 1)
    recent_start = ref_date - timedelta(days=HALF_DAYS - 1)            # 直近14日
    prev_end = recent_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=HALF_DAYS - 1)             # その前14日

    # 日次を date(str)->dict に整形
    rows = {}
    for r in daily_rows:
        rows[r["date"]] = {
            "clicks": r["clicks"], "impressions": r["impressions"],
            "position": r["position"],
        }
    s = lambda d: d.isoformat()

    clicks_7d, imp_7d, _ = _daterange_sum(rows, s(short_start), s(ref_date))
    clicks_28d, imp_28d, pos_28d = _daterange_sum(rows, s(long_start), s(ref_date))
    clicks_recent, imp_recent, pos_recent = _daterange_sum(rows, s(recent_start), s(ref_date))
    clicks_prev, imp_prev, pos_prev = _daterange_sum(rows, s(prev_start), s(prev_end))
    ctr_28d = (clicks_28d / imp_28d) if imp_28d > 0 else 0.0

    # トレンド: クリック増加 / 順位上昇（=順位の数値が小さくなる）
    clicks_rising = clicks_recent > clicks_prev
    pos_rising = (pos_recent is not None and pos_prev is not None
                  and pos_recent < pos_prev)

    # ---- 判定（first match wins） ----
    if age_days < cfg["observe_age_days"]:
        status, bucket = "observing_new", "watch"
        verdict = "観察待ち（新規）"
        reason = f"公開{age_days}日。判定保留（>= {cfg['observe_age_days']}日で評価開始）"

    elif (clicks_rising and pos_rising and clicks_28d > 0
          and pos_28d is not None and pos_28d <= cfg["winner_pos"]):
        status, bucket = "winner", "double_down"
        verdict = "勝者：張る推奨"
        reason = (f"クリック増({clicks_prev}→{clicks_recent}) ・順位上昇 "
                  f"・平均{pos_28d:.1f}位（<= {cfg['winner_pos']}）")

    elif imp_28d > eps and imp_7d <= eps:
        status, bucket = "stall", "kill"
        verdict = "失速：表示が枯れた"
        reason = f"28日表示{imp_28d}があったが直近7日は{imp_7d}。一度生きて枯れた"

    elif clicks_28d > 0 and pos_28d is not None and pos_28d <= cfg["winner_candidate_pos"]:
        status, bucket = "winner_candidate", "watch"
        verdict = "当たり候補：観察継続"
        reason = f"28日クリック{clicks_28d} ・平均{pos_28d:.1f}位（<= {cfg['winner_candidate_pos']}）"

    elif imp_7d >= cfg["improve_imp_7d"] and clicks_28d == 0:
        status, bucket = "needs_improve", "improve"
        verdict = "要改善：表示はあるがクリック0"
        reason = f"直近7日表示{imp_7d}（>= {cfg['improve_imp_7d']}）なのにクリック0。タイトル/UXを一度だけ直す"

    elif age_days >= cfg["kill_age_days"] and imp_28d <= eps:
        status, bucket = "dead", "kill"
        verdict = "退場：離陸せず"
        reason = f"公開{age_days}日・28日表示{imp_28d}（<= {eps}）。離陸の兆候なし"

    else:
        status, bucket = "observing", "watch"
        verdict = "観察中：シグナル不足"
        reason = f"公開{age_days}日・28日表示{imp_28d}/クリック{clicks_28d}。判断材料が足りない"

    # スパークライン用：直近28日の日次（無い日は0埋め）
    spark_dates, spark_imp, spark_clicks = [], [], []
    for i in range(WINDOW_LONG_DAYS - 1, -1, -1):
        d = s(ref_date - timedelta(days=i))
        spark_dates.append(d)
        if d in rows:
            spark_imp.append(rows[d]["impressions"])
            spark_clicks.append(rows[d]["clicks"])
        else:
            spark_imp.append(0)
            spark_clicks.append(0)

    return {
        "tool_id": tool["tool_id"],
        "url": tool["url"],
        "title": tool["title"],
        "target_query": tool["target_query"],
        "launched_at": tool["launched_at"],
        "age_days": age_days,
        "status": status,
        "bucket": bucket,
        "bucket_label": BUCKET_LABEL[bucket],
        "action_label": ACTION_LABEL[bucket],
        "verdict": verdict,
        "reason": reason,
        "metrics": {
            "imp_7d": imp_7d,
            "imp_28d": imp_28d,
            "clicks_28d": clicks_28d,
            "ctr_28d": round(ctr_28d, 4),
            "pos_28d": round(pos_28d, 1) if pos_28d is not None else None,
            "clicks_recent": clicks_recent,
            "clicks_prev": clicks_prev,
            "pos_recent": round(pos_recent, 1) if pos_recent is not None else None,
            "pos_prev": round(pos_prev, 1) if pos_prev is not None else None,
        },
        "spark_dates": spark_dates,
        "spark_imp": spark_imp,
        "spark_clicks": spark_clicks,
    }


def _queue_sort_key(card):
    """キューの並び：バケツ優先度 → バケツ内のシグナル強さ。"""
    b = card["bucket"]
    m = card["metrics"]
    if b == "double_down":
        secondary = -m["clicks_28d"]              # クリック多い順
    elif b == "kill":
        secondary = -card["age_days"]             # 古い順
    elif b == "improve":
        secondary = -m["imp_7d"]                  # 表示多い順
    else:  # watch
        secondary = -m["imp_28d"]                 # 表示多い順
    return (BUCKET_PRIORITY[b], secondary)


def compute_all(ref_date=None):
    ref_date = ref_date or date.today()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tools = [dict(r) for r in conn.execute("SELECT * FROM tools")]
        cards = []
        now_iso = datetime.now().isoformat(timespec="seconds")
        for t in tools:
            daily = conn.execute(
                "SELECT date, clicks, impressions, ctr, position "
                "FROM gsc_daily WHERE tool_id = ? ORDER BY date", (t["tool_id"],)
            ).fetchall()
            daily = [dict(r) for r in daily]
            card = compute_for_tool(t, daily, ref_date)
            cards.append(card)

            # tools.status を更新（人が後で見たときの一次情報）
            conn.execute(
                "UPDATE tools SET status = ?, status_updated_at = ? WHERE tool_id = ?",
                (card["status"], now_iso, t["tool_id"]),
            )
        conn.commit()
    finally:
        conn.close()

    cards.sort(key=_queue_sort_key)

    counts = {"double_down": 0, "kill": 0, "improve": 0, "watch": 0}
    for c in cards:
        counts[c["bucket"]] += 1
    counts["total"] = len(cards)

    return {
        "generated_at": now_iso,
        "ref_date": ref_date.isoformat(),
        "data_lag_days": CONFIG["data_lag_days"],
        "config": CONFIG,
        "counts": counts,
        "queue": cards,
    }


def main():
    p = argparse.ArgumentParser(description="判定してダッシュボードJSONを書き出す")
    p.add_argument("--ref-date", default=None, help="参照日 YYYY-MM-DD（省略で今日）")
    p.add_argument("--out", default=str(DASHBOARD_DATA), help="出力JSONパス")
    a = p.parse_args()
    ref = datetime.strptime(a.ref_date, "%Y-%m-%d").date() if a.ref_date else None

    result = compute_all(ref)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    c = result["counts"]
    print(f"OK: {out}")
    print(f"  参照日 {result['ref_date']} / 全{c['total']}本")
    print(f"  張る {c['double_down']} / 殺す {c['kill']} / 要改善 {c['improve']} / 観察 {c['watch']}")


if __name__ == "__main__":
    main()
