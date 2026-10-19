#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HotRadar 数据抓取引擎
====================
从 6 个免费公开 API 抓取全球热榜，每个数据源独立容错：
单源失败只记录警告，绝不影响其他数据源和整体构建。

数据源（全部免费、无需 API Key）：
  - Hacker News    Firebase 官方 API
  - GitHub         Search API（未认证 10 次/分钟，每天 1 次足够）
  - V2EX           公开 JSON API（中文技术社区）
  - Reddit         公开 .json 端点
  - DEV Community  公开 API
  - Lobsters       公开 JSON
  - CoinGecko      公开行情 API

用法：
  python src/fetch.py
输出：
  data/YYYY-MM-DD.json   当日快照
  data/latest.json       最新快照
"""
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

UA = "HotRadarBot/1.0 (+https://github.com/; automated trending aggregator)"
TIMEOUT = 15
TZ = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
TODAY = datetime.now(TZ).strftime("%Y-%m-%d")
TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(s):
    return html_mod.unescape(TAG_RE.sub("", s or "")).strip()


def http_get(url, retries=2):
    """带重试的 JSON GET，失败返回 None"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    print(f"    [warn] GET 失败 {url[:70]} -> {last_err}")
    return None


def now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def norm(item):
    """统一条目结构"""
    base = {"title": "", "url": "", "score": 0, "comments": 0, "author": "",
            "tags": [], "desc": "", "time": now_ts(), "id": ""}
    base.update({k: v for k, v in item.items() if k in base})
    return base


def parse_iso(ts_str):
    """解析 ISO 时间串为 unix 时间戳"""
    try:
        return int(datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                   .replace(tzinfo=timezone.utc).timestamp())
    except Exception:  # noqa: BLE001
        return now_ts()


# ---------------- 各数据源 ----------------

def fetch_hackernews(limit=20):
    ids = http_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not ids:
        return []
    ids = ids[:limit]

    def one(i):
        return http_get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")

    with ThreadPoolExecutor(max_workers=8) as pool:
        raw = list(pool.map(one, ids))
    items = []
    for i, it in zip(ids, raw):
        if not it or it.get("type") != "story" or not it.get("title"):
            continue
        items.append(norm({
            "title": it["title"],
            "url": it.get("url") or f"https://news.ycombinator.com/item?id={i}",
            "score": it.get("score", 0),
            "comments": it.get("descendants", 0),
            "author": it.get("by", ""),
            "tags": [],
            "desc": "",
            "time": it.get("time", now_ts()),
            "id": str(i),
        }))
    return items


def fetch_github(limit=20):
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    qs = urllib.parse.urlencode({
        "q": f"created:>{week_ago} stars:>10",
        "sort": "stars", "order": "desc", "per_page": limit,
    })
    data = http_get(f"https://api.github.com/search/repositories?{qs}")
    if not data or "items" not in data:
        return []
    items = []
    for r in data["items"]:
        items.append(norm({
            "title": r["full_name"],
            "url": r["html_url"],
            "score": r.get("stargazers_count", 0),
            "comments": r.get("open_issues_count", 0),
            "author": (r.get("owner") or {}).get("login", ""),
            "tags": [r["language"]] if r.get("language") else [],
            "desc": r.get("description") or "",
            "time": parse_iso(r.get("created_at", "")),
            "id": str(r.get("id", "")),
        }))
    return items


def fetch_v2ex(limit=20):
    data = http_get("https://www.v2ex.com/api/topics/hot.json")
    if not isinstance(data, list) or not data:
        return []
    items = []
    for t in data[:limit]:
        node = t.get("node") or {}
        items.append(norm({
            "title": t.get("title", ""),
            "url": t.get("url", ""),
            "score": 0,
            "comments": t.get("replies", 0),
            "author": (t.get("member") or {}).get("username", ""),
            "tags": [node["title"]] if node.get("title") else [],
            "desc": strip_tags(t.get("content") or "")[:160],
            "time": t.get("created", now_ts()),
            "id": str(t.get("id", "")),
        }))
    return items


def fetch_reddit(limit=15):
    items = []
    for sub in ("programming", "technology"):
        data = http_get(f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}")
        if not data or "data" not in data:
            continue
        for c in data["data"].get("children", []):
            d = c.get("data") or {}
            if d.get("stickied") or not d.get("title"):
                continue
            url = d.get("url_overridden_by_dest") or (
                "https://www.reddit.com" + d.get("permalink", ""))
            items.append(norm({
                "title": d["title"],
                "url": url,
                "score": d.get("score", 0),
                "comments": d.get("num_comments", 0),
                "author": d.get("author", ""),
                "tags": [f"r/{sub}"],
                "desc": strip_tags(d.get("selftext") or "")[:200],
                "time": int(d.get("created_utc", now_ts())),
                "id": d.get("id", ""),
            }))
        time.sleep(1)
    return items[:limit]


def fetch_devto(limit=15):
    data = http_get(f"https://dev.to/api/articles?top=7&per_page={limit}")
    if not isinstance(data, list) or not data:
        return []
    items = []
    for a in data[:limit]:
        items.append(norm({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "score": a.get("positive_reactions_count", 0),
            "comments": a.get("comments_count", 0),
            "author": (a.get("user") or {}).get("name", ""),
            "tags": a.get("tag_list") or [],
            "desc": a.get("description") or "",
            "time": parse_iso(a.get("published_timestamp", "")),
            "id": str(a.get("id", "")),
        }))
    return items


def fetch_lobsters(limit=15):
    data = http_get("https://lobste.rs/hottest.json")
    if not isinstance(data, list) or not data:
        return []
    items = []
    for s in data[:limit]:
        items.append(norm({
            "title": s.get("title", ""),
            "url": s.get("url") or s.get("short_id_url", ""),
            "score": s.get("score", 0),
            "comments": s.get("comment_count", 0),
            "author": s.get("submitter_user", ""),
            "tags": s.get("tags") or [],
            "desc": s.get("description") or "",
            "time": parse_iso(s.get("created_at", "")),
            "id": s.get("short_id", ""),
        }))
    return items


def fetch_crypto():
    coins = [("bitcoin", "BTC 比特币"), ("ethereum", "ETH 以太坊"),
             ("binancecoin", "BNB 币安币"), ("solana", "SOL"),
             ("ripple", "XRP 瑞波"), ("dogecoin", "DOGE"),
             ("cardano", "ADA 艾达"), ("tron", "TRX 波场")]
    ids = ",".join(c[0] for c in coins)
    data = http_get(
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=cny&include_24hr_change=true")
    out = []
    if not data:
        return out
    for cid, name in coins:
        d = data.get(cid)
        if not d:
            continue
        out.append({"id": cid, "name": name, "cny": d.get("cny", 0),
                    "change": d.get("cny_24h_change", 0)})
    return out


FETCHERS = {
    "hackernews": fetch_hackernews,
    "github": fetch_github,
    "v2ex": fetch_v2ex,
    "reddit": fetch_reddit,
    "devto": fetch_devto,
    "lobsters": fetch_lobsters,
}


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    print(f"[fetch] HotRadar 数据抓取 · {TODAY} (北京时间)")
    sources = {}
    for key, fn in FETCHERS.items():
        try:
            items = fn()
        except Exception as e:  # noqa: BLE001
            print(f"  [error] {key} 异常: {e}")
            items = []
        sources[key] = {"items": items}
        print(f"  [ok] {key}: {len(items)} 条")
    crypto = fetch_crypto()
    print(f"  [ok] crypto: {len(crypto)} 个币种")

    snapshot = {
        "date": TODAY,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "sources": sources,
        "crypto": crypto,
    }
    path = os.path.join(config.DATA_DIR, f"{TODAY}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    with open(os.path.join(config.DATA_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    total = sum(len(s["items"]) for s in sources.values())
    print(f"[fetch] 完成：共 {total} 条 -> {path}")


if __name__ == "__main__":
    main()
