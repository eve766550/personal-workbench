# -*- coding: utf-8 -*-
"""
抓取 AI 资讯（RSS），生成 ../data/ai-news.js
用法：   python scripts/fetch_news.py

说明：只抓取公开 RSS，无需 API Key。想加更多来源，往 FEEDS 里加一行即可。
"""
import html
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "ai-news.js")

FEEDS = [
    ("量子位", "https://www.qbitai.com/feed"),
    # 想加来源就在下面照格式加一行，格式：(显示名, RSS 地址)
    # ("机器之心", "https://www.jiqizhixin.com/rss"),
    # ("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalWorkbench/1.0)"}

MAX_ITEMS = 12

# 分类关键词（自上而下匹配，命中即停）
RULES = [
    ("论文研究", ["论文", "研究", "arXiv", "提出", "算法", "架构", "数据集", "训练方法"]),
    ("模型发布", ["发布", "开源", "推出", "上线", "问世", "登场", "模型", "大模型",
                  "Agent", "智能体", "多模态", "SOTA", "参数"]),
]

# 每类的默认关注理由
REASONS = {
    "论文研究": "技术前沿，可了解方法与思路，对毕业设计选题有参考价值。",
    "模型发布": "关注模型能力与调用成本的变化，直接影响你能做什么。",
    "行业动态": "关注行业与政策动向，关系到就业方向和产品化的合规边界。",
}


def classify(title):
    for cat, kws in RULES:
        if any(k in title for k in kws):
            return cat
    return "行业动态"


def clean(text):
    """去 HTML 标签、解实体、压缩空白"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_feed(name, url):
    req = urllib.request.Request(url, headers=HEADERS)
    raw = urllib.request.urlopen(req, timeout=25).read()
    root = ET.fromstring(raw)
    out = []
    for it in root.findall(".//item"):
        t = it.find("title")
        title = clean(t.text if t is not None else "")
        if not title:
            continue
        lk = it.find("link")
        desc = it.find("description")
        out.append({
            "title": title,
            "source": name,
            "url": (lk.text or "#").strip() if lk is not None else "#",
            "summary": clean(desc.text)[:180] if desc is not None else "",
        })
    return out


def main():
    items, seen = [], set()

    for name, url in FEEDS:
        try:
            got = fetch_feed(name, url)
            print("  %s：抓到 %d 条" % (name, len(got)))
        except Exception as e:
            print("  ! %s 抓取失败：%s" % (name, e))
            continue
        for g in got:
            if g["title"] in seen:
                continue
            seen.add(g["title"])
            g["category"] = classify(g["title"])
            g["reason"] = REASONS[g["category"]]
            items.append(g)

    items = items[:MAX_ITEMS]

    now = datetime.now(timezone(timedelta(hours=8)))
    payload = {
        "date": now.strftime("%Y-%m-%d"),
        "updatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "items": items,
    }

    js = ("// 本文件由 scripts/fetch_news.py 自动生成，请勿手工修改\n"
          "// 数据源：公开 RSS（见 scripts/fetch_news.py 的 FEEDS）\n"
          "window.AI_NEWS = "
          + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fp:
        fp.write(js)

    print("已写入：" + OUT)
    print("共 %d 条：" % len(items))
    for it in items:
        print("   [%s] %s" % (it["category"], it["title"][:50]))


if __name__ == "__main__":
    main()
