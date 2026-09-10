"""模組 C：技術面篩選"""
import pandas as pd
import numpy as np
from config import SCREENER_CONFIG

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def analyze_technical(code, df):
    """對單支股票做技術面分析，回傳評分和原因"""
    cfg = SCREENER_CONFIG["tech"]
    try:
        if df is None or len(df) < 60:
            return None

        close = df["Close"].dropna()
        volume = df["Volume"].dropna()

        if len(close) < 60:
            return None

        price = float(close.iloc[-1])

        # 價格範圍過濾
        if not (cfg["min_price"] <= price <= cfg["max_price"]):
            return None

        # 60MA
        ma60 = close.rolling(60).mean().iloc[-1]
        above_ma60 = price > ma60

        if cfg["above_ma60"] and not above_ma60:
            return None

        # RSI
        rsi_series = calc_rsi(close)
        rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50

        if not (cfg["rsi_min"] <= rsi <= cfg["rsi_max"]):
            return None

        # 成交量比（近 5 日 vs 近 20 日）
        if len(volume) >= 20:
            vol5 = volume.iloc[-5:].mean()
            vol20 = volume.iloc[-20:].mean()
            vol_ratio = vol5 / vol20 if vol20 > 0 else 1
        else:
            vol_ratio = 1

        # 52 週高低點
        year_data = close.iloc[-252:] if len(close) >= 252 else close
        week52_low = float(year_data.min())
        week52_high = float(year_data.max())

        from_low = (price - week52_low) / week52_low if week52_low > 0 else 0

        if not (cfg["from_low_min"] <= from_low <= cfg["from_low_max"]):
            return None

        # 20MA 多頭排列（股價 > 20MA > 60MA）
        ma20 = close.rolling(20).mean().iloc[-1]
        bullish_alignment = (price > ma20 > ma60)

        # 計算評分（最高 100 分）
        score = 0
        reasons = []

        if above_ma60:
            score += 20
            reasons.append(f"站穩季線（60MA: {ma60:.0f}）")

        if vol_ratio >= cfg["volume_ratio"]:
            score += 25
            reasons.append(f"量能放大 {vol_ratio:.1f}x")

        if 50 <= rsi <= 70:
            score += 20
            reasons.append(f"RSI 健康 ({rsi:.0f})")
        elif rsi < 50:
            score += 10
            reasons.append(f"RSI 偏低 ({rsi:.0f})，可留意")

        if bullish_alignment:
            score += 20
            reasons.append("多頭排列（價 > 20MA > 60MA）")

        # 距 52 週低點甜蜜點（30-60%）
        if 0.30 <= from_low <= 0.60:
            score += 15
            reasons.append(f"距 52 週低點 {from_low*100:.0f}%（甜蜜區）")
        else:
            score += 5
            reasons.append(f"距 52 週低點 {from_low*100:.0f}%")

        return {
            "code": code,
            "price": price,
            "ma20": round(float(ma20), 1),
            "ma60": round(float(ma60), 1),
            "rsi": round(rsi, 1),
            "vol_ratio": round(vol_ratio, 2),
            "week52_low": round(week52_low, 1),
            "week52_high": round(week52_high, 1),
            "from_low_pct": round(from_low * 100, 1),
            "tech_score": score,
            "tech_reasons": reasons,
        }

    except Exception as e:
        return None

def run_technical_screener(price_data_dict):
    """對所有股票跑技術面篩選"""
    print("\n【模組 C】技術面篩選中...")
    results = []
    for code, df in price_data_dict.items():
        result = analyze_technical(code, df)
        if result:
            results.append(result)

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("tech_score", ascending=False)

    print(f"  技術面通過：{len(results_df)} 支")
    return results_df
