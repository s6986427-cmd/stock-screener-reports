#!/usr/bin/env python3
"""剛噴出偵測 — 全市場（上市+上櫃）掃描，只需短期資料，獨立執行"""
import os
import sys
import time
import json
from datetime import datetime
from zoneinfo import ZoneInfo

TW_TZ = ZoneInfo("Asia/Taipei")

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_all_listed_stocks, fetch_stock_price_data
from screener_early import run_spike_screener


def main():
    start = time.time()
    print("=" * 50)
    print("  剛噴出偵測（全市場）")
    print(f"  時間：{datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    stocks_df = get_all_listed_stocks(include_otc=True)
    if stocks_df.empty:
        print("無法取得股票清單")
        sys.exit(1)

    market_map = dict(zip(stocks_df["code"], stocks_df["market"]))
    codes = stocks_df["code"].tolist()

    print(f"\n共 {len(codes)} 檔股票，抓取 2 個月日線資料...")
    price_data = fetch_stock_price_data(codes, period="2mo", market_map=market_map)

    result_df = run_spike_screener(price_data)

    name_map = dict(zip(stocks_df["code"], stocks_df["name"]))
    industry_map = dict(zip(stocks_df["code"], stocks_df["industry"]))
    if not result_df.empty:
        result_df["name"] = result_df["code"].map(name_map)
        result_df["market"] = result_df["code"].map(market_map)
        result_df["industry"] = result_df["code"].map(industry_map)
        result_df = result_df.sort_values("daily_gain_pct", ascending=False)

    records = result_df.to_dict(orient="records") if not result_df.empty else []
    with open("spike_result.json", "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(TW_TZ).isoformat(),
            "total_scanned": len(codes),
            "hits": records,
        }, f, ensure_ascii=False, indent=2)

    elapsed = int(time.time() - start)
    print(f"\n完成！耗時 {elapsed} 秒，共掃描 {len(codes)} 檔，剛噴出 {len(records)} 檔")
    for r in records:
        print(f"  {r['code']} {r.get('name','')} 現價{r['price']} 漲幅{r['daily_gain_pct']}% 量比{r['vol_ratio']}x")


if __name__ == "__main__":
    main()
