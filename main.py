#!/usr/bin/env python3
"""
選股雷達 — 一鍵執行
用法：python3 main.py
"""
import os
import sys
import time
import subprocess
import pandas as pd
from datetime import datetime

# 確保工作目錄正確
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_all_listed_stocks, fetch_stock_price_data
from screener_c import run_technical_screener
from screener_b import run_trend_screener
from screener_a import run_fundamental_screener
from report_generator import generate_report
from config import TARGET_SECTORS, ALL_TARGET_CODES
from company_profile import COMPANY_PROFILES

# 建立代碼 → 細分類的對應表
CODE_TO_SECTOR = {
    code: sector
    for sector, codes in TARGET_SECTORS.items()
    for code in codes
}

def main():
    start_time = time.time()
    print("=" * 50)
    print("  選股雷達啟動（七大產業模式）")
    print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Step 1：取得上市+上櫃公司清單（只抓目標產業股票）
    print("\n[1/4] 取得目標產業清單...")
    stocks_df = get_all_listed_stocks(include_otc=True)
    if stocks_df.empty:
        print("  ⚠️  無法取得股票清單，請確認網路連線")
        sys.exit(1)

    # 加入細分類標籤，只保留七大類別的股票
    stocks_df["sector"] = stocks_df["code"].map(CODE_TO_SECTOR)
    target_stocks_df = stocks_df[stocks_df["sector"].notna()].copy()

    for sector, codes in TARGET_SECTORS.items():
        found = len([c for c in codes if c in stocks_df["code"].values])
        print(f"  {sector}：{found} 支")

    print(f"  → 共 {len(target_stocks_df)} 支目標股票")

    # Step 2：抓股價資料
    print("\n[2/4] 抓取股價資料...")
    target_codes = target_stocks_df["code"].tolist()
    market_map = dict(zip(target_stocks_df["code"], target_stocks_df["market"]))
    price_data = fetch_stock_price_data(target_codes, period="1y", market_map=market_map)

    # Step 3：技術面篩選
    print("\n[3/4] 技術面篩選...")
    tech_df = run_technical_screener(price_data)
    if tech_df.empty:
        print("  ⚠️  技術面無符合標的")
        tech_df = pd.DataFrame(columns=["code", "price", "ma20", "ma60", "rsi", "vol_ratio",
                                         "week52_low", "week52_high", "from_low_pct",
                                         "tech_score", "tech_reasons"])

    # 合併股票名稱、產業別、細分類
    tech_df = tech_df.merge(
        target_stocks_df[["code", "name", "industry", "sector"]], on="code", how="left"
    )

    # Step 4：產業趨勢分析
    print("\n[4/5] 產業趨勢分析...")
    trend_df = run_trend_screener(tech_df)

    # Step 5：財務與籌碼分析（對技術面通過的股票）
    print("\n[5/5] 財務與籌碼分析...")
    fund_df = run_fundamental_screener(tech_df[["code", "name", "sector"]])

    # 整合三個模組
    print("\n整合評分...")
    final_df = tech_df.merge(trend_df, on="code", how="left")
    final_df = final_df.merge(fund_df, on="code", how="left")
    final_df["trend_score"] = final_df["trend_score"].fillna(0)

    # 加入公司靜態資料（護城河、風險、供應鏈位置）
    def get_profile_field(code, field):
        p = COMPANY_PROFILES.get(str(code), {})
        return p.get(field)

    final_df["position"] = final_df["code"].apply(lambda c: get_profile_field(c, "position") or "—")
    final_df["moat"] = final_df["code"].apply(lambda c: get_profile_field(c, "moat") or "—")
    final_df["risk_note"] = final_df["code"].apply(lambda c: get_profile_field(c, "risk") or "—")
    final_df["trend_tags"] = final_df["code"].apply(
        lambda c: "、".join(get_profile_field(c, "trend") or []) or "—"
    )

    # 自動生成一句話投資理由
    def one_liner(row):
        name = row.get("name", "")
        position = row.get("position", "")
        trend_tags = row.get("trend_tags", "")
        moat = row.get("moat", "")
        inst = row.get("inst_signal", "")
        eps_trend = row.get("eps_trend", "")
        parts = []
        if trend_tags and trend_tags != "—":
            parts.append(f"受益於 {trend_tags}")
        if position and position != "—":
            parts.append(f"位於供應鏈{position}")
        if moat and moat != "—":
            parts.append(moat.split("，")[0])
        if eps_trend in ["成長"]:
            parts.append("EPS 年增")
        if inst == "買超":
            parts.append("三大法人買超")
        return "，".join(parts[:3]) + "。" if parts else "—"

    final_df["one_liner"] = final_df.apply(one_liner, axis=1)

    # 判斷綜合評級
    def grade(row):
        modules = 0
        if row.get("tech_score", 0) >= 60:
            modules += 1
        if row.get("trend_score", 0) >= 15:
            modules += 1
        if row.get("inst_signal") == "買超" or row.get("eps_trend") == "成長":
            modules += 1
        if modules >= 3:
            return "hot"
        elif modules >= 2:
            return "watch"
        else:
            return "observe"

    final_df["grade"] = final_df.apply(grade, axis=1)
    final_df = final_df.sort_values(
        ["grade", "tech_score", "trend_score"],
        ascending=[True, False, False],
        key=lambda x: x.map({"hot": 0, "watch": 1, "observe": 2}) if x.name == "grade" else x
    )

    # 輸出報告
    print("\n產生 HTML 報告...")
    output_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = generate_report(final_df, total_analyzed=len(target_codes), output_dir=output_dir, mode="sector")

    # 輸出 JSON（供網頁報告使用）
    import json
    json_cols = ["code", "name", "sector", "industry", "price", "grade", "tech_score",
                 "trend_score", "one_liner", "rsi", "vol_ratio", "from_low_pct", "inst_signal"]
    json_cols = [c for c in json_cols if c in final_df.columns]
    records = final_df[json_cols].where(pd.notna(final_df[json_cols]), None).to_dict(orient="records")
    with open(os.path.join(output_dir, "sector_result.json"), "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_scanned": len(target_codes),
            "hits": records,
        }, f, ensure_ascii=False, indent=2)

    elapsed = int(time.time() - start_time)
    print(f"\n{'='*50}")
    print(f"  完成！耗時 {elapsed} 秒")
    print(f"  報告位置：{report_path}")
    hot_count = len(final_df[final_df["grade"] == "hot"])
    watch_count = len(final_df[final_df["grade"] == "watch"])
    print(f"  🔥 強力推薦：{hot_count} 支")
    print(f"  👀 值得關注：{watch_count} 支")
    print("=" * 50)

    # 自動用瀏覽器打開報告（雲端排程環境沒有瀏覽器，略過）
    if not os.environ.get("GITHUB_ACTIONS"):
        try:
            subprocess.run(["open", report_path])
        except Exception:
            pass

if __name__ == "__main__":
    main()
