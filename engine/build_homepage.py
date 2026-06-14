#!/usr/bin/env python3
"""
build_homepage.py — specs/*.yaml から public/index.html を組み立てる。

トップページの「枠（masthead・lead・footer）」は固定し、道具カードだけを
specs から生成する。これで、道具を1本足す＝spec を置くだけでトップに並ぶ。

使い方:
    python engine/build_homepage.py
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import SPECS_DIR, PUBLIC

try:
    import yaml
except ImportError:
    sys.exit("エラー: PyYAML が必要です。 pip install pyyaml")

# セグメントの表示順（これ以外のセグメントは末尾にまとめる）
SEG_ORDER = ["お金の計算", "文章", "印刷もの"]


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def load_specs():
    specs = []
    for f in sorted(glob.glob(str(SPECS_DIR / "*.yaml"))):
        if Path(f).name.startswith("_"):
            continue
        spec = yaml.safe_load(Path(f).read_text(encoding="utf-8"))
        if spec and "id" in spec:
            specs.append(spec)
    return specs


def seg_key(spec):
    seg = spec.get("segment", "その他")
    rank = SEG_ORDER.index(seg) if seg in SEG_ORDER else len(SEG_ORDER)
    return (rank, spec["id"])


def card(spec, idx):
    return (
        f'      <a class="bin" href="/tools/{spec["id"]}/" data-idx="{idx:02d}">\n'
        f'        <p class="seg">{esc(spec.get("segment", ""))}</p>\n'
        f'        <p class="name">{esc(spec.get("title", spec["id"]))}</p>\n'
        f'        <p class="desc">{esc(spec.get("summary", ""))}</p>\n'
        f'        <span class="open">ひらく →</span>\n'
        f'      </a>\n'
    )


def build():
    specs = sorted(load_specs(), key=seg_key)
    bins = "\n".join(card(s, i + 1) for i, s in enumerate(specs))

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>道具屋 — 小さな道具を、ひとつずつ</title>
<meta name="description" content="日々のこまごました計算や作成を、その場で片づける小さな道具置き場。割り勘・文字数・のし袋・連番・当番表など、必要なものだけを単機能で。">
<link rel="canonical" href="https://dooguya.com/">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<div class="wrap">

  <header class="masthead">
    <p class="eyebrow">小さな道具置き場</p>
    <a class="brand" href="/">道具屋</a>
    <p class="lead">日々のこまごました計算や作成を、その場で片づけるための小さな道具を置いています。ひとつの道具は、ひとつの用事だけ。迷わず使えることを大事にしています。</p>
    <hr class="rule">
  </header>

  <main>
    <section class="bins" aria-label="道具の一覧">

{bins}
    </section>

    <p class="shelfnote">道具は少しずつ増えていきます。</p>
  </main>

  <footer class="foot">
    <span>道具屋</span>
    <a href="/sitemap.xml">サイトマップ</a>
  </footer>

</div>
</body>
</html>
"""
    out = PUBLIC / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out}（道具 {len(specs)} 本）")


if __name__ == "__main__":
    build()
