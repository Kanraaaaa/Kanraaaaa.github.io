# Research Hub — 深度研究主页

## 结构

```
github-pages/
├── index.html                    # 首页（报告卡片列表）
└── research/
    └── svs-survey-v3.html         # 歌声合成技术调研报告
```

## 如何添加新报告

1. 把新的 HTML 报告放到 `research/` 目录，例如 `research/my-new-report.html`
2. 在 `index.html` 的 `researchGrid` 区域，复制一个 `<a class="research-card">` 卡片，修改链接、标题、描述、标签
3. 提交推送即可

### 示例：添加新报告卡片

在 `index.html` 的 `<div class="research-grid" id="researchGrid">` 内添加：

```html
<a class="research-card" href="research/my-new-report.html" data-tags="ai,svs">
  <div class="card-glow" style="background: linear-gradient(90deg, #10b981, #22d3ee);"></div>
  <div class="card-icon">🔊</div>
  <h3>报告标题</h3>
  <p class="card-desc">报告简介描述...</p>
  <div class="card-tags">
    <span class="tag tag-ai">AI</span>
    <span class="tag tag-survey">调研</span>
  </div>
  <div class="card-meta" style="margin-top:12px;">
    <span class="meta-item">📅 2026.08</span>
    <span class="meta-item">📄 50 篇论文</span>
  </div>
</a>
```

## 部署到 GitHub Pages

1. 创建仓库 `<你的用户名>.github.io`（必须 Public）
2. 把 `github-pages/` 目录下所有文件推送上去
3. 等待 1-2 分钟，访问 `https://<你的用户名>.github.io`

## 趋势周报自动更新

`.github/workflows/weekly-trends.yml` 每周一北京时间 08:30 运行，采集刚结束的完整 ISO 周，并将周报 HTML、来源快照、首页最新入口和归档列表提交到 `main`。GitHub Pages 从该分支发布后，主页即可看到新一期。

采集来源：

- GitHub Trending 周榜：项目发现和榜单星数（仅在源页面提供时记录）
- arXiv API：`cs.AI`、`cs.CL`、`cs.LG`、`cs.DC`、`cs.SE` 本周新稿
- Hugging Face Papers：逐日热榜，单独记录最佳排名、上榜天数和票数
- GitHub Releases Atom：vLLM Ascend、Triton-Ascend、Ascend for PyTorch、SGLang Ascend、vLLM 和 SGLang
- 科技 RSS/Atom：OpenAI News、Google DeepMind、Hugging Face Blog、NVIDIA Developer、GitHub Blog、Simon Willison，以及机器之心（第三方转换源）；每周条目按发布时间过滤，媒体内容作为线索
- 优质文章页：从 Simon Willison、Jeff Geerling、Mitchell Hashimoto、Paul Graham 的博客源整理每周最多 5 篇阅读候选，并保留来源背景和原文链接

每期原始结构化快照保存在 `trends/data/`，HTML 报告保存在 `trends/`。如需手动补生成某周，可在 GitHub Actions 中运行 **Weekly ecosystem trends** 并输入 ISO 周，例如 `2026-W45`。

主页的“优质文章”入口指向 `trends/reading.html`。该页从周报快照归档精选博客条目；只纳入小型作者清单，不导入完整的 92 源 OPML。

## 当前报告

| 报告 | 日期 | 论文数 | 产品数 | 版本 |
|------|------|--------|--------|------|
| 歌声合成技术演进与方案调研 | 2026.07 | 111 | 35 | V3 |
