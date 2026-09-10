"""模組 E：初期起漲偵測（全市場掃描，不限七大產業）
參照精材 3374／聯一光 3441 起漲初期樣態校準：
均線多頭排列（日/週/月）+ MACD 黃金交叉 + DMI 翻多 + KD 黃金交叉 + RSI 健康區 + 距低點 10~40% + 量增
"""
import pandas as pd
import numpy as np
from config import EARLY_RALLY_CONFIG, MID_RALLY_CONFIG, SPIKE_CONFIG
from screener_c import calc_rsi


def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    osc = (dif - dea) * 2
    return dif, dea, osc


def calc_dmi(high, low, close, period=14):
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return plus_di, minus_di, adx


def calc_kd(high, low, close, n=9, k_period=3, d_period=3):
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / k_period, adjust=False).mean()
    d = k.ewm(alpha=1 / d_period, adjust=False).mean()
    return k, d


def _crossed_up_within(fast, slow, lookback):
    """判斷 fast 是否在近 lookback 天內由下往上穿越 slow，回傳 (是否發生, 交叉當天索引)"""
    n = len(fast)
    for i in range(n - lookback, n):
        if i <= 0:
            continue
        if fast.iloc[i - 1] <= slow.iloc[i - 1] and fast.iloc[i] > slow.iloc[i]:
            return True, i
    return False, None


def _bullish_alignment(close, high, low, ma_periods=(5, 10, 20), rising_lookback=3, strict=True):
    """
    strict=True（日線用）：價 > MA5 > MA10 > MA20，且三條均線都上揚
    strict=False（週線/月線用）：長週期均線是落後指標，起漲初期不會馬上排列整齊，
    只要求「價站上 MA5」+「MA5 正在上揚」，代表短期趨勢已經轉向
    """
    if len(close) < max(ma_periods) + rising_lookback:
        return False
    ma5 = close.rolling(ma_periods[0]).mean()
    price = close.iloc[-1]
    if pd.isna(ma5.iloc[-1]):
        return False

    if not strict:
        above_ma5 = price > ma5.iloc[-1]
        ma5_rising = ma5.iloc[-1] > ma5.iloc[-1 - rising_lookback]
        return bool(above_ma5 and ma5_rising)

    ma10 = close.rolling(ma_periods[1]).mean()
    ma20 = close.rolling(ma_periods[2]).mean()
    if pd.isna(ma10.iloc[-1]) or pd.isna(ma20.iloc[-1]):
        return False
    order_ok = price > ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]
    rising_ok = (
        ma5.iloc[-1] > ma5.iloc[-1 - rising_lookback]
        and ma10.iloc[-1] > ma10.iloc[-1 - rising_lookback]
        and ma20.iloc[-1] > ma20.iloc[-1 - rising_lookback]
    )
    return bool(order_ok and rising_ok)


def _resample(df, rule):
    o = df.resample(rule).agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna(subset=["Close"])
    return o


def analyze_early_rally(code, df):
    cfg = EARLY_RALLY_CONFIG
    try:
        if df is None or len(df) < 260:
            return None

        close = df["Close"].dropna()
        high = df["High"].dropna()
        low = df["Low"].dropna()
        volume = df["Volume"].dropna()
        if len(close) < 260:
            return None

        price = float(close.iloc[-1])
        if not (cfg["min_price"] <= price and (cfg["max_price"] is None or price <= cfg["max_price"])):
            return None

        # 距 52 週低點
        year_data = close.iloc[-252:] if len(close) >= 252 else close
        week52_low = float(year_data.min())
        from_low = (price - week52_low) / week52_low if week52_low > 0 else 0
        if not (cfg["from_low_min"] <= from_low <= cfg["from_low_max"]):
            return None

        # RSI
        rsi = float(calc_rsi(close).iloc[-1])
        if not (cfg["rsi_min"] <= rsi <= cfg["rsi_max"]):
            return None

        # 量能：近 3 日均量 / 近 20 日均量
        if len(volume) < 20:
            return None
        vol3 = volume.iloc[-3:].mean()
        vol20 = volume.iloc[-20:].mean()
        vol_ratio = vol3 / vol20 if vol20 > 0 else 0
        if vol_ratio < cfg["volume_ratio"]:
            return None

        # MACD 黃金交叉
        dif, dea, osc = calc_macd(close)
        macd_cross, _ = _crossed_up_within(dif, dea, cfg["macd_cross_lookback"])
        if not macd_cross:
            return None

        # DMI 翻多
        plus_di, minus_di, adx = calc_dmi(high, low, close)
        dmi_cross, cross_i = _crossed_up_within(plus_di, minus_di, cfg["dmi_cross_lookback"])
        if not dmi_cross:
            return None
        if pd.isna(adx.iloc[cross_i]) or adx.iloc[cross_i] > cfg["adx_max_at_cross"]:
            return None

        # KD 黃金交叉（中低檔）
        k, d = calc_kd(high, low, close)
        kd_cross, kd_i = _crossed_up_within(k, d, cfg["dmi_cross_lookback"])
        if not kd_cross:
            return None
        if k.iloc[kd_i] > cfg["kd_max_at_cross"] or d.iloc[kd_i] > cfg["kd_max_at_cross"]:
            return None

        # 日線多頭排列
        if not _bullish_alignment(close, high, low):
            return None

        # 週線：短均線（MA5）站上且轉上揚
        weekly = _resample(df, "W")
        if len(weekly) < 10 or not _bullish_alignment(weekly["Close"], weekly["High"], weekly["Low"], rising_lookback=2, strict=False):
            return None

        # 月線：短均線（MA5）站上且轉上揚
        monthly = _resample(df, "ME")
        if len(monthly) < 8 or not _bullish_alignment(monthly["Close"], monthly["High"], monthly["Low"], rising_lookback=1, strict=False):
            return None

        return {
            "code": code,
            "price": round(price, 2),
            "rsi": round(rsi, 1),
            "vol_ratio": round(float(vol_ratio), 2),
            "from_low_pct": round(from_low * 100, 1),
            "adx_at_cross": round(float(adx.iloc[cross_i]), 1),
            "reasons": [
                "日/週/月三線多頭排列",
                f"MACD 近{cfg['macd_cross_lookback']}日黃金交叉",
                f"DMI 翻多（ADX {adx.iloc[cross_i]:.0f}，趨勢剛形成）",
                "KD 中低檔黃金交叉",
                f"RSI {rsi:.0f}（健康區）",
                f"距 52 週低點 {from_low*100:.0f}%（初期）",
                f"量增 {vol_ratio:.1f}x",
            ],
        }
    except Exception:
        return None


def analyze_mid_rally(code, df):
    """續漲確認：已經漲了一小段，目前仍是多頭方向，不要求訊號剛發生"""
    cfg = MID_RALLY_CONFIG
    try:
        if df is None or len(df) < 260:
            return None

        close = df["Close"].dropna()
        high = df["High"].dropna()
        low = df["Low"].dropna()
        volume = df["Volume"].dropna()
        if len(close) < 260:
            return None

        price = float(close.iloc[-1])
        if not (cfg["min_price"] <= price and (cfg["max_price"] is None or price <= cfg["max_price"])):
            return None

        year_data = close.iloc[-252:] if len(close) >= 252 else close
        week52_low = float(year_data.min())
        from_low = (price - week52_low) / week52_low if week52_low > 0 else 0
        if not (cfg["from_low_min"] <= from_low <= cfg["from_low_max"]):
            return None

        rsi = float(calc_rsi(close).iloc[-1])
        if not (cfg["rsi_min"] <= rsi <= cfg["rsi_max"]):
            return None

        if len(volume) < 20:
            return None
        vol3 = volume.iloc[-3:].mean()
        vol20 = volume.iloc[-20:].mean()
        vol_ratio = vol3 / vol20 if vol20 > 0 else 0
        if vol_ratio < cfg["volume_ratio"]:
            return None

        dif, dea, osc = calc_macd(close)
        if not (dif.iloc[-1] > dea.iloc[-1]):
            return None

        plus_di, minus_di, adx = calc_dmi(high, low, close)
        if not (plus_di.iloc[-1] > minus_di.iloc[-1]):
            return None
        if pd.isna(adx.iloc[-1]) or adx.iloc[-1] < cfg["adx_min"]:
            return None

        k, d = calc_kd(high, low, close)
        if not (k.iloc[-1] > d.iloc[-1]):
            return None

        if not _bullish_alignment(close, high, low):
            return None
        weekly = _resample(df, "W")
        if len(weekly) < 10 or not _bullish_alignment(weekly["Close"], weekly["High"], weekly["Low"], rising_lookback=2, strict=False):
            return None
        monthly = _resample(df, "ME")
        if len(monthly) < 8 or not _bullish_alignment(monthly["Close"], monthly["High"], monthly["Low"], rising_lookback=1, strict=False):
            return None

        return {
            "code": code,
            "price": round(price, 2),
            "rsi": round(rsi, 1),
            "vol_ratio": round(float(vol_ratio), 2),
            "from_low_pct": round(from_low * 100, 1),
            "adx": round(float(adx.iloc[-1]), 1),
            "reasons": [
                "日/週/月三線多頭排列",
                "MACD 仍在多方（DIF > 訊號線）",
                f"DMI 多方確立（ADX {adx.iloc[-1]:.0f}，趨勢已站穩）",
                "KD 仍在多方（K > D）",
                f"RSI {rsi:.0f}",
                f"距 52 週低點 {from_low*100:.0f}%（已起漲一段）",
                f"量能 {vol_ratio:.1f}x（未明顯萎縮）",
            ],
        }
    except Exception:
        return None


def run_mid_rally_screener(price_data_dict):
    print("\n【模組 F】續漲確認中（全市場）...")
    results = []
    for code, df in price_data_dict.items():
        result = analyze_mid_rally(code, df)
        if result:
            results.append(result)
    results_df = pd.DataFrame(results)
    print(f"  續漲確認訊號：{len(results_df)} 支")
    return results_df


def analyze_spike(code, df):
    """剛噴出：今天價漲量爆，不看均線排列或指標交叉"""
    cfg = SPIKE_CONFIG
    try:
        if df is None or len(df) < 21:
            return None
        close = df["Close"].dropna()
        volume = df["Volume"].dropna()
        if len(close) < 21 or len(volume) < 21:
            return None

        price = float(close.iloc[-1])
        if not (cfg["min_price"] <= price and (cfg["max_price"] is None or price <= cfg["max_price"])):
            return None

        prev_close = float(close.iloc[-2])
        if prev_close <= 0:
            return None
        daily_gain = (price - prev_close) / prev_close
        if daily_gain < cfg["min_daily_gain"]:
            return None

        vol_today = float(volume.iloc[-1])
        vol20 = volume.iloc[-21:-1].mean()
        vol_ratio = vol_today / vol20 if vol20 > 0 else 0
        if vol_ratio < cfg["min_vol_ratio"]:
            return None

        rsi = float(calc_rsi(close).iloc[-1]) if len(close) >= 15 else None

        return {
            "code": code,
            "price": round(price, 2),
            "daily_gain_pct": round(daily_gain * 100, 1),
            "vol_ratio": round(float(vol_ratio), 2),
            "rsi": round(rsi, 1) if rsi is not None else None,
            "reasons": [
                f"今日大漲 {daily_gain*100:.1f}%",
                f"爆量 {vol_ratio:.1f}x",
            ],
        }
    except Exception:
        return None


def run_spike_screener(price_data_dict):
    print("\n【模組 G】剛噴出偵測中（全市場）...")
    results = []
    for code, df in price_data_dict.items():
        result = analyze_spike(code, df)
        if result:
            results.append(result)
    results_df = pd.DataFrame(results)
    print(f"  剛噴出訊號：{len(results_df)} 支")
    return results_df


def run_early_rally_screener(price_data_dict):
    print("\n【模組 E】初期起漲偵測中（全市場）...")
    results = []
    for code, df in price_data_dict.items():
        result = analyze_early_rally(code, df)
        if result:
            results.append(result)
    results_df = pd.DataFrame(results)
    print(f"  初期起漲訊號：{len(results_df)} 支")
    return results_df
