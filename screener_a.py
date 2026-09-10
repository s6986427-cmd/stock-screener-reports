"""模組 A：財務與籌碼分析（EPS 成長、本益比、三大法人）"""
import requests
import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta

def fetch_eps_pe(code, market=None):
    """用 yfinance 抓本益比與季 EPS（上櫃股用 .TWO 後綴）"""
    try:
        suffix = ".TWO" if market == "上櫃" else ".TW"
        ticker = yf.Ticker(f"{code}{suffix}")
        info = ticker.info
        if not info or not info.get("trailingPE") and not info.get("trailingEps"):
            # 後綴猜錯時嘗試另一種
            alt_suffix = ".TW" if suffix == ".TWO" else ".TWO"
            alt_ticker = yf.Ticker(f"{code}{alt_suffix}")
            alt_info = alt_ticker.info
            if alt_info and (alt_info.get("trailingPE") or alt_info.get("trailingEps")):
                ticker, info = alt_ticker, alt_info

        pe = info.get("trailingPE") or info.get("forwardPE")
        eps = info.get("trailingEps")

        # 季財報
        try:
            qe = ticker.quarterly_earnings
            if qe is not None and not qe.empty and len(qe) >= 3:
                eps_list = qe["Earnings"].tolist()[:4]
                # 判斷成長：最近一季 vs 去年同季
                if len(eps_list) >= 4:
                    eps_growth = ((eps_list[0] - eps_list[3]) / abs(eps_list[3]) * 100
                                  if eps_list[3] != 0 else None)
                else:
                    eps_growth = None
                eps_trend = "成長" if eps_growth and eps_growth > 10 else (
                    "持平" if eps_growth and -10 <= eps_growth <= 10 else "衰退"
                ) if eps_growth is not None else "資料不足"
            else:
                eps_growth = None
                eps_trend = "資料不足"
        except Exception:
            eps_growth = None
            eps_trend = "資料不足"

        return {
            "pe": round(pe, 1) if pe else None,
            "eps": round(eps, 2) if eps else None,
            "eps_growth_yoy": round(eps_growth, 1) if eps_growth else None,
            "eps_trend": eps_trend,
        }
    except Exception:
        return {"pe": None, "eps": None, "eps_growth_yoy": None, "eps_trend": "資料不足"}

def fetch_institutional(code):
    """從台灣證交所抓近 10 日三大法人買賣超"""
    try:
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/fund/TWT38U?response=json&date={date_str}&stockNo={code}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()

        if data.get("stat") != "OK" or not data.get("data"):
            return _empty_institutional()

        rows = data["data"]
        # 欄位：日期, 外資買, 外資賣, 外資差, 投信買, 投信賣, 投信差, 自營買, 自營賣, 自營差, 合計
        foreign_net = sum(int(r[3].replace(",", "")) for r in rows[-10:] if len(r) > 10)
        trust_net = sum(int(r[6].replace(",", "")) for r in rows[-10:] if len(r) > 10)
        dealer_net = sum(int(r[9].replace(",", "")) for r in rows[-10:] if len(r) > 10)
        total_net = foreign_net + trust_net + dealer_net

        def fmt(n):
            return f"+{n//1000}張" if n > 0 else f"{n//1000}張"

        return {
            "foreign_net": foreign_net,
            "trust_net": trust_net,
            "dealer_net": dealer_net,
            "total_net": total_net,
            "foreign_str": fmt(foreign_net),
            "trust_str": fmt(trust_net),
            "dealer_str": fmt(dealer_net),
            "inst_signal": "買超" if total_net > 0 else "賣超",
        }
    except Exception:
        return _empty_institutional()

def _empty_institutional():
    return {
        "foreign_net": 0, "trust_net": 0, "dealer_net": 0, "total_net": 0,
        "foreign_str": "—", "trust_str": "—", "dealer_str": "—", "inst_signal": "—",
    }

def get_sector_avg_pe(sector, pe_dict):
    """計算同業平均本益比"""
    pes = [v for k, v in pe_dict.items() if v and isinstance(v, (int, float))]
    return round(sum(pes) / len(pes), 1) if pes else None

def run_fundamental_screener(stocks_df):
    """對候選股票跑財務與籌碼分析"""
    print("\n【模組 A】財務與籌碼分析中...")
    results = []
    codes = stocks_df["code"].tolist()

    # 先批次抓 PE，用於計算同業平均
    pe_by_sector = {}

    for i, row in stocks_df.iterrows():
        code = str(row["code"])
        sector = str(row.get("sector", ""))
        print(f"  分析 {code} {row.get('name','')}...", end="\r")

        fin = fetch_eps_pe(code, market=row.get("market"))
        inst = fetch_institutional(code)

        # 本益比合理性
        pe = fin.get("pe")
        if sector not in pe_by_sector:
            pe_by_sector[sector] = []
        if pe:
            pe_by_sector[sector].append(pe)

        results.append({
            "code": code,
            **fin,
            **inst,
        })
        time.sleep(0.3)

    # 加入同業平均本益比對比
    for r in results:
        sector = stocks_df[stocks_df["code"] == r["code"]]["sector"].values
        sector = sector[0] if len(sector) > 0 else ""
        pes = pe_by_sector.get(sector, [])
        avg_pe = round(sum(pes) / len(pes), 1) if pes else None
        r["sector_avg_pe"] = avg_pe
        if r["pe"] and avg_pe:
            ratio = r["pe"] / avg_pe
            r["pe_vs_sector"] = "偏低" if ratio < 0.8 else ("合理" if ratio <= 1.2 else "偏高")
        else:
            r["pe_vs_sector"] = "—"

    print(f"\n  財務籌碼分析完成（{len(results)} 支）")
    return pd.DataFrame(results)
