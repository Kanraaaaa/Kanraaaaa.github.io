#!/usr/bin/env python3
"""Collect public weekly AI/ecosystem signals and publish a static report."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRENDS = ROOT / "trends"
SNAPSHOTS = TRENDS / "data"
USER_AGENT = "Kanraaaaa-weekly-ecosystem-report/1.0 (GitHub Pages)"
TRACKS = {
    "agent": ("🤖 AI Agent / Agentic", ("agent", "agentic", "mcp", "skill", "multi-agent", "harness", "orchestrat")),
    "llm": ("🧠 LLM 训练与推理", ("llm", "inference", "training", "serving", "moe", "kv cache", "quant", "decode", "prefill", "推理", "训练")),
    "devtools": ("🛠️ 开发者工具", ("developer tool", "devtool", "compiler", "ide", "editor", "cli", "debug", "sdk", "build system", "开发工具")),
    "ecosystem": ("🌱 新兴生态", ("open source", "ecosystem", "runtime", "framework", "model", "dataset", "protocol", "robot", "multimodal", "开源", "生态")),
}
RELEASE_REPOS = [
    ("vllm-project/vllm-ascend", "vLLM Ascend", "cann"),
    ("triton-lang/triton-ascend", "Triton-Ascend", "cann"),
    ("Ascend/pytorch", "Ascend for PyTorch / torch_npu", "cann"),
    ("Ascend/ascend-sglang", "SGLang Ascend", "cann"),
    ("vllm-project/vllm", "vLLM", "llm"),
    ("sgl-project/sglang", "SGLang", "llm"),
]
ARXIV_CATEGORIES = ("cs.AI", "cs.CL", "cs.LG", "cs.DC", "cs.SE")
ATOM = {"atom": "http://www.w3.org/2005/Atom"}


def http_get(url: str, accept: str = "*/*") -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()


def get_json(url: str):
    return json.loads(http_get(url, "application/json").decode("utf-8"))


def get_text(url: str) -> str:
    return http_get(url, "text/html,application/atom+xml,application/xml;q=0.9,*/*;q=0.8").decode("utf-8", "replace")


def week_range(week: str) -> tuple[date, date]:
    year, number = map(int, week.replace("W", "-").split("-"))
    monday = date.fromisocalendar(year, number, 1)
    return monday, monday + timedelta(days=6)


def previous_week(today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    previous_sunday = today - timedelta(days=today.weekday() + 1)
    iso = previous_sunday.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def plain(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def classify(text: str) -> str:
    lowered = text.lower()
    scores = {key: sum(1 for term in terms if term in lowered) for key, (_, terms) in TRACKS.items()}
    return max(scores, key=scores.get) if max(scores.values(), default=0) else "ecosystem"


class TrendingParser(HTMLParser):
    """Extract repository rows from GitHub's public weekly trending page."""

    def __init__(self):
        super().__init__()
        self.in_article = False
        self.depth = 0
        self.parts: list[str] = []
        self.repo = ""
        self.items: list[dict] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and not self.in_article:
            self.in_article, self.depth, self.parts, self.repo = True, 1, [], ""
        elif self.in_article:
            self.depth += 1
            href = attrs.get("href", "")
            match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", href)
            if tag == "a" and match and not self.repo:
                self.repo = f"{match.group(1)}/{match.group(2)}"

    def handle_endtag(self, tag):
        if not self.in_article:
            return
        if tag == "article" and self.depth == 1:
            self._finish_article()
            self.in_article = False
            return
        self.depth = max(1, self.depth - 1)

    def handle_data(self, data):
        if self.in_article:
            self.parts.append(data)

    def _finish_article(self):
        if not self.repo:
            return
        text = plain(" ".join(self.parts))
        delta = re.search(r"([\d,]+)\s+stars?\s+this week", text, re.I)
        language = ""
        for candidate in ("Python", "TypeScript", "JavaScript", "Rust", "Go", "C++", "Java", "Shell", "Jupyter Notebook"):
            if candidate.lower() in text.lower():
                language = candidate
                break
        description = text.replace(self.repo, "", 1).strip()
        if delta:
            description = description.replace(delta.group(0), "")
        self.items.append({
            "repo": self.repo,
            "url": f"https://github.com/{self.repo}",
            "description": description[:420],
            "language": language,
            "stars_week": int(delta.group(1).replace(",", "")) if delta else None,
            "track": classify(f"{self.repo} {description}"),
            "source": "GitHub Trending · weekly snapshot",
        })


def collect_github_trending() -> tuple[list[dict], str]:
    parser = TrendingParser()
    parser.feed(get_text("https://github.com/trending?since=weekly"))
    if not parser.items:
        raise RuntimeError("GitHub Trending page returned no parseable repositories")
    return parser.items, "ok"


def collect_arxiv(start: date, end: date) -> tuple[list[dict], str]:
    categories = " OR ".join(f"cat:{category}" for category in ARXIV_CATEGORIES)
    date_query = f"submittedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"
    params = urllib.parse.urlencode({
        "search_query": f"{date_query} AND ({categories})",
        "start": 0,
        "max_results": 150,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    root = ET.fromstring(http_get(f"https://export.arxiv.org/api/query?{params}", "application/atom+xml,application/xml"))
    papers = []
    for entry in root.findall("atom:entry", ATOM):
        title = plain(entry.findtext("atom:title", default="", namespaces=ATOM))
        summary = plain(entry.findtext("atom:summary", default="", namespaces=ATOM))
        url = entry.findtext("atom:id", default="", namespaces=ATOM).strip()
        submitted = entry.findtext("atom:published", default="", namespaces=ATOM)
        categories_for_paper = [node.attrib.get("term", "") for node in entry.findall("atom:category", ATOM)]
        if not title or not url:
            continue
        papers.append({
            "id": url.rstrip("/").split("/")[-1], "title": title, "summary": summary,
            "url": url, "submitted": submitted,
            "categories": categories_for_paper,
            "track": classify(f"{title} {summary}"),
            "source": "arXiv API",
        })
    return papers, "ok"


def collect_hf_papers(start: date, end: date) -> tuple[list[dict], str]:
    by_id: dict[str, dict] = {}
    day = start
    while day <= end:
        params = urllib.parse.urlencode({"date": day.isoformat(), "sort": "trending", "limit": 100, "p": 0})
        rows = get_json(f"https://huggingface.co/api/daily_papers?{params}")
        for rank, row in enumerate(rows, 1):
            paper = row.get("paper") or row
            paper_id = paper.get("id") or row.get("id")
            if not paper_id:
                continue
            record = by_id.setdefault(paper_id, {
                "id": paper_id,
                "title": paper.get("title") or row.get("title") or "",
                "summary": plain(paper.get("summary") or row.get("summary") or ""),
                "url": f"https://huggingface.co/papers/{paper_id}",
                "arxiv_url": f"https://arxiv.org/abs/{paper_id}",
                "github": paper.get("githubRepo"),
                "upvotes": int(paper.get("upvotes", 0) or 0),
                "best_rank": rank,
                "days_on_trending": 0,
                "dates": [],
                "track": classify(f"{paper.get('title', '')} {paper.get('summary', '')}"),
                "source": "Hugging Face Papers API · daily trending",
            })
            record["days_on_trending"] += 1
            record["best_rank"] = min(record["best_rank"], rank)
            record["upvotes"] = max(record["upvotes"], int(paper.get("upvotes", 0) or 0))
            record["dates"].append(day.isoformat())
            if paper.get("githubRepo"):
                record["github"] = paper["githubRepo"]
        day += timedelta(days=1)
        time.sleep(0.15)
    papers = sorted(by_id.values(), key=lambda item: (-item["days_on_trending"], item["best_rank"], -item["upvotes"]))
    return papers, "ok"


def collect_releases(start: date, end: date) -> tuple[list[dict], list[dict]]:
    releases, statuses = [], []
    for repo, label, track in RELEASE_REPOS:
        url = f"https://github.com/{repo}/releases.atom"
        try:
            root = ET.fromstring(http_get(url, "application/atom+xml,application/xml"))
            found = 0
            for entry in root.findall("atom:entry", ATOM):
                published = entry.findtext("atom:published", default="", namespaces=ATOM) or entry.findtext("atom:updated", default="", namespaces=ATOM)
                release_date = parse_date(published)
                if not release_date or not (start <= release_date <= end):
                    continue
                title = plain(entry.findtext("atom:title", default="", namespaces=ATOM))
                link_node = entry.find("atom:link", ATOM)
                link = link_node.attrib.get("href", "") if link_node is not None else f"https://github.com/{repo}/releases"
                content = plain(entry.findtext("atom:content", default="", namespaces=ATOM) or entry.findtext("atom:summary", default="", namespaces=ATOM))
                releases.append({"repo": repo, "label": label, "title": title, "date": release_date.isoformat(), "url": link, "summary": content[:1800], "track": track, "source": f"GitHub Releases · {repo}"})
                found += 1
            statuses.append({"source": f"GitHub Releases · {repo}", "status": "ok", "items": found})
        except Exception as exc:
            statuses.append({"source": f"GitHub Releases · {repo}", "status": f"failed: {str(exc)[:160]}", "items": 0})
    return releases, statuses


def fetch_optional(name: str, collector, *args):
    try:
        items, status = collector(*args)
        return items, {"source": name, "status": status, "items": len(items)}
    except Exception as exc:
        return [], {"source": name, "status": f"failed: {str(exc)[:200]}", "items": 0}


def e(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def card(title: str, url: str, body: str, badges: list[str] | None = None, meta: str = "") -> str:
    badge_html = "".join(f'<span class="tag">{e(badge)}</span>' for badge in (badges or []))
    title_html = f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(title)}</a>' if url else e(title)
    meta_html = f'<p class="small">{e(meta)}</p>' if meta else ""
    return f'<article class="card"><h3>{title_html}</h3>{badge_html}<p>{e(body)}</p>{meta_html}</article>'


def report_html(week: str, start: date, end: date, trending: list[dict], arxiv: list[dict], hf: list[dict], releases: list[dict], statuses: list[dict]) -> str:
    counts = {key: sum(item["track"] == key for item in trending) for key in TRACKS}
    top_growth = max((item["stars_week"] for item in trending if item.get("stars_week") is not None), default=None)
    last_week_theme = ", ".join(f"{TRACKS[k][0].split(' ', 1)[1]} {v}" for k, v in counts.items() if v)
    if not last_week_theme:
        last_week_theme = "本周公开周榜未能提供可分类项目"

    sections = []
    for key, (label, _) in TRACKS.items():
        items = [repo for repo in trending if repo["track"] == key][:8]
        cards = []
        for item in items:
            badges = [item["language"]] if item.get("language") else []
            if item.get("stars_week") is not None:
                badges.append(f"+{item['stars_week']:,} stars/week")
            desc = item.get("description") or "GitHub Trending 本周榜单条目；仓库页面查看项目说明。"
            cards.append(card(item["repo"], item["url"], desc, badges, item["source"]))
        if not cards:
            cards.append(card("本周未收集到可核实条目", "", "当前公开周榜没有提供这一赛道的可分类项目；周报不会为凑数而填充候选。"))
        sections.append(f'<section><h2>{label}</h2><p class="desc">项目发现源：GitHub Trending 周榜。项目简介来自仓库列表，周增星数仅在源页面明确提供时显示。</p><div class="grid">{"".join(cards)}</div></section>')

    arxiv_cards = []
    for item in arxiv[:8]:
        arxiv_cards.append(card(item["title"], item["url"], item["summary"][:620], [item["submitted"][:10], ", ".join(item["categories"][:3])], f"arXiv:{item['id']} · 初次提交 {item['submitted'][:10]}"))
    if not arxiv_cards:
        arxiv_cards.append(card("本周未筛到匹配主题的新论文", "", "arXiv API 按 cs.AI、cs.CL、cs.LG、cs.DC、cs.SE 和本周提交日期检索；当前没有通过主题筛选的条目。"))

    hf_cards = []
    for item in hf[:6]:
        meta = f"HF 周内最佳日榜第 {item['best_rank']} · {item['days_on_trending']} 天上榜 · 最多 {item['upvotes']} 票"
        if item.get("github"):
            meta += f" · 代码：{item['github']}"
        hf_cards.append(card(item["title"], item["url"], item["summary"][:620], ["社区热度", f"arXiv:{item['id']}"], meta))
    if not hf_cards:
        hf_cards.append(card("本周 HF Papers 日榜不可用或无数据", "https://huggingface.co/papers/trending", "HF 热度作为社区注意力信号单独呈现；不将其视为论文质量评价。"))

    release_cards = []
    for item in releases:
        release_cards.append(card(f"{item['label']} · {item['title']}", item["url"], item["summary"] or "Release 条目没有附带正文摘要，请打开发布页查看变更。", [item["date"], "CANN/Ascend" if item["track"] == "cann" else "框架发布"], item["source"]))
    direct_releases = [r for r in releases if r["track"] == "cann"]
    if not direct_releases:
        release_cards.append(card("本周未发现跟踪仓库的正式 Release", "", "跟踪源包括 vLLM Ascend、Triton-Ascend、Ascend for PyTorch 和 SGLang Ascend。未发现正式 Release 不代表没有代码提交或公告。"))
    release_cards.append(card("本周新模型首发支持 CANN", "", "自动流程只把框架 Release 中明确列出的模型适配记为支持线索。模型首发支持必须另有模型发布方或昇腾官方一手证据；未核实前不会标成已支持。", ["核验规则"]))

    source_rows = "".join(f'<li><b>{e(item["source"])}</b>：{e(item["status"])}，{item["items"]} 条</li>' for item in statuses)
    failed = [item["source"] for item in statuses if item["status"].startswith("failed")]
    failure_note = "部分来源获取失败：" + "、".join(failed) if failed else "所有必需来源均成功获取。"
    source_note = f"<p class=\"notice\">{e(failure_note)} 自动收集结果用于发现线索；模型支持、性能数字与重要版本信息需回到一手发布说明核对。周增星数只在 GitHub 周榜显式提供时展示。</p>"
    date_label = f"{start.year}年{start.month}月{start.day}日 – {end.month}月{end.day}日"
    stats = f'<div class="stats"><div><div class="num">{len(trending)}</div><div class="label">GitHub 周榜候选</div></div><div><div class="num">{len(arxiv)}</div><div class="label">arXiv 本周新稿</div></div><div><div class="num">{len(hf)}</div><div class="label">HF 周内热榜论文</div></div><div><div class="num">{len(releases)}</div><div class="label">跟踪仓库 Release</div></div></div>'
    top_stat = f" · 周榜最高显示 +{top_growth:,} ⭐/周" if top_growth is not None else ""
    lead = f"本期覆盖 {date_label}。GitHub 周榜按 AI Agent、LLM 训推、开发者工具和新兴生态分类；论文区将 arXiv 新稿与 HF 社区热榜分开；昇腾观察只记录可追溯的框架发布和明确的模型支持证据。{top_stat}"
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>技术生态趋势周报 · {week}</title>
<style>
:root{{--bg:#08090a;--panel:#111315;--text:#f7f8f8;--muted:#a0a6b0;--line:#292d33;--accent:#7c83ff}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:#d4d8df;font:16px/1.65 Inter,"Noto Sans SC",system-ui,sans-serif}}.wrap{{max-width:960px;margin:auto;padding:0 24px;position:relative}}a{{color:#a5b4fc}}.back{{display:inline-block;margin-top:28px;text-decoration:none;color:var(--muted)}}header{{padding:38px 0 26px}}h1{{font-size:38px;line-height:1.2;color:var(--text);margin:16px 0 8px}}h2{{font-size:22px;color:var(--text);margin:0 0 6px}}h3{{font-size:16px;color:#fff;margin:0 0 8px}}.sub,.desc{{color:var(--muted)}}.stats{{display:flex;gap:28px;margin-top:22px;flex-wrap:wrap}}.num{{font-size:25px;color:white;font-weight:700}}.label{{font-size:12px;color:var(--muted)}}section{{padding:26px 0;border-top:1px solid var(--line)}}.lead,.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}}.lead{{border-left:3px solid var(--accent)}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.card p{{margin:0 0 8px;color:#b5bac3;font-size:14px;overflow-wrap:anywhere}}.tag{{display:inline-block;font-size:11px;color:#a5b4fc;border:1px solid #494c75;border-radius:20px;padding:1px 8px;margin:0 5px 7px 0}}.small{{font-size:12px!important;color:var(--muted)!important}}.notice{{color:#fbbf24;font-size:13px}}footer{{border-top:1px solid var(--line);margin-top:28px;padding:30px 0;color:var(--muted);font-size:13px}}@media(max-width:680px){{.grid{{grid-template-columns:1fr}}h1{{font-size:30px}}}}
</style></head><body><div class="wrap"><a class="back" href="../index.html">← 返回主页</a><header><span class="tag">自动汇总 · 来源可追溯</span><h1>技术生态趋势周报</h1><p class="sub">{week} · {date_label}</p>{stats}</header>
<section><h2>🧭 本周观察</h2><p class="desc">{e(lead)}</p><div class="lead">自动化只负责采集、分类和整理来源中的事实字段；对“支持 CANN”“性能提升”等结论，优先链接项目 Release、官方文档或论文原文。HF 热度、GitHub 周榜和论文发表分别呈现，不混成单一热度分数。</div></section>
{''.join(sections)}
<section><h2>📄 arXiv 本周新论文</h2><p class="desc">按首次提交日期检索本周 cs.AI、cs.CL、cs.LG、cs.DC、cs.SE 论文，再按主题匹配；预印本收录不代表同行评审通过。</p><div class="grid">{''.join(arxiv_cards)}</div></section>
<section><h2>🔥 Hugging Face Papers 社区热度</h2><p class="desc">汇总本周每天的 Papers 热榜，展示最佳日榜位置、上榜天数和票数；这衡量社区注意力，不代表研究质量。</p><div class="grid">{''.join(hf_cards)}</div></section>
<section><h2>🔴 昇腾 CANN：框架发布与模型支持</h2><p class="desc">跟踪框架 Release、Ascend 软件栈版本和逐模型教程。模型发布与框架新增支持分开记录。</p><div class="grid">{''.join(release_cards)}</div></section>
<section><h2>📚 来源状态与统计口径</h2><ul>{source_rows}</ul>{source_note}<p class="small">GitHub Trending 是本次运行时的周榜快照；arXiv 以论文首次提交日期过滤；HF Papers 使用逐日历史榜单；项目发布以 GitHub Releases Atom Feed 为准。</p></section>
<section><a class="back" href="archive.html">📋 查看往期归档 →</a></section></div><footer><div class="wrap">技术生态趋势周报 · {week} · 自动收集，人工可复核</div></footer></body></html>'''


def update_home(week: str, start: date, end: date, paper_count: int, cann_count: int) -> None:
    path = ROOT / "index.html"
    text = path.read_text(encoding="utf-8")
    begin, finish = "<!-- TRENDS_LATEST_START -->", "<!-- TRENDS_LATEST_END -->"
    latest = f'''{begin}
    <a href="trends/{week}.html" class="trends-card">
      <div class="trends-card-header"><span class="trends-badge">最新</span><span class="trends-week">{week}</span></div>
      <p class="trends-summary">AI Agent / LLM 训推 / 开发者工具 / 新兴生态 · {paper_count} 篇论文 · {cann_count} 条昇腾框架更新</p>
      <div class="trends-meta"><span>📅 {start.month}.{start.day} – {end.month}.{end.day}</span><span>🔄 每周一更新</span></div>
    </a>
    {finish}'''
    if begin in text and finish in text:
        text = re.sub(re.escape(begin) + r".*?" + re.escape(finish), latest, text, flags=re.S)
    else:
        old = re.search(r'<a href="trends/[^\"]+\.html" class="trends-card">.*?</a>', text, re.S)
        if not old:
            raise RuntimeError("Could not find the latest-trends card in index.html")
        text = text[:old.start()] + latest + text[old.end():]
    path.write_text(text, encoding="utf-8")


def update_archive() -> None:
    path = TRENDS / "archive.html"
    text = path.read_text(encoding="utf-8")
    entries = []
    for report in TRENDS.glob("20??-W??.html"):
        match = re.fullmatch(r"(\d{4}-W\d{2})\.html", report.name)
        if not match:
            continue
        week = match.group(1)
        start, end = week_range(week)
        suffix = " · 试刊版" if week == "2026-W44" else ""
        entries.append((week, f'<a class="archive-item" href="{week}.html"><span class="week-id">{week}{suffix}</span><span class="week-date">{start.month}月{start.day}日 – {end.month}月{end.day}日</span></a>'))
    entries.sort(key=lambda row: row[0], reverse=True)
    replacement = '<div class="archive-list">\n' + "\n".join(item for _, item in entries) + "\n    </div>"
    text, count = re.subn(r'<div class="archive-list">.*?</div>', replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not find archive list in trends/archive.html")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", help="ISO week to collect, e.g. 2026-W45; defaults to the previous completed week")
    args = parser.parse_args()
    week = args.week or previous_week()
    start, end = week_range(week)

    statuses: list[dict] = []
    trending, status = fetch_optional("GitHub Trending · weekly", collect_github_trending)
    statuses.append(status)
    arxiv, status = fetch_optional("arXiv API", collect_arxiv, start, end)
    statuses.append(status)
    hf, status = fetch_optional("Hugging Face Papers · daily snapshots", collect_hf_papers, start, end)
    statuses.append(status)
    releases, release_statuses = collect_releases(start, end)
    statuses.extend(release_statuses)

    primary_statuses = statuses[:3]
    if sum(item["status"] == "ok" for item in primary_statuses) < 2:
        raise RuntimeError("Fewer than two source groups succeeded; refusing to publish an empty/partial report")

    TRENDS.mkdir(exist_ok=True)
    SNAPSHOTS.mkdir(exist_ok=True)
    snapshot = {
        "week": week, "from": start.isoformat(), "to": end.isoformat(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "sources": statuses,
        "github_trending": trending,
        "arxiv_papers": arxiv,
        "hf_papers": hf,
        "github_releases": releases,
    }
    (SNAPSHOTS / f"{week}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cann_releases = sum(item["track"] == "cann" for item in releases)
    (TRENDS / f"{week}.html").write_text(report_html(week, start, end, trending, arxiv, hf, releases, statuses), encoding="utf-8")
    update_home(week, start, end, len(arxiv), cann_releases)
    update_archive()
    print(f"Published {week}: GitHub {len(trending)}, arXiv {len(arxiv)}, HF {len(hf)}, CANN releases {cann_releases}")
    print("Source statuses:")
    for item in statuses:
        print(f"- {item['source']}: {item['status']} ({item['items']})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"weekly report failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
