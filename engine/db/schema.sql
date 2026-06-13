-- 数撃ち工場 / 心臓v0 — SQLite スキーマ
-- ナレッジ D「保存（SQLite, 3テーブル）」に対応。
-- date は 'YYYY-MM-DD' のテキストで保持する。

-- 1) tools : 撃った弾（ツール）の台帳
CREATE TABLE IF NOT EXISTS tools (
    tool_id            TEXT PRIMARY KEY,   -- 例: "wari-calc"（URLのスラッグと一致させる）
    url                TEXT NOT NULL,      -- 例: "https://hub.example.com/tools/wari-calc/"
    title              TEXT NOT NULL,
    target_query       TEXT,               -- 狙った検索クエリ（仮説）
    spec_path          TEXT,               -- 生成元のYAML specへのパス
    launched_at        TEXT NOT NULL,      -- 公開日 'YYYY-MM-DD'（年齢の起点）
    status             TEXT DEFAULT 'observing',  -- compute_status が上書きする
    status_updated_at  TEXT,
    note               TEXT
);

-- 2) gsc_daily : GSCのpage次元・日次メトリクス（生死判定の主データ）
CREATE TABLE IF NOT EXISTS gsc_daily (
    tool_id      TEXT NOT NULL,
    date         TEXT NOT NULL,            -- 'YYYY-MM-DD'
    clicks       INTEGER NOT NULL DEFAULT 0,
    impressions  INTEGER NOT NULL DEFAULT 0,
    ctr          REAL    NOT NULL DEFAULT 0,   -- 0〜1（GSCの素の値）
    position     REAL,                          -- 平均掲載順位（小さいほど上位）
    PRIMARY KEY (tool_id, date),
    FOREIGN KEY (tool_id) REFERENCES tools(tool_id)
);

-- 3) actions : 人間/自動が下したアクションの記録（v0.5で書き込み、v0は空でOK）
CREATE TABLE IF NOT EXISTS actions (
    tool_id  TEXT NOT NULL,
    date     TEXT NOT NULL,               -- アクションを取った日
    action   TEXT NOT NULL CHECK (action IN ('kill','double_down','improve','watch')),
    note     TEXT,
    PRIMARY KEY (tool_id, date, action),
    FOREIGN KEY (tool_id) REFERENCES tools(tool_id)
);

-- 集計を速くするための索引
CREATE INDEX IF NOT EXISTS idx_gsc_daily_date ON gsc_daily(date);
CREATE INDEX IF NOT EXISTS idx_tools_status   ON tools(status);
