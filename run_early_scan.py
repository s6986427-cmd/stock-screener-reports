#!/usr/bin/env python3
"""初期起漲偵測 — 全市場（上市+上櫃）掃描，獨立執行"""
import os
import sys
import time
import json
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_all_listed_stocks, fetch_stock_price_data
from screener_early import run_early_rally_screener, run_mid_rally_screener, run_spike_screener


def main():
    start = time.time()
    print("=" * 50)
    print("  初期起漲偵測（全市場）")
    print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    stocks_df = get_all_listed_stocks(include_otc=True)
    if stocks_df.empty:
        print("無法取得股票清單")
        sys.exit(1)

    market_map = dict(zip(stocks_df["code"], stocks_df["market"]))
    codes = stocks_df["code"].tolist()

    print(f"\n共 {len(codes)} 檔股票，抓取 3 年日線資料...")
    price_data = fetch_stock_price_data(codes, period="3y", market_map=market_map)

    name_map = dict(zip(stocks_df["code"], stocks_df["name"]))
    industry_map = dict(zip(stocks_df["code"], stocks_df["industry"]))

    def enrich_and_save(result_df, out_path):
        if not result_df.empty:
            result_df = result_df.copy()
            result_df["name"] = result_df["code"].map(name_map)
            result_df["market"] = result_df["code"].map(market_map)
            result_df["industry"] = result_df["code"].map(industry_map)
            result_df = result_df.sort_values("vol_ratio", ascending=False)
        records = result_df.to_dict(orient="records") if not result_df.empty else []
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "total_scanned": len(codes),
                "hits": records,
            }, f, ensure_ascii=False, indent=2)
        return records

    early_df = run_early_rally_screener(price_data)
    early_records = enrich_and_save(early_df, "early_rally_result.json")

    mid_df = run_mid_rally_screener(price_data)
    mid_records = enrich_and_save(mid_df, "mid_rally_result.json")

    spike_df = run_spike_screener(price_data)
    spike_records = enrich_and_save(spike_df, "spike_result.json")

    elapsed = int(time.time() - start)
    print(f"\n完成！耗時 {elapsed} 秒，共掃描 {len(codes)} 檔")
    print(f"初期起漲：{len(early_records)} 檔，續漲確認：{len(mid_records)} 檔，剛噴出：{len(spike_records)} 檔")
    print("--- 初期起漲 ---")
    for r in early_records:
        print(f"  {r['code']} {r.get('name','')} 現價{r['price']} RSI{r['rsi']} 量比{r['vol_ratio']}x 距低點{r['from_low_pct']}%")
    print("--- 續漲確認 ---")
    for r in mid_records:
        print(f"  {r['code']} {r.get('name','')} 現價{r['price']} RSI{r['rsi']} 量比{r['vol_ratio']}x 距低點{r['from_low_pct']}%")
    print("--- 剛噴出 ---")
    for r in spike_records:
        print(f"  {r['code']} {r.get('name','')} 現價{r['price']} 漲幅{r['daily_gain_pct']}% 量比{r['vol_ratio']}x")


if __name__ == "__main__":
    main()
