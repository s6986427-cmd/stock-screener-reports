import requests
import pandas as pd
import time
import json
import io
from datetime import datetime, timedelta

def _fetch_isin_table(str_mode, market_label):
    """從證交所 ISIN 頁面抓股票清單（strMode=2 上市／strMode=4 上櫃）"""
    url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={str_mode}"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = "big5"
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    df = df[["有價證券代號及名稱", "市場別", "產業別"]].copy()
    df.columns = ["code_name", "market", "industry"]
    df = df[df["market"] == market_label].copy()
    df["code"] = df["code_name"].str.extract(r"^(\d{4})")
    df["name"] = df["code_name"].str.extract(r"^\d{4}\s+(.+)$")
    df = df.dropna(subset=["code"]).reset_index(drop=True)
    df["code_int"] = pd.to_numeric(df["code"], errors="coerce")
    df = df[(df["code_int"] >= 1000) & (df["code_int"] <= 9999)].copy()
    df = df.drop_duplicates(subset=["code"]).reset_index(drop=True)
    return df[["code", "name", "industry"]].copy()

def get_all_listed_stocks(include_otc=True):
    """從台灣證交所抓上市公司清單，include_otc=True 時一併抓上櫃（TPEx）清單"""
    print("  正在抓取上市公司清單...")
    try:
        df_twse = _fetch_isin_table(2, "上市")
        df_twse["market"] = "上市"
        print(f"  找到 {len(df_twse)} 家上市公司")
    except Exception as e:
        print(f"  抓取上市公司清單失敗：{e}")
        df_twse = pd.DataFrame(columns=["code", "name", "industry", "market"])

    if not include_otc:
        return df_twse

    try:
        print("  正在抓取上櫃公司清單...")
        df_tpex = _fetch_isin_table(4, "上櫃")
        df_tpex["market"] = "上櫃"
        print(f"  找到 {len(df_tpex)} 家上櫃公司")
    except Exception as e:
        print(f"  抓取上櫃公司清單失敗：{e}")
        df_tpex = pd.DataFrame(columns=["code", "name", "industry", "market"])

    combined = pd.concat([df_twse, df_tpex], ignore_index=True)
    combined = combined.drop_duplicates(subset=["code"]).reset_index(drop=True)
    return combined

def get_monthly_revenue(year, month):
    """從公開資訊觀測站抓月營收資料"""
    print(f"  正在抓取 {year}/{month:02d} 月營收...")
    url = "https://mops.twse.com.tw/mops/web/ajax_t05st10_ifrs"
    params = {
        "encodeURIComponent": 1,
        "step": 1,
        "firstin": 1,
        "off": 1,
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": "all",
        "isnew": "true",
        "co_id": "",
        "year": str(year - 1911),  # 民國年
        "month": str(month).zfill(2),
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://mops.twse.com.tw/mops/web/t05st10_ifrs",
    }
    try:
        resp = requests.post(url, data=params, headers=headers, timeout=30)
        resp.encoding = "utf-8"
        tables = pd.read_html(resp.text)
        if tables:
            df = tables[0]
            return df
    except Exception as e:
        print(f"  月營收抓取失敗：{e}")
    return pd.DataFrame()

def fetch_stock_price_data(codes, period="6mo", market_map=None):
    """用 yfinance 批次抓股價資料。market_map: {code: '上市'|'上櫃'}，上櫃股用 .TWO 後綴"""
    import yfinance as yf
    market_map = market_map or {}

    def suffix_for(code):
        return ".TWO" if market_map.get(code) == "上櫃" else ".TW"

    ticker_to_code = {f"{c}{suffix_for(c)}": c for c in codes}
    tickers = list(ticker_to_code.keys())
    print(f"  正在抓取 {len(tickers)} 支股票的股價資料...", flush=True)
    results = {}
    batch_size = 30
    total_batches = (len(tickers) + batch_size - 1) // batch_size
    for i in range(0, len(tickers), batch_size):
        batch_num = i // batch_size + 1
        batch = tickers[i:i+batch_size]
        t0 = time.time()
        try:
            data = yf.download(
                batch,
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
                timeout=20,
            )
            for ticker in batch:
                code = ticker_to_code[ticker]
                try:
                    if len(batch) == 1:
                        df = data
                    else:
                        df = data[ticker] if ticker in data.columns.get_level_values(0) else pd.DataFrame()
                    if df is not None and not df.empty:
                        results[code] = df
                except Exception:
                    pass
            elapsed = time.time() - t0
            print(f"  批次 {batch_num}/{total_batches} 完成（{elapsed:.1f}s，累計抓到 {len(results)} 支）", flush=True)
            time.sleep(1)
        except Exception as e:
            print(f"  批次 {batch_num}/{total_batches} 失敗：{e}", flush=True)
    print(f"  成功抓到 {len(results)} 支股票資料", flush=True)
    return results

def fetch_news(keyword_list, max_per_keyword=5):
    """從鉅亨網搜尋相關新聞"""
    from bs4 import BeautifulSoup
    news_items = []
    for keyword in keyword_list[:8]:  # 最多抓 8 個關鍵字
        try:
            url = f"https://news.cnyes.com/news/cat/tw_stock?keyword={requests.utils.quote(keyword)}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            articles = soup.select("a[href*='/news/id/']")[:max_per_keyword]
            for a in articles:
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if title and len(title) > 10:
                    news_items.append({"keyword": keyword, "title": title, "url": href})
        except Exception:
            pass
        time.sleep(0.5)
    return news_items
