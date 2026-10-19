#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HotRadar 静态站点生成器
======================
读取 data/*.json 每日快照，生成完整静态站点到 output/。

生成内容：
  index.html            今日速览（头条/行情/各源热榜/自动点评/热词）
  sources.html          数据源总览
  source/{key}.html     每个数据源的完整榜单
  archive.html          历史归档索引
  archive/{date}.html   每日完整存档（SEO 长尾主力）
  tag/{tag}.html        标签聚合页
  about/privacy/contact/404
  sitemap.xml / robots.txt / feed.xml / ads.txt
  og/{date}.png         OG 分享图（需 Pillow，缺失自动跳过）
"""
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
    import og as og_mod
except Exception:  # noqa: BLE001
    og_mod = None

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


# ---------------- 基础工具 ----------------

def esc(s):
    return html.escape(str(s), quote=True)


def fmt_num(n):
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0"
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def fmt_cny(n):
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return "¥0"
    if n >= 100:
        return f"¥{n:,.0f}"
    if n >= 1:
        return f"¥{n:,.2f}"
    return f"¥{n:.4f}"


def domain_of(url):
    try:
        return urllib.parse.urlparse(url).netloc.replace("www.", "")
    except Exception:  # noqa: BLE001
        return ""


def date_label(d):
    y, m, dd = d.split("-")
    return f"{y}年{int(m)}月{int(dd)}日"


def weekday_of(d):
    return WEEKDAYS[datetime.strptime(d, "%Y-%m-%d").weekday()]


def day_of_year(d):
    return datetime.strptime(d, "%Y-%m-%d").timetuple().tm_yday


def time_of(iso_str):
    return (iso_str.split("T")[1][:5] if "T" in iso_str else "--:--")


def total_items(snap):
    return sum(len(s["items"]) for s in snap["sources"].values())


def source_count(snap):
    return sum(1 for s in snap["sources"].values() if s["items"])


def max_score(snap):
    best = 0
    for s in snap["sources"].values():
        for it in s["items"]:
            best = max(best, it.get("score", 0))
    return best


def top_headline(snap):
    best = None
    for key, src in snap["sources"].items():
        for it in src["items"]:
            if best is None or it.get("score", 0) > best[1].get("score", 0):
                best = (key, it)
    return best


# ---------------- 数据加载 ----------------

def load_snapshots():
    snaps = []
    if not os.path.isdir(config.DATA_DIR):
        return snaps
    for f in sorted(os.listdir(config.DATA_DIR)):
        if not DATE_RE.match(f):
            continue
        try:
            with open(os.path.join(config.DATA_DIR, f), encoding="utf-8") as fh:
                snaps.append(json.load(fh))
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 跳过损坏的数据文件 {f}: {e}")
    snaps.sort(key=lambda s: s["date"], reverse=True)
    return snaps


# ---------------- HTML 组件 ----------------

def ad_slot(name, fmt="auto"):
    slot_id = config.AD_SLOTS.get(name, "")
    attr = f' data-slot="{esc(slot_id)}"' if slot_id else ""
    return f'<div class="ad-slot" data-ad="{name}" data-format="{fmt}"{attr}></div>'


def src_badge(key, size=""):
    meta = config.SOURCE_META.get(key, {})
    cls = f"src-badge {size}".strip()
    return (f'<span class="{cls}" style="--c:{meta.get("color", "#888")}">'
            f'{esc(meta.get("short", key))}</span>')


def hot_item_html(key, it, rank, show_date=None, date_prefix=""):
    meta = config.SOURCE_META.get(key, {})
    parts = [f'<li class="hot-item">']
    rank_cls = "rank rank-top" if rank <= 3 else "rank"
    parts.append(f'<span class="{rank_cls}">{rank}</span>')
    parts.append('<div class="hot-body">')
    parts.append(
        f'<a class="hot-title" href="{esc(it.get("url", "#"))}" '
        f'target="_blank" rel="noopener nofollow">{esc(it.get("title", ""))}</a>')
    desc = (it.get("desc") or "").strip()
    if desc:
        parts.append(f'<p class="hot-desc">{esc(desc)}</p>')
    parts.append('<div class="hot-meta">')
    parts.append(f'<span class="src-tag" style="--c:{meta.get("color", "#888")}">'
                 f'{esc(meta.get("name", key))}</span>')
    if it.get("score"):
        parts.append(f'<span class="meta-score">🔥 {fmt_num(it["score"])}</span>')
    if it.get("comments"):
        parts.append(f'<span class="meta-cmts">💬 {fmt_num(it["comments"])}</span>')
    if it.get("author"):
        parts.append(f'<span class="meta-author">@{esc(it["author"])}</span>')
    dom = domain_of(it.get("url", ""))
    if dom:
        parts.append(f'<span class="meta-domain">{esc(dom)}</span>')
    if show_date:
        parts.append(f'<a class="meta-date" href="{date_prefix}archive/{show_date}.html">{date_label(show_date)}</a>')
    parts.append(f'<time data-time="{int(it.get("time", 0))}"></time>')
    parts.append('</div></div></li>')
    return "".join(parts)


def hot_list_html(key, items, start=1, show_date=None):
    lis = [hot_item_html(key, it, i, show_date) for i, it in enumerate(items, start)]
    return f'<ol class="hot-list">{"".join(lis)}</ol>'


def source_section_html(key, snap, limit=8, prefix=""):
    items = snap["sources"].get(key, {}).get("items", [])
    if not items:
        return ""
    meta = config.SOURCE_META[key]
    head = (
        f'<div class="section-head"><h2>{src_badge(key)} '
        f'{esc(meta["name"])} <span class="src-label">{esc(meta["label"])}</span></h2>'
        f'<a class="more-link" href="{prefix}source/{key}.html">完整榜单 →</a></div>')
    return (f'<section class="section source-section" id="src-{key}">'
            f'{head}{hot_list_html(key, items[:limit])}</section>')


def crypto_html(crypto):
    if not crypto:
        return ""
    cards = []
    for c in crypto:
        change = c.get("change", 0) or 0
        cls = "up" if change >= 0 else "down"
        sign = "+" if change >= 0 else ""
        cards.append(
            f'<div class="crypto-card"><span class="crypto-name">{esc(c["name"])}</span>'
            f'<span class="crypto-price">{fmt_cny(c["cny"])}</span>'
            f'<span class="crypto-change {cls}">{sign}{change:.2f}%</span></div>')
    return (
        f'<section class="section crypto-section"><div class="section-head">'
        f'<h2>💰 币圈行情</h2><span class="section-note">数据来源 CoinGecko</span></div>'
        f'<div class="crypto-grid">{"".join(cards)}</div></section>')


def tag_filename(tag):
    """把标签转成安全的文件名（去掉 URL/文件系统敏感字符）"""
    safe = re.sub(r'[\\/:*?"<>|%#]', "-", tag).strip()
    return safe or "tag"


def tag_page_path(tag):
    # tag_filename 已过滤掉 URL/文件系统敏感字符，直接拼文件名（不再 quote，
    # 否则磁盘文件名含 % 而浏览器解码后 404）
    return "tag/" + tag_filename(tag) + ".html"


def tag_cloud_html(tags, prefix=""):
    if not tags:
        return ""
    chips = []
    for tag, cnt in tags:
        href = prefix + tag_page_path(tag)
        chips.append(f'<a class="tag-chip" href="{href}">{esc(tag)} <i>{cnt}</i></a>')
    return (
        f'<section class="section"><div class="section-head"><h2>🏷️ 今日热词</h2>'
        f'<span class="section-note">点击查看相关热点</span></div>'
        f'<div class="tag-cloud">{"".join(chips)}</div></section>')


def make_commentary(snap, prefix=""):
    """根据榜单数据自动生成点评文字（每日独特内容）"""
    paras = []
    for key, src in snap["sources"].items():
        items = src["items"]
        if not items:
            continue
        meta = config.SOURCE_META.get(key, {})
        top = items[0]
        title = esc(top.get("title", ""))
        if key == "github":
            paras.append(
                f'<strong>{esc(meta["name"])}</strong>：本周新星项目 <em>{title}</em> '
                f'以 {fmt_num(top["score"])} Star 领跑，是过去 7 天关注度增长最快的开源项目。')
        elif key == "hackernews":
            paras.append(
                f'<strong>{esc(meta["name"])}</strong>：今日头牌 <em>{title}</em> 获得 '
                f'{top["score"]} 分支持与 {fmt_num(top["comments"])} 条讨论，'
                f'代表当前全球技术圈最受关注的话题。')
        elif key == "v2ex":
            paras.append(
                f'<strong>{esc(meta["name"])}</strong>：社区热议 <em>{title}</em>，'
                f'已引发 {fmt_num(top["comments"])} 条回复，是中文技术社区今日焦点。')
        elif key == "reddit":
            paras.append(
                f'<strong>{esc(meta["name"])}</strong>：<em>{title}</em> 登上技术版块热帖榜，'
                f'收获 {fmt_num(top["score"])} 分赞与 {fmt_num(top["comments"])} 条评论。')
        elif key == "devto":
            paras.append(
                f'<strong>{esc(meta["name"])}</strong>：本周最受欢迎文章是 <em>{title}</em>，'
                f'获得 {fmt_num(top["score"])} 个开发者点赞。')
        elif key == "lobsters":
            paras.append(
                f'<strong>{esc(meta["name"])}</strong>：技术链接榜首位是 <em>{title}</em>，'
                f'以讨论质量著称的社区今日焦点。')
    best = top_headline(snap)
    if best:
        key, top = best
        paras.append(
            f'综合各大榜单，今日全网热度最高的是来自{esc(config.SOURCE_META[key]["name"])}的 '
            f'<em>{esc(top["title"])}</em>。热点雷达每日 06:00 自动更新，'
            f'可通过 <a href="{prefix}feed.xml">RSS</a> 订阅追踪。')
    return paras


def collect_tags(snap):
    counts = {}
    for src in snap["sources"].values():
        for it in src["items"]:
            for t in it.get("tags", []):
                t = (t or "").strip()
                if t:
                    counts[t] = counts.get(t, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))


# ---------------- 页面骨架 ----------------

def header_html(prefix, active):
    def cls(name):
        return ' class="active"' if active == name else ""

    nav = (f'<nav class="site-nav" id="site-nav">'
           f'<a href="{prefix}index.html"{cls("today")}>今日</a>'
           f'<a href="{prefix}sources.html"{cls("sources")}>数据源</a>'
           f'<a href="{prefix}archive.html"{cls("archive")}>归档</a>'
           f'<a href="{prefix}about.html"{cls("about")}>关于</a>'
           f'</nav>')
    return f'''<header class="site-header">
  <div class="container header-inner">
    <a class="logo" href="{prefix}index.html">
      <span class="logo-mark">🔥</span>
      <span class="logo-text">{esc(config.SITE_NAME)}<small>{esc(config.SITE_NAME_EN)}</small></span>
    </a>
    {nav}
    <div class="header-actions">
      <button class="icon-btn" id="theme-toggle" aria-label="切换深浅色模式" title="切换深浅色模式">🌙</button>
      <button class="icon-btn nav-toggle" id="nav-toggle" aria-label="打开菜单" title="菜单">☰</button>
    </div>
  </div>
</header>'''


def footer_html(prefix):
    src_links = "".join(
        f'<a href="{prefix}source/{k}.html">{esc(v["name"])}</a>'
        for k, v in config.SOURCE_META.items())
    year = datetime.now().year
    return f'''<footer class="site-footer">
  <div class="container footer-grid">
    <div class="footer-col footer-brand">
      <strong>{esc(config.SITE_NAME)} · {esc(config.SITE_TAGLINE)}</strong>
      <p>每日自动聚合全球六大技术热榜，内容由程序自动生成与更新，仅供参考。</p>
    </div>
    <div class="footer-col">
      <strong>导航</strong>
      <a href="{prefix}index.html">今日热点</a>
      <a href="{prefix}sources.html">数据源</a>
      <a href="{prefix}archive.html">历史归档</a>
      <a href="{prefix}feed.xml">RSS 订阅</a>
    </div>
    <div class="footer-col">
      <strong>数据源</strong>
      {src_links}
    </div>
    <div class="footer-col">
      <strong>关于</strong>
      <a href="{prefix}about.html">关于我们</a>
      <a href="{prefix}privacy.html">隐私政策</a>
      <a href="{prefix}contact.html">联系我们</a>
    </div>
  </div>
  <div class="container footer-bottom">
    <span>© {year} {esc(config.SITE_NAME)}</span>
    <span>本站包含广告与推广链接 · <a href="{prefix}privacy.html">隐私政策</a></span>
  </div>
</footer>
<a class="back-top" id="back-top" href="#" aria-label="回到顶部">↑</a>'''


THEME_BOOT = ("<script>(function(){var t=localStorage.getItem('hr-theme');"
              "if(!t&&window.matchMedia&&matchMedia('(prefers-color-scheme:dark)').matches)t='dark';"
              "if(t)document.documentElement.setAttribute('data-theme',t)})();</script>")


def page_shell(title, description, path, body, prefix="", active="",
               jsonld="", og_image=""):
    domain = config.SITE_DOMAIN.rstrip("/")
    canonical = f"{domain}/{path}"
    if not og_image:
        og_image = f"{domain}/og/default.png"
    jsonld_block = (f'<script type="application/ld+json">{jsonld}</script>'
                    if jsonld else "")
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="keywords" content="{esc(config.SITE_KEYWORDS)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(config.SITE_NAME)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{og_image}">
<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{esc(config.SITE_NAME)} RSS" href="{prefix}feed.xml">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script>window.ADSENSE_CLIENT="{esc(config.ADSENSE_CLIENT)}";</script>
{THEME_BOOT}
{jsonld_block}
</head>
<body>
{header_html(prefix, active)}
<main class="container">
{body}
</main>
{footer_html(prefix)}
<script src="{prefix}assets/app.js" defer></script>
</body>
</html>'''


def write_page(out_path, content):
    full = os.path.join(config.OUTPUT_DIR, out_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def breadcrumb_html(prefix, trail):
    """trail: [(label, href or None), ...]"""
    parts = ['<nav class="breadcrumb" aria-label="面包屑">',
             f'<a href="{prefix}index.html">首页</a>']
    for i, (label, href) in enumerate(trail):
        sep = '<span class="bc-sep">/</span>'
        if href:
            parts.append(f'{sep}<a href="{href}">{esc(label)}</a>')
        else:
            parts.append(f'{sep}<span class="bc-current">{esc(label)}</span>')
    parts.append('</nav>')
    return "".join(parts)


# ---------------- 页面构建 ----------------

def digest_body(snap, is_today, prefix=""):
    """今日/归档页共用主体"""
    date = snap["date"]
    body = []
    # 头部信息
    stats = (f'<div class="hero-stats">'
             f'<span>📦 收录 <b>{total_items(snap)}</b> 条</span>'
             f'<span>📡 <b>{source_count(snap)}</b> 个数据源</span>'
             f'<span>🔥 最高热度 <b>{fmt_num(max_score(snap))}</b></span>'
             f'<span>🕘 更新于 {time_of(snap.get("generated_at", ""))}</span>'
             f'</div>')
    title = "今日全球热点速览" if is_today else "全球热点归档"
    body.append(f'''<section class="hero">
  <div class="hero-date">
    <span class="hero-day">{date_label(date)}</span>
    <span class="hero-week">{weekday_of(date)}</span>
    <span class="hero-no">第 {day_of_year(date)} 天</span>
  </div>
  <h1>{title}</h1>
  <p class="hero-sub">六大热榜 · 程序自动聚合 · 每日 06:00 更新</p>
  {stats}
</section>''')

    # 今日头条 TOP3（每个源的第一名按源内相对热度排序）
    candidates = []
    for key, src in snap["sources"].items():
        items = src["items"]
        if not items:
            continue
        top = items[0]
        mx = max((i.get("score", 0) for i in items), default=0) or 1
        candidates.append((top.get("score", 0) / mx, key, top))
    candidates.sort(key=lambda x: x[0], reverse=True)
    top3 = candidates[:3]
    if top3:
        cards = []
        for rank, (_, key, it) in enumerate(top3, 1):
            meta = config.SOURCE_META.get(key, {})
            desc = (it.get("desc") or "").strip() or "点击查看原文详情"
            cards.append(f'''<article class="top3-card rank-{rank}">
  <div class="top3-rank">{rank}</div>
  <span class="src-badge" style="--c:{meta.get("color", "#888")}">{esc(meta.get("name", key))}</span>
  <a class="top3-title" href="{esc(it.get("url", "#"))}" target="_blank" rel="noopener nofollow">{esc(it.get("title", ""))}</a>
  <p class="top3-desc">{esc(desc)}</p>
  <div class="top3-meta">
    <span>🔥 {fmt_num(it.get("score", 0))}</span>
    <span>💬 {fmt_num(it.get("comments", 0))}</span>
    <span>{esc(domain_of(it.get("url", "")))}</span>
  </div>
</article>''')
        body.append(f'''<section class="section">
  <div class="section-head"><h2>🏆 今日头条</h2>
  <span class="section-note">各数据源头名按源内热度加权</span></div>
  <div class="top3-grid">{"".join(cards)}</div>
</section>''')

    body.append(ad_slot("header", "horizontal"))

    # 币圈行情
    body.append(crypto_html(snap.get("crypto", [])))

    # 各数据源热榜
    for key in config.SOURCE_META:
        section = source_section_html(key, snap, limit=8, prefix=prefix)
        if section:
            body.append(section)

    # 自动点评
    paras = make_commentary(snap, prefix=prefix)
    if paras:
        body.append(f'''<section class="section commentary">
  <div class="section-head"><h2>🤖 今日自动点评</h2>
  <span class="section-note">由程序根据榜单数据自动生成</span></div>
  {"".join(f"<p>{p}</p>" for p in paras)}
</section>''')

    # 热词
    body.append(tag_cloud_html(collect_tags(snap)[:40], prefix=prefix))

    body.append(ad_slot("incontent", "horizontal"))

    # 昨日/前后归档导航
    return "".join(body)


def build_index(snaps):
    if not snaps:
        return
    latest = snaps[0]
    body = digest_body(latest, True)
    yesterday = (datetime.strptime(latest["date"], "%Y-%m-%d")
                 - timedelta(days=1)).strftime("%Y-%m-%d")
    has_yesterday = any(s["date"] == yesterday for s in snaps)
    if has_yesterday:
        body += (f'<a class="yesterday-card" href="archive/{yesterday}.html">'
                 f'<span>📅 昨天看什么？</span>'
                 f'<strong>{date_label(yesterday)} 热点归档 →</strong></a>')
    body += ad_slot("footer", "horizontal")

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": config.SITE_NAME,
        "alternateName": config.SITE_NAME_EN,
        "url": config.SITE_DOMAIN,
        "description": config.SITE_DESC,
        "inLanguage": "zh-CN",
    }, ensure_ascii=False)
    desc = f"{date_label(latest['date'])}全球热点：Hacker News、GitHub、V2EX 等六大热榜自动聚合速览。"
    write_page("index.html", page_shell(
        f"{date_label(latest['date'])} 全球热点速览", desc, "index.html",
        body, prefix="", active="today", jsonld=jsonld,
        og_image=f"{config.SITE_DOMAIN.rstrip('/')}/og/{latest['date']}.png"))


def build_sources_page(snaps):
    latest = snaps[0] if snaps else None
    cards = []
    for key, meta in config.SOURCE_META.items():
        count = len(latest["sources"].get(key, {}).get("items", [])) if latest else 0
        cards.append(f'''<a class="source-card" href="source/{key}.html" style="--c:{meta["color"]}">
  <div class="source-card-head">
    <span class="src-badge lg" style="--c:{meta["color"]}">{esc(meta["short"])}</span>
    <strong>{esc(meta["name"])}</strong>
  </div>
  <p>{esc(meta["desc"])}</p>
  <div class="source-card-foot">
    <span>今日 {count} 条</span>
    <span class="source-card-link">查看榜单 →</span>
  </div>
</a>''')
    body = f'''<section class="section">
  <div class="section-head"><h2>📡 数据源</h2>
  <span class="section-note">全部免费公开 API · 无需密钥 · 每日自动抓取</span></div>
  <div class="source-grid">{"".join(cards)}</div>
</section>
{ad_slot("incontent", "horizontal")}'''
    write_page("sources.html", page_shell(
        "数据源", "热点雷达的六大免费数据源介绍：Hacker News、GitHub、V2EX、Reddit、DEV、Lobsters。",
        "sources.html", body, active="sources"))


def build_source_page(snaps, key):
    meta = config.SOURCE_META[key]
    latest = snaps[0] if snaps else None
    items = latest["sources"].get(key, {}).get("items", []) if latest else []
    body = [breadcrumb_html("../", [("数据源", "../sources.html"), (meta["name"], None)])]
    body.append(f'''<section class="section source-hero" style="--c:{meta["color"]}">
  <div class="source-hero-head">
    <span class="src-badge lg" style="--c:{meta["color"]}">{esc(meta["short"])}</span>
    <div>
      <h1>{esc(meta["name"])} <span class="src-label">{esc(meta["label"])}</span></h1>
      <p>{esc(meta["desc"])}</p>
    </div>
  </div>
  <div class="source-hero-meta">
    <a href="{esc(meta["site"])}" target="_blank" rel="noopener nofollow">访问官网 ↗</a>
    <span>今日收录 {len(items)} 条</span>
  </div>
</section>''')
    body.append(ad_slot("header", "horizontal"))
    if items:
        body.append(f'<section class="section"><div class="section-head"><h2>完整榜单</h2>'
                    f'<span class="section-note">按热度排序</span></div>'
                    f'{hot_list_html(key, items[:30])}</section>')
    else:
        body.append('<section class="section empty-note"><p>该数据源今日暂未抓取到数据，'
                    '可能由于网络限制，明日会自动重试。</p></section>')
    body.append(ad_slot("incontent", "horizontal"))
    # 其他数据源导航
    others = [k for k in config.SOURCE_META if k != key]
    chips = "".join(
        f'<a class="tag-chip" href="{k}.html">{esc(config.SOURCE_META[k]["name"])}</a>'
        for k in others)
    body.append(f'<section class="section"><div class="section-head"><h2>其他数据源</h2></div>'
                f'<div class="tag-cloud">{chips}</div></section>')
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"{meta['name']}热榜",
        "url": f"{config.SITE_DOMAIN.rstrip('/')}/source/{key}.html",
        "inLanguage": "zh-CN",
    }, ensure_ascii=False)
    write_page(f"source/{key}.html", page_shell(
        f"{meta['name']}热榜", f"{meta['name']}：{meta['desc']}",
        f"source/{key}.html", "".join(body), prefix="../", active="sources",
        jsonld=jsonld))


def build_archive_page(snaps):
    rows = []
    for snap in snaps:
        best = top_headline(snap)
        headline = esc(best[1]["title"]) if best else "暂无数据"
        rows.append(
            f'<a class="archive-row" href="archive/{snap["date"]}.html">'
            f'<span class="archive-date">{date_label(snap["date"])} {weekday_of(snap["date"])}</span>'
            f'<span class="archive-headline">{headline}</span>'
            f'<span class="archive-count">{total_items(snap)} 条</span></a>')
    body = f'''<section class="section">
  <div class="section-head"><h2>🗂️ 历史归档</h2>
  <span class="section-note">共 {len(snaps)} 天 · 每日自动生成 · 历史热点可追溯</span></div>
  <div class="archive-list">{"".join(rows)}</div>
</section>
{ad_slot("incontent", "horizontal")}'''
    write_page("archive.html", page_shell(
        "历史归档", "热点雷达历史归档：每日全球热榜完整记录。",
        "archive.html", body, active="archive"))


def build_archive_day(snap, snaps):
    date = snap["date"]
    body = [breadcrumb_html("../", [("历史归档", "../archive.html"),
                                 (date_label(date), None)])]
    body.append(digest_body(snap, False, prefix="../"))
    body.append(ad_slot("footer", "horizontal"))
    # 上/下一天导航
    idx = next((i for i, s in enumerate(snaps) if s["date"] == date), None)
    nav = []
    if idx is not None and idx + 1 < len(snaps):
        prev = snaps[idx + 1]["date"]
        nav.append(f'<a class="day-nav prev" href="{prev}.html">← {date_label(prev)}</a>')
    if idx is not None and idx > 0:
        nxt = snaps[idx - 1]["date"]
        nav.append(f'<a class="day-nav next" href="{nxt}.html">{date_label(nxt)} →</a>')
    if nav:
        body.append(f'<nav class="day-nav-bar">{"".join(nav)}</nav>')

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"{date_label(date)}全球热点归档",
        "url": f"{config.SITE_DOMAIN.rstrip('/')}/archive/{date}.html",
        "inLanguage": "zh-CN",
    }, ensure_ascii=False)
    desc = f"{date_label(date)}全球热点归档：Hacker News、GitHub、V2EX 等六大热榜完整记录。"
    write_page(f"archive/{date}.html", page_shell(
        f"{date_label(date)} 热点归档", desc, f"archive/{date}.html",
        "".join(body), prefix="../", active="archive", jsonld=jsonld,
        og_image=f"{config.SITE_DOMAIN.rstrip('/')}/og/{date}.png"))


def build_tag_pages(snaps):
    recent = snaps[:7]
    counts = {}
    tag_items = {}
    for snap in recent:
        for key, src in snap["sources"].items():
            for it in src["items"]:
                for t in it.get("tags", []):
                    t = (t or "").strip()
                    if not t:
                        continue
                    counts[t] = counts.get(t, 0) + 1
                    tag_items.setdefault(t, []).append((snap["date"], key, it))
    top_tags = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:40]
    used_names = set()
    for tag, _cnt in top_tags:
        items = tag_items[tag][:30]
        lis = []
        for d, key, it in items:
            lis.append(hot_item_html(key, it, len(lis) + 1, show_date=d, date_prefix="../"))
        body = [breadcrumb_html("../", [("热词", "../archive.html"), (tag, None)])]
        body.append(f'''<section class="section">
  <div class="section-head"><h2>🏷️ 标签：{esc(tag)}</h2>
  <span class="section-note">最近 7 天 {len(tag_items[tag])} 条相关内容</span></div>
  <ol class="hot-list">{"".join(lis)}</ol>
</section>
{ad_slot("incontent", "horizontal")}''')
        fname = tag_filename(tag)
        while fname in used_names:
            fname += "-2"
        used_names.add(fname)
        path = "tag/" + fname + ".html"
        write_page(path, page_shell(
            f"标签：{tag}", f"热点雷达标签「{tag}」：最近 7 天相关热点聚合。",
            path, "".join(body), prefix="../"))


ABOUT_BODY = """
<section class="section prose">
  <h1>关于热点雷达</h1>
  <p><strong>热点雷达（HotRadar）</strong>是一个全自动的全球科技热点聚合站。我们没有编辑团队，
  所有内容由程序每日定时从各大平台的公开接口抓取、聚合、排序后自动生成，
  帮助中文读者用最少的时间追踪全球技术圈当天最值得关注的信息。</p>

  <h2>工作原理</h2>
  <ol>
    <li><strong>每日 06:00（北京时间）</strong>，云端任务自动从 6 个免费公开 API 抓取当日热榜数据；</li>
    <li>程序对多源数据做统一结构化处理，按热度排序，并自动生成当日点评文字；</li>
    <li>静态页面生成器产出全站 HTML（含归档页、标签页、RSS、站点地图），自动部署上线；</li>
    <li>整个过程无需人工干预，历史数据逐日累积，形成可追溯的热点档案库。</li>
  </ol>

  <h2>数据来源</h2>
  <p>本站数据全部来自各平台公开接口，版权归原平台与原作者所有。本站仅做索引与摘要展示，
  所有条目均附原文链接，点击后将跳转至原始页面。如权利人认为相关内容不宜展示，请联系我们，会及时处理。</p>

  <h2>技术栈</h2>
  <p>Python（抓取 + 静态生成）、GitHub Actions（每日定时自动化）、GitHub Pages（全球 CDN 托管）、
  零数据库、零后端服务，全站静态页面，打开速度快且安全。</p>

  <h2>商业化</h2>
  <p>本站通过 Google AdSense 展示广告获得收入，用于覆盖域名与服务器成本；页面中如出现联盟推广链接，
  均会明确标注。广告收入不影响内容选取，排序完全由各平台公开的热度数据决定。</p>

  <h2>联系我们</h2>
  <p>意见反馈、内容纠错或商务合作，请见 <a href="contact.html">联系我们</a> 页面。</p>
</section>
"""

PRIVACY_BODY = """
<section class="section prose">
  <h1>隐私政策</h1>
  <p>更新日期：{date}。热点雷达（以下简称"本站"）非常重视用户隐私。本政策说明本站如何收集、使用和保护信息。</p>

  <h2>一、我们收集的信息</h2>
  <p>本站为纯静态内容站点，不要求注册登录，不主动收集任何个人身份信息。
  我们可能通过第三方服务获取匿名的聚合统计数据（如页面浏览量、来源地区），用于改进内容。</p>

  <h2>二、Cookie 与广告</h2>
  <p>本站使用 Google AdSense 展示广告。Google 作为第三方供应商，会使用 Cookie（包括 DoubleClick DART Cookie）
  根据您访问本站及其他网站的行为投放个性化广告。</p>
  <ul>
    <li>Google 对 Cookie 的使用遵循其隐私政策：<a href="https://policies.google.com/technologies/ads" target="_blank" rel="noopener nofollow">Google 广告技术说明</a>；</li>
    <li>您可以通过 <a href="https://adssettings.google.com" target="_blank" rel="noopener nofollow">Google 广告设置</a> 关闭个性化广告；</li>
    <li>您也可以访问 <a href="https://www.aboutads.info/choices/" target="_blank" rel="noopener nofollow">aboutads.info</a> 退出部分第三方供应商的个性化广告。</li>
  </ul>
  <p>此外，本站使用浏览器 localStorage 保存您的深浅色模式偏好，该数据仅存储在您的设备本地。</p>

  <h2>三、第三方链接</h2>
  <p>本站条目均链接至第三方网站（Hacker News、GitHub、V2EX 等）。这些网站有独立的隐私政策，
  我们不对其内容与行为负责。</p>

  <h2>四、日志</h2>
  <p>托管服务商（GitHub/Microsoft）可能会记录标准的服务器访问日志（IP 地址、浏览器类型、访问时间等），
  用于安全防护与故障排查，我们不会将其用于个人识别。</p>

  <h2>五、政策更新</h2>
  <p>本政策如有更新，将在本页面发布。继续使用本站即表示您接受更新后的政策。</p>

  <h2>六、联系我们</h2>
  <p>如对本政策有任何疑问，请通过 <a href="contact.html">联系我们</a> 页面与我们取得联系。</p>
</section>
"""

CONTACT_BODY = """
<section class="section prose">
  <h1>联系我们</h1>
  <p>对本站的内容纠错、功能建议、侵权投诉或商务合作，欢迎通过以下方式联系：</p>
  <div class="contact-cards">
    <div class="contact-card">
      <h3>📧 电子邮件</h3>
      <p><a href="mailto:{email}">{email}</a></p>
      <p class="contact-note">一般 1-3 个工作日内回复</p>
    </div>
    <div class="contact-card">
      <h3>💼 商务合作</h3>
      <p>广告投放、软文合作、链接交换等，请发送邮件至上述邮箱，标题注明【合作】。</p>
    </div>
    <div class="contact-card">
      <h3>🐙 开源社区</h3>
      <p>本站由开源工具链构建，欢迎在 GitHub 上提交 Issue 反馈问题。</p>
    </div>
  </div>
  <h2>侵权与内容处理</h2>
  <p>若您认为本站聚合的某条内容侵犯了您的权益，请提供原文链接与权利证明发送至上述邮箱，
  我们会在核实后及时处理（移除或添加来源标注）。</p>
</section>
"""


def build_static_pages():
    domain = config.SITE_DOMAIN.rstrip("/")
    date = datetime.now().strftime("%Y年%m月%d日")

    write_page("about.html", page_shell(
        "关于我们", "热点雷达是什么：全自动全球科技热点聚合站的工作原理与介绍。",
        "about.html", ABOUT_BODY, active="about"))
    write_page("privacy.html", page_shell(
        "隐私政策", "热点雷达隐私政策：信息收集、Cookie 与 Google AdSense 广告说明。",
        "privacy.html", PRIVACY_BODY.format(date=date)))
    write_page("contact.html", page_shell(
        "联系我们", "联系热点雷达：邮件、商务合作与侵权处理渠道。",
        "contact.html", CONTACT_BODY.format(email=config.CONTACT_EMAIL)))
    write_page("404.html", page_shell(
        "页面不存在", "抱歉，您访问的页面不存在。", "404.html", """
<section class="section empty-note">
  <h1>404 · 页面不存在</h1>
  <p>您访问的页面可能已被移动或从未存在。</p>
  <p><a class="btn" href="index.html">返回今日热点</a>
     <a class="btn ghost" href="archive.html">浏览历史归档</a></p>
</section>
""", active=""))


def build_sitemap(snaps):
    domain = config.SITE_DOMAIN.rstrip("/")
    urls = []

    def add(path, priority="0.6", freq="daily"):
        urls.append(f"  <url><loc>{domain}/{path}</loc>"
                    f"<changefreq>{freq}</changefreq><priority>{priority}</priority></url>")

    add("index.html", "1.0")
    add("sources.html", "0.8")
    add("archive.html", "0.8")
    add("about.html", "0.4", "yearly")
    add("privacy.html", "0.4", "yearly")
    add("contact.html", "0.4", "yearly")
    for key in config.SOURCE_META:
        add(f"source/{key}.html", "0.7")
    for snap in snaps:
        add(f"archive/{snap['date']}.html", "0.6")
    # 标签页
    for f in sorted(os.listdir(config.OUTPUT_DIR + "/tag")):
        if f.endswith(".html"):
            add(f"tag/{f}", "0.5")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    write_page("sitemap.xml", xml)


def build_robots():
    domain = config.SITE_DOMAIN.rstrip("/")
    content = (f"User-agent: *\nAllow: /\n\n"
               f"Sitemap: {domain}/sitemap.xml\n")
    write_page("robots.txt", content)


def build_feed(snaps):
    domain = config.SITE_DOMAIN.rstrip("/")
    items_xml = []
    for snap in snaps[:20]:
        date = snap["date"]
        lis = []
        for key, src in snap["sources"].items():
            for it in src["items"][:5]:
                lis.append(f'<li><a href="{esc(it.get("url", "#"))}">{esc(it.get("title", ""))}</a>'
                           f'（{esc(config.SOURCE_META.get(key, {}).get("name", key))}）</li>')
        desc = f"<![CDATA[<p>{date_label(date)}全球热点速览：</p><ul>{''.join(lis)}</ul>]]>"
        items_xml.append(
            f"  <item>\n"
            f"    <title>{esc(config.SITE_NAME)}：{date_label(date)}全球热点</title>\n"
            f"    <link>{domain}/archive/{date}.html</link>\n"
            f"    <description>{desc}</description>\n"
            f"    <guid isPermaLink=\"true\">{domain}/archive/{date}.html</guid>\n"
            f"  </item>")
    rss = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
           f'<channel>\n'
           f'  <title>{esc(config.SITE_NAME)}</title>\n'
           f'  <link>{domain}/</link>\n'
           f'  <description>{esc(config.SITE_DESC)}</description>\n'
           f'  <language>zh-cn</language>\n'
           f'  <atom:link href="{domain}/feed.xml" rel="self" type="application/rss+xml"/>\n'
           + "\n".join(items_xml) +
           f'\n</channel>\n</rss>\n')
    write_page("feed.xml", rss)


def build_ads_txt():
    if config.ADSENSE_CLIENT:
        pub = config.ADSENSE_CLIENT.replace("ca-pub-", "pub-")
        content = f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n"
    else:
        content = ("# 配置 AdSense 后取消下一行注释并填入你的发布商 ID\n"
                   "# google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0\n")
    write_page("ads.txt", content)


def build_og_images(snaps):
    if not config.OG_ENABLED or og_mod is None:
        print("  [skip] OG 图生成（Pillow 不可用或已关闭）")
        return
    ok = 0
    for snap in snaps[:config.OG_DAYS]:
        try:
            og_mod.generate(snap, os.path.join(config.OUTPUT_DIR, "og"))
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] OG 图生成失败 {snap['date']}: {e}")
    # 默认分享图 = 最新一天
    if snaps:
        try:
            og_mod.generate(snaps[0], os.path.join(config.OUTPUT_DIR, "og"),
                            filename="default.png")
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 默认 OG 图生成失败: {e}")
    print(f"  [ok] OG 图 {ok} 张")


def main():
    snaps = load_snapshots()
    if not snaps:
        print("[build] 错误：data/ 目录下没有数据快照，请先运行 python src/fetch.py")
        sys.exit(1)

    # 清理并重建输出目录
    if os.path.isdir(config.OUTPUT_DIR):
        shutil.rmtree(config.OUTPUT_DIR)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # 复制静态资源
    if os.path.isdir(config.ASSETS_DIR):
        shutil.copytree(config.ASSETS_DIR, os.path.join(config.OUTPUT_DIR, "assets"))
    # favicon 放到根目录
    favicon_src = os.path.join(config.ASSETS_DIR, "favicon.svg")
    if os.path.exists(favicon_src):
        shutil.copy(favicon_src, os.path.join(config.OUTPUT_DIR, "favicon.svg"))

    print(f"[build] HotRadar 构建 · {len(snaps)} 天数据")
    build_index(snaps)
    build_sources_page(snaps)
    for key in config.SOURCE_META:
        build_source_page(snaps, key)
    build_archive_page(snaps)
    for snap in snaps:
        build_archive_day(snap, snaps)
    build_tag_pages(snaps)
    build_static_pages()
    build_og_images(snaps)
    build_sitemap(snaps)
    build_robots()
    build_feed(snaps)
    build_ads_txt()

    n_pages = sum(len(files) for _, _, files in os.walk(config.OUTPUT_DIR))
    print(f"[build] 完成：{n_pages} 个文件 -> {config.OUTPUT_DIR}")


if __name__ == "__main__":
    main()
