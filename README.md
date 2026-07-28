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

## 当前报告

| 报告 | 日期 | 论文数 | 产品数 | 版本 |
|------|------|--------|--------|------|
| 歌声合成技术演进与方案调研 | 2026.07 | 111 | 35 | V3 |
