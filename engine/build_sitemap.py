#!/usr/bin/env python3
"""
build_sitemap.py — specs/*.yaml から public/sitemap.xml を作る。

トップページ＋各ツールURLを列挙する。/_status/（社内ダッシュボード）は載せない。

使い方:
    python engine/build_sitemap.py
"""
import glob
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import SPECS_DIR, PUBLIC, BASE_URL, SITEMAP_PATH

try:
    import yaml
except ImportError:
    sys.exit("エラー: PyYAML が必要です。 pip install pyyaml")


def build():
    base = BASE_URL.rstrip("/")
    today = date.today().isoformat()
    urls = [(base + "/", today)]
    for f in sorted(glob.glob(str(SPECS_DIR / "*.yaml"))):
        if Path(f).name.startswith("_"):
            continue
        spec = yaml.safe_load(Path(f).read_text(encoding="utf-8"))
        if not spec or "id" not in spec:
            continue
        urls.append((f"{base}/tools/{spec['id']}/", spec.get("launched_at", today)))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>\n")

    PUBLIC.mkdir(parents=True, exist_ok=True)
    SITEMAP_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {SITEMAP_PATH}（{len(urls)} URL）")


if __name__ == "__main__":
    build()
