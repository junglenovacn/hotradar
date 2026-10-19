# 热点雷达 HotRadar

> 每日自动聚合全球六大技术热榜的静态站点 —— 内容生产全自动，靠 AdSense 广告变现。

## 这是什么

一个**全自动内容站**：每天定时从 6 个免费公开 API 抓取热榜数据（Hacker News、GitHub Trending、V2EX、Reddit、dev.to、Lobsters），由 Python 程序自动生成完整静态网站（含自动点评、热词标签、OG 分享图、RSS），通过 GitHub Actions 每天 06:00（北京时间）自动抓取 → 构建 → 部署到 GitHub Pages。**零服务器成本、零人工维护**。

线上形态：`https://<你的用户名>.github.io/<仓库名>/`

## 目录结构

```
site1-hotradar/
├── src/
│   ├── config.py      # 站点配置（域名、数据源、广告位）
│   ├── fetch.py       # 抓取引擎：6 个数据源，独立容错/超时/重试
│   ├── og.py          # OG 分享图生成（Pillow，1200x630）
│   └── build.py       # 静态站点生成器（52+ 页面）
├── assets/            # style.css / app.js / favicon.svg
├── data/              # 每日数据快照 JSON（自动回写仓库，保留 30 天）
├── output/            # 构建产物（= 部署目录）
└── .github/workflows/deploy.yml   # 每日自动化流水线
```

## 本地运行

```bash
# 1. 安装依赖（仅 Pillow）
pip install pillow

# 2. 抓取今日数据（网络不通的数据源会自动降级，不影响其他源）
python src/fetch.py

# 3. 构建静态站点
python src/build.py

# 4. 本地预览
cd output && python -m http.server 8000
```

## 部署到 GitHub Pages（免费国外空间）

1. 把本项目推送到 GitHub 仓库（`site1-hotradar` 目录内容放仓库根目录）
2. 仓库 **Settings → Pages → Source** 选 **GitHub Actions**
3. Actions 会自动运行（或手动点 **Run workflow**），几分钟后上线
4. 把 `src/config.py` 里的 `SITE_DOMAIN` 改成你的真实域名
5. 绑定自定义域名（可选）：仓库根放 `CNAME` 文件，Settings → Pages → Custom domain

## 变现路径

| 阶段 | 动作 | 预期 |
|------|------|------|
| 上线 | 提交 AdSense 审核（需先有原创内容，本站每日自动产出） | 1-3 周 |
| 过审 | 全站 4 个广告位自动展示 | 首月 ¥0-50 |
| 起量 | 每日归档页积累长尾流量，RSS 订阅 | 3-6 个月 ¥100-500/月 |
| 放大 | 同套代码复制到第二个垂直主题站 | 收益叠加 |

**广告位已预埋**：页头横幅、文内信息流、侧栏、页脚。拿到 `ca-pub-xxx` 发布商 ID 后填入 `src/config.py` 的 `ADSENSE_CLIENT`，重建即全站生效；同步取消 `ads.txt` 注释。

## 自动化流水线说明

GitHub Actions 每日做 5 件事：

1. `python src/fetch.py` — 抓 6 个数据源（每个源独立 try/except，单个源失败不拖垮全站）
2. `python src/build.py` — 生成 52+ 个静态页面 + OG 图
3. 清理 30 天前的旧快照，把今日快照 commit 回仓库（数据即资产）
4. 上传 `output/` 部署到 GitHub Pages
5. 失败自动保留昨日数据，站点永不空白

被墙的数据源（Reddit/CoinGecko/V2EX）在 GitHub Actions 的国外网络里可正常抓取；本机开发时它们会自动跳过。

## SEO 已内置

- 每个页面独立 title/description/canonical/OG
- JSON-LD 结构化数据（CollectionPage）
- sitemap.xml + robots.txt + feed.xml
- 每日自动产生的独特内容（自动点评+榜单数据），解决"内容新鲜度"
- 内链：来源页 ↔ 归档页 ↔ 标签页互链
