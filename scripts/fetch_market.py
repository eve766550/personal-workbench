# -*- coding: utf-8 -*-
"""
抓取美股行情，生成 ../data/us-market.js
数据源：新浪财经行情接口（免费、无需注册、无需 API Key）
用法：   python scripts/fetch_market.py

字段说明（新浪 hq 接口返回的逗号分隔串）：
  [0] 名称   [1] 最新价   [2] 涨跌幅%   [3] 行情时间   [4] 涨跌额
  [25] 常规收盘时间(美东)   [26] 昨收
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "us-market.js")

SINA = "https://hq.sinajs.cn/list="
HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0",
}

# 指数
INDICES = [
    ("gb_$ixic", "IXIC", "纳斯达克综合"),
    ("gb_$ndx",  "NDX",  "纳斯达克100"),
    ("gb_$inx",  "SPX",  "标普500"),
    ("gb_$dji",  "DJI",  "道琼斯"),
]

# 个股（科技七巨头 + 台积电）
STOCKS = [
    ("gb_aapl",  "AAPL",  "苹果"),
    ("gb_msft",  "MSFT",  "微软"),
    ("gb_nvda",  "NVDA",  "英伟达"),
    ("gb_googl", "GOOGL", "谷歌"),
    ("gb_amzn",  "AMZN",  "亚马逊"),
    ("gb_meta",  "META",  "Meta"),
    ("gb_tsla",  "TSLA",  "特斯拉"),
    ("gb_tsm",   "TSM",   "台积电"),
]

# 板块（用对应 ETF 的涨跌幅代表板块）
SECTORS = [
    ("gb_smh", "半导体"),
    ("gb_igv", "软件"),
    ("gb_xle", "能源"),
    ("gb_xlf", "金融"),
]

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def fetch(codes):
    """批量抓取，返回 {gb_xxx: [字段...]}"""
    url = SINA + ",".join(codes)
    req = urllib.request.Request(url, headers=HEADERS)
    raw = urllib.request.urlopen(req, timeout=20).read().decode("gbk", "ignore")
    out = {}
    for line in raw.split(";"):
        line = line.strip()
        if not line.startswith("var hq_str_"):
            continue
        key, _, rest = line.partition("=")
        key = key.replace("var hq_str_", "").strip()
        val = rest.strip().strip('"')
        out[key] = val.split(",") if val else []
    return out


def num(fields, idx):
    try:
        return float(fields[idx])
    except (IndexError, ValueError):
        return None


def parse_trade_date(fields):
    """从 'Oct 15 04:00PM EDT' 解析出交易日 -> '2026-10-15'"""
    for s in fields:
        m = re.match(r"([A-Za-z]{3})\s+(\d{1,2})\s+\d{1,2}:\d{2}(AM|PM)\s+\w+$", s.strip())
        if m and m.group(1) in MONTHS:
            year = None
            for f in reversed(fields):
                if re.fullmatch(r"20\d{2}", f.strip()):
                    year = int(f.strip())
                    break
            return "%04d-%02d-%02d" % (year or datetime.now().year,
                                       MONTHS[m.group(1)], int(m.group(2)))
    return datetime.now().strftime("%Y-%m-%d")


def main():
    codes = ([c for c, _, _ in INDICES] + [c for c, _, _ in STOCKS]
             + [c for c, _ in SECTORS])
    data = fetch(codes)

    indices = []
    for code, sym, name in INDICES:
        f = data.get(code, [])
        price, pct = num(f, 1), num(f, 2)
        if not price or pct is None:
            print("  ! 无数据，跳过：" + name)
            continue
        chg = num(f, 4)
        indices.append({
            "code": sym, "name": name,
            "value": round(price, 2),
            "change": round(chg, 2) if chg is not None else 0.0,
            "changePct": round(pct, 2),
        })

    stocks = []
    for code, sym, name in STOCKS:
        f = data.get(code, [])
        price, pct = num(f, 1), num(f, 2)
        if not price or pct is None:
            print("  ! 无数据，跳过：" + name)
            continue
        stocks.append({"code": sym, "name": name,
                       "value": round(price, 2), "changePct": round(pct, 2)})

    sectors = []
    for code, name in SECTORS:
        pct = num(data.get(code, []), 2)
        if pct is None:
            print("  ! 无数据，跳过：" + name)
            continue
        sectors.append({"name": name, "changePct": round(pct, 2)})

    ref = data.get("gb_aapl") or data.get("gb_$ixic") or []
    trade_date = parse_trade_date(ref)

    # 自动生成一句话小结
    summary = ""
    if indices:
        srt = sorted(indices, key=lambda x: -x["changePct"])
        lead, lag = srt[0], srt[-1]
        bits = ["%s %+.2f%%" % (lead["name"], lead["changePct"])]
        if lag["name"] != lead["name"]:
            bits.append("%s %+.2f%%" % (lag["name"], lag["changePct"]))
        summary = "%s 美股收盘：%s。" % (trade_date, "，".join(bits))
        if sectors:
            summary += "板块方面，%s。" % "、".join(
                "%s %+.2f%%" % (s["name"], s["changePct"]) for s in sectors)

    now = datetime.now(timezone(timedelta(hours=8)))
    payload = {
        "date": trade_date,
        "updatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "indices": indices,
        "stocks": stocks,
        "sectors": sectors,
        "summary": summary,
    }

    js = ("// 本文件由 scripts/fetch_market.py 自动生成，请勿手工修改\n"
          "// 数据源：新浪财经 https://finance.sina.com.cn   （免费接口，无需 Key）\n"
          "window.US_MARKET = "
          + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fp:
        fp.write(js)

    print("已写入：" + OUT)
    print("交易日 %s ｜ 指数 %d ｜ 个股 %d ｜ 板块 %d"
          % (trade_date, len(indices), len(stocks), len(sectors)))
    for ix in indices:
        print("   %-12s %10s  %+.2f%%" % (ix["name"], ix["value"], ix["changePct"]))


if __name__ == "__main__":
    main()
