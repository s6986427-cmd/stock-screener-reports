"""模組 B：產業趨勢分析 — 找受益概念股"""
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
from config import SCREENER_CONFIG, INDUSTRY_MAP

# 台灣上市公司產業關鍵字對應表（根據公司主業分類）
COMPANY_KEYWORDS = {
    # AI 供應鏈 / 銅箔 PCB 材料
    "8358": ["銅箔", "CCL", "AI 伺服器"],      # 金居
    "1303": ["銅箔", "PCB 材料"],               # 南亞
    "4950": ["CCL", "覆銅板"],                  # 台燿
    # 被動元件
    "2492": ["MLCC", "被動元件", "AI"],         # 華新科
    "2327": ["MLCC", "被動元件"],               # 國巨
    "2328": ["電阻", "被動元件"],               # 廣宇
    # 先進封裝
    "3711": ["先進封裝", "CoWoS"],              # 日月光投控
    "6274": ["先進封裝", "HBM"],                # 台燿
    # 散熱
    "3526": ["散熱", "液冷", "AI 伺服器"],      # 新普
    "3017": ["散熱", "AI"],                     # 奇鋐
    # IC 載板
    "3037": ["ABF", "IC 載板", "AI"],           # 欣興
    "6269": ["IC 載板", "ABF"],                 # 台郡
    # 電動車
    "1590": ["電動車", "EV", "車用"],           # 亞德客
    "6283": ["車用電子", "電動車"],             # 愛進發
}

def fetch_cnyes_news(keyword):
    """從 Google 新聞 RSS 抓台股相關新聞"""
    try:
        import xml.etree.ElementTree as ET
        query = requests.utils.quote(f"{keyword} 台股")
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        results = []
        for item in items[:5]:
            title_el = item.find("title")
            if title_el is not None and title_el.text:
                results.append({"title": title_el.text, "keyword": keyword})
        return results
    except Exception:
        pass
    return []

def fetch_moneydj_news(keyword):
    """從 MoneyDJ 抓財經新聞"""
    try:
        url = f"https://www.moneydj.com/kline/xa/Ya/yp1.xdjhtm"
        headers = {"User-Agent": "Mozilla/5.0"}
        search_url = f"https://www.moneydj.com/kline/xa/Ya/yp1.xdjhtm?a={requests.utils.quote(keyword)}"
        resp = requests.get(search_url, headers=headers, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        titles = [a.get_text(strip=True) for a in soup.select("a") if len(a.get_text(strip=True)) > 15]
        return [{"title": t, "keyword": keyword} for t in titles[:5]]
    except Exception:
        pass
    return []

def score_stock_by_trend(code, industry, stock_name, news_list):
    """根據產業和新聞計算趨勢分數"""
    score = 0
    matched_themes = []

    company_kws = COMPANY_KEYWORDS.get(code, [])
    industry_str = str(industry) + str(stock_name)

    # 比對產業別主題
    for theme, keywords in INDUSTRY_MAP.items():
        for kw in keywords:
            if kw in industry_str or any(kw in ckw for ckw in company_kws):
                score += 15
                if theme not in matched_themes:
                    matched_themes.append(theme)
                break

    # 比對公司預設關鍵字
    for kw in company_kws:
        for news in news_list:
            if kw in news.get("title", ""):
                score += 10
                break

    # 比對趨勢關鍵字
    for trend_kw in SCREENER_CONFIG["trend_keywords"]:
        if trend_kw in industry_str:
            score += 8
            break

    return score, matched_themes

def run_trend_screener(stocks_df):
    """對候選股票跑產業趨勢分析"""
    print("\n【模組 B】產業趨勢分析中...")

    # 先抓熱門趨勢新聞
    print("  抓取趨勢新聞...")
    all_news = []
    hot_keywords = ["AI 伺服器", "銅箔", "MLCC", "先進封裝", "電動車", "散熱"]
    for kw in hot_keywords:
        news = fetch_cnyes_news(kw)
        all_news.extend(news)
        time.sleep(0.3)

    print(f"  抓到 {len(all_news)} 則相關新聞")

    results = []
    for _, row in stocks_df.iterrows():
        code = str(row.get("code", ""))
        industry = str(row.get("industry", ""))
        name = str(row.get("name", ""))

        trend_score, themes = score_stock_by_trend(code, industry, name, all_news)

        results.append({
            "code": code,
            "trend_score": trend_score,
            "themes": "、".join(themes) if themes else "—",
        })

    df = pd.DataFrame(results)
    print(f"  趨勢分析完成")
    return df
