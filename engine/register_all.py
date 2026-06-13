#!/usr/bin/env python3
"""
register_all.py — specs/*.yaml を全部 tools テーブルに登録する。

CIでは毎回 DBを作り直す（GSC履歴はGoogle側にあるので一時DBでよい）。
その際、specsから tools を再登録するためのスクリプト。
URLは BASE_URL + /tools/<id>/ で組み立てる。

使い方:
    python engine/register_all.py
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import SPECS_DIR, BASE_URL
from register_tool import register_tool

try:
    import yaml
except ImportError:
    sys.exit("エラー: PyYAML が必要です。 pip install pyyaml")


def register_all():
    files = sorted(glob.glob(str(SPECS_DIR / "*.yaml")))
    count = 0
    for f in files:
        if Path(f).name.startswith("_"):   # _TEMPLATE.yaml はスキップ
            continue
        spec = yaml.safe_load(Path(f).read_text(encoding="utf-8"))
        if not spec or "id" not in spec:
            continue
        tool_id = spec["id"]
        url = f"{BASE_URL.rstrip('/')}/tools/{tool_id}/"
        register_tool(
            tool_id=tool_id,
            url=url,
            title=spec.get("title", tool_id),
            target_query=spec.get("target_query"),
            spec_path=f"specs/{Path(f).name}",
            launched_at=spec.get("launched_at"),
            note=spec.get("segment"),
        )
        count += 1
    print(f"OK: {count} 本のツールを登録しました")


if __name__ == "__main__":
    register_all()
