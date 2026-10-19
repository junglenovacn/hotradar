# -*- coding: utf-8 -*-
"""
HotRadar 站点配置 —— 部署前只需要改这个文件
"""

import os

# ==================== 基本信息 ====================
SITE_NAME = "热点雷达"
SITE_NAME_EN = "HotRadar"
SITE_TAGLINE = "全球热点 · 每日自动聚合"
# 部署后改成你的真实域名（先用 GitHub Pages 默认域名也行，如 https://你的用户名.github.io）
SITE_DOMAIN = "https://hotradar.github.io"
SITE_DESC = ("热点雷达：每日自动聚合 Hacker News、GitHub、V2EX、Reddit、DEV、Lobsters "
             "六大全球热榜，中文读者一站式追踪科技热点，内容全自动更新。")
SITE_KEYWORDS = "热榜,科技热点,Hacker News,GitHub Trending,V2EX,技术资讯,每日热榜,自动聚合"
LANG = "zh-CN"
TIMEZONE_OFFSET = 8  # 北京时间（GitHub Actions 运行在 UTC，需要 +8）
AUTHOR = "HotRadar"
CONTACT_EMAIL = "hotradar@example.com"   # 改成你的邮箱
GITHUB_REPO = ""                          # 例如 yourname/hotradar（展示在关于页）

# ==================== 变现配置 ====================
# Google AdSense 客户端编号（审核通过后填写，形如 ca-pub-1234567890123456）
# 留空则全站显示"广告位占位"，不会报错
ADSENSE_CLIENT = ""
# 各广告位 slot ID（在 AdSense 后台创建广告单元后可选填写）
AD_SLOTS = {
    "header": "",
    "incontent": "",
    "sidebar": "",
    "footer": "",
}
# 联盟推广位（可选）：填写后首页展示，赚 CPS 佣金
AFFILIATE_LINKS = [
    # {"title": "Vultr 云服务器", "url": "https://www.vultr.com/?ref=xxxx",
    #  "desc": "注册送 $100 额度", "tag": "赞助"},
]

# ==================== 目录 ====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# ==================== 数据源元信息 ====================
SOURCE_META = {
    "hackernews": {
        "name": "Hacker News", "short": "HN", "label": "今日热榜", "color": "#ff6600",
        "site": "https://news.ycombinator.com",
        "desc": "全球技术创业者与工程师社区 Y Combinator 的投票热榜，科技风向标。",
    },
    "github": {
        "name": "GitHub", "short": "GH", "label": "本周新星项目", "color": "#5b21b6",
        "site": "https://github.com",
        "desc": "过去 7 天获得 Star 最多的新开源项目，按 Star 数排序。",
    },
    "v2ex": {
        "name": "V2EX", "short": "V2", "label": "社区热帖", "color": "#1f8dd6",
        "site": "https://www.v2ex.com",
        "desc": "中文创意工作者社区热点，分享探索、技术、职场与生活。",
    },
    "reddit": {
        "name": "Reddit", "short": "RD", "label": "技术热帖", "color": "#ff4500",
        "site": "https://www.reddit.com",
        "desc": "r/programming 与 r/technology 版块当前最热帖子。",
    },
    "devto": {
        "name": "DEV 社区", "short": "DEV", "label": "本周精选", "color": "#0ea5e9",
        "site": "https://dev.to",
        "desc": "开发者社区本周最受欢迎的技术文章。",
    },
    "lobsters": {
        "name": "Lobsters", "short": "LOB", "label": "技术链接榜", "color": "#ac1300",
        "site": "https://lobste.rs",
        "desc": "面向程序员的技术链接聚合站，以讨论质量著称。",
    },
}

# ==================== OG 分享图 ====================
OG_ENABLED = True
OG_DAYS = 30  # 只为最近 N 天生成分享图，控制构建体积
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
