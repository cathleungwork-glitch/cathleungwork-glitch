"""Defensive momentum screen and the contest book built from it.

The book is long a handful of medical names that are still in an uptrend,
have positive six-month momentum, and gave back the least in the window
being judged, plus a BOXX ballast so the account is never flat.

Contest facts this sizing is built around (Diamond Strategy, Singapore
IBKR paper, about 1,000,000 SGD, close 27 January 2027):

- Ten cumulative flat days are already used. Another flat session is an
  automatic exit. BOXX counts toward the position ratio, cash does not.
- Position ratio is (absolute long market value + absolute short market
  value) / that day's NAV. This book is long only.
- The team's reading of the holding rule is a ratio of at least 50%.
  The organizer's captured reply defines the ratio and does not state
  the 50% figure. The book targets 60% so it clears that reading.
- The live board, as the team reads it, weights Sharpe 35%, return 25%,
  max drawdown 25%, and stability 15%. The sleeve is 15% of NAV, so a
  simultaneous repeat of the 8% eligibility loss is 1.2% of NAV.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from medmom.universe import AI_RANK, BALLAST

NAV_SGD = 1_000_000.0
TOP_N = 6
MIN_AI = 3
# An AI name may replace a plainer medical name only when its stress-window
# loss is within three percentage points of the name it replaces. The contest
# is won on drawdown, so the preference does not buy a much deeper hole.
AI_DD_SLACK = 0.03
AI_GROUPS = frozenset({"ai_core", "ai_applied"})
# 15% sleeve times the 8% eligibility cap is 1.2% of NAV if every holding
# repeats that loss together. That sits inside the sub-1.4% drawdowns that
# were occupying the top of the board in mid-November 2026.
BASE_SLEEVE = 0.15
TARGET_GROSS = 0.60
MIN_GROSS = 0.55
# Each name's stress-window loss has to be 8% or smaller. SPY's peak-to-last
# loss over the autumn 2026 selloff was about 8%. Names that fell more than
# the index are not "least retrace".
MAX_STRESS_LOSS = 0.08
RELAXED_STRESS_LOSS = 0.12
BAND_LOW = 0.97
BAND_HIGH = 1.06
RELAXED_BAND_LOW = 0.94
RELAXED_BAND_HIGH = 1.10
MIN_PRICE = 8.0
MIN_DOLLAR_VOL = 15_000_000.0
TRAILING_STRESS_SESSIONS = 60
CORR_LOOKBACK = 60
CORR_CUT = 0.75
CORR_SCALE = 0.75
COST_ONE_WAY = 0.0005  # 5 bps of traded notional
THIS_SELLOFF_START = pd.Timestamp("2026-09-01")
CONTEST_START = pd.Timestamp("2026-10-26")


@dataclass(frozen=True)
class Row:
    ticker: str
    company: str
    group: str
    price: float
    sma50: float
    sma200: float
    ret_126: float
    stress_dd: float
    dollar_vol: float
    dist_sma50: float
    dd_20: float
    ret_contest: float | None

    @property
    def ai_rank(self) -> int:
        return AI_RANK.get(self.group, 0)

    @property
    def ai(self) -> bool:
        return self.group in AI_GROUPS


@dataclass(frozen=True)
class ScreenResult:
    asof: pd.Timestamp
    mode: str
    band: tuple[float, float]
    max_stress_loss: float
    relaxed: bool
    eligible: tuple[Row, ...]
    chosen: tuple[Row, ...]
    watch: tuple[Row, ...]
    measured: tuple[Row, ...]


def _sessions(series: pd.Series) -> pd.Series:
    return series.dropna()


def stress_drawdown(sessions: pd.Series, mode: str, asof: pd.Timestamp) -> float | None:
    """Loss from the window high to `asof`. Zero means the close is the high."""
    if mode == "this_selloff":
        window = sessions.loc[THIS_SELLOFF_START:asof]
    elif mode == "trailing":
        window = sessions.iloc[-TRAILING_STRESS_SESSIONS:]
    else:
        raise ValueError(f"unknown mode {mode}")
    if window.empty:
        return None
    peak = float(window.max())
    if peak <= 0:
        return None
    return float(sessions.loc[asof] / peak - 1.0)


def measure(
    close: pd.Series,
    volume: pd.Series | None,
    asof: pd.Timestamp,
    company: str,
    group: str,
    mode: str,
) -> Row | None:
    sessions = _sessions(close.loc[:asof])
    if sessions.empty or sessions.index[-1] != asof:
        return None
    if len(sessions) < 210:
        return None
    price = float(sessions.loc[asof])
    sma50 = float(sessions.iloc[-50:].mean())
    sma200 = float(sessions.iloc[-200:].mean())
    if sma50 <= 0 or sma200 <= 0:
        return None
    ret_126 = float(price / float(sessions.iloc[-127]) - 1.0)
    stress = stress_drawdown(sessions, mode, asof)
    if stress is None:
        return None
    high20 = float(sessions.iloc[-20:].max())
    dd_20 = float(price / high20 - 1.0) if high20 > 0 else 0.0
    dollar_vol = 0.0
    if volume is not None:
        vol = volume.reindex(sessions.index).iloc[-20:]
        px = sessions.iloc[-20:]
        pair = (px * vol).dropna()
        if len(pair):
            dollar_vol = float(pair.mean())
    ret_contest = None
    pre = _sessions(close.loc[: CONTEST_START - pd.Timedelta(days=1)])
    if not pre.empty and asof >= CONTEST_START:
        base = float(pre.iloc[-1])
        if base > 0:
            ret_contest = float(price / base - 1.0)
    return Row(
        ticker=str(close.name),
        company=company,
        group=group,
        price=price,
        sma50=sma50,
        sma200=sma200,
        ret_126=ret_126,
        stress_dd=stress,
        dollar_vol=dollar_vol,
        dist_sma50=float(price / sma50 - 1.0),
        dd_20=dd_20,
        ret_contest=ret_contest,
    )


def _passes(row: Row, band: tuple[float, float], max_loss: float) -> bool:
    low, high = band
    if row.price < MIN_PRICE:
        return False
    if row.dollar_vol < MIN_DOLLAR_VOL:
        return False
    if row.sma50 <= row.sma200:
        return False
    if row.price <= row.sma200:
        return False
    if row.ret_126 <= 0:
        return False
    if row.stress_dd < -max_loss:
        return False
    if not (low <= row.price / row.sma50 <= high):
        return False
    return True


def _watch(row: Row, max_loss: float) -> bool:
    """Resilient uptrend that is outside the buy band."""
    if row.price < MIN_PRICE or row.dollar_vol < MIN_DOLLAR_VOL:
        return False
    if row.sma50 <= row.sma200 or row.price <= row.sma200:
        return False
    if row.ret_126 <= 0 or row.stress_dd < -max_loss:
        return False
    return True


def select(eligible: Sequence[Row], top_n: int = TOP_N, min_ai: int = MIN_AI) -> tuple[Row, ...]:
    """Least stress loss first, then swap in AI names that are close on that loss."""
    ranked = sorted(eligible, key=lambda r: (r.stress_dd, r.ret_126, r.ai_rank), reverse=True)
    chosen = list(ranked[:top_n])
    available = [r for r in ranked if r.ai]
    target = min(min_ai, len(available))

    def ai_count(rows: Sequence[Row]) -> int:
        return sum(1 for r in rows if r.ai)

    while ai_count(chosen) < target:
        in_book = {r.ticker for r in chosen}
        candidate = next(r for r in available if r.ticker not in in_book)
        non_ai = [r for r in chosen if not r.ai]
        if not non_ai:
            break
        worst = min(non_ai, key=lambda r: (r.stress_dd, r.ret_126, r.ai_rank))
        if candidate.stress_dd < worst.stress_dd - AI_DD_SLACK:
            break
        chosen = [r for r in chosen if r.ticker != worst.ticker]
        chosen.append(candidate)
    order = {r.ticker: i for i, r in enumerate(ranked)}
    chosen.sort(key=lambda r: order[r.ticker])
    return tuple(chosen)


def screen_frame(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    meta: Mapping[str, tuple[str, str]],
    asof: pd.Timestamp,
    mode: str,
) -> ScreenResult:
    asof = pd.Timestamp(asof)
    rows: list[Row] = []
    for ticker, (company, group) in meta.items():
        if ticker not in close.columns:
            continue
        vol = volume[ticker] if ticker in volume.columns else None
        series = close[ticker].copy()
        series.name = ticker
        row = measure(series, vol, asof, company, group, mode)
        if row is not None:
            rows.append(row)

    band = (BAND_LOW, BAND_HIGH)
    max_loss = MAX_STRESS_LOSS
    relaxed = False
    eligible = [r for r in rows if _passes(r, band, max_loss)]
    if len(eligible) < 4:
        band = (RELAXED_BAND_LOW, RELAXED_BAND_HIGH)
        relaxed = True
        eligible = [r for r in rows if _passes(r, band, max_loss)]
    if len(eligible) < 4:
        max_loss = RELAXED_STRESS_LOSS
        eligible = [r for r in rows if _passes(r, band, max_loss)]
    chosen = select(eligible)
    chosen_tickers = {r.ticker for r in chosen}
    watch = tuple(
        sorted(
            (r for r in rows if r.ticker not in chosen_tickers and _watch(r, max_loss)),
            key=lambda r: (r.stress_dd, r.ret_126),
            reverse=True,
        )
    )
    return ScreenResult(
        asof=asof,
        mode=mode,
        band=band,
        max_stress_loss=max_loss,
        relaxed=relaxed,
        eligible=tuple(sorted(eligible, key=lambda r: (r.stress_dd, r.ret_126), reverse=True)),
        chosen=chosen,
        watch=watch,
        measured=tuple(sorted(rows, key=lambda r: (r.stress_dd, r.ret_126), reverse=True)),
    )


def average_pairwise_corr(returns: pd.DataFrame) -> float | None:
    cols = [c for c in returns.columns if returns[c].notna().sum() >= 20]
    if len(cols) < 2:
        return None
    corr = returns[cols].corr()
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    values = corr.where(mask).stack().astype(float)
    if values.empty:
        return None
    return float(values.mean())


def sleeve_weights(chosen: Sequence[Row], trailing_returns: pd.DataFrame) -> dict[str, float]:
    """Equal risk across the chosen names, never more than the base sleeve.

    Names that do not fill the six slots do not get a bigger position. The
    unused sleeve stays in BOXX. If the holdings moved together over the
    last quarter, the sleeve is cut by a quarter.
    """
    if not chosen:
        return {BALLAST: TARGET_GROSS}
    per_name = BASE_SLEEVE / TOP_N
    raw = {row.ticker: per_name for row in chosen}
    sleeve = per_name * len(chosen)
    corr = average_pairwise_corr(trailing_returns)
    if corr is not None and corr > CORR_CUT:
        scale = CORR_SCALE
        raw = {k: v * scale for k, v in raw.items()}
        sleeve *= scale
    boxx = TARGET_GROSS - sleeve
    raw[BALLAST] = boxx
    return raw


def shares_for(
    weights: Mapping[str, float],
    prices: Mapping[str, float],
    fx_sgd_per_usd: float,
    nav_sgd: float = NAV_SGD,
    target_gross: float = TARGET_GROSS,
) -> dict[str, int]:
    """Floor every line, then add BOXX shares until gross reaches the target."""
    if fx_sgd_per_usd <= 0:
        raise ValueError("fx must be SGD per USD")
    usd_nav = nav_sgd / fx_sgd_per_usd
    out: dict[str, int] = {}
    for ticker, weight in weights.items():
        px = prices.get(ticker)
        if px is None or px <= 0 or weight <= 0:
            continue
        out[ticker] = int(math.floor(weight * usd_nav / px))

    def gross(holding: Mapping[str, int]) -> float:
        usd = sum(holding[t] * prices[t] for t in holding)
        return usd * fx_sgd_per_usd / nav_sgd

    if BALLAST not in out:
        out[BALLAST] = 0
    # One BOXX share is a few basis points of NAV. Cap the loop anyway.
    for _ in range(100_000):
        if gross(out) >= target_gross:
            break
        out[BALLAST] += 1
    return {t: n for t, n in out.items() if n > 0}


def position_ratio(
    holding: Mapping[str, int],
    prices: Mapping[str, float],
    fx_sgd_per_usd: float,
    nav_sgd: float = NAV_SGD,
) -> float:
    usd = sum(holding[t] * prices[t] for t in holding)
    return usd * fx_sgd_per_usd / nav_sgd


def max_drawdown(equity: Iterable[float]) -> float:
    series = pd.Series(list(equity), dtype=float)
    if series.empty:
        return 0.0
    peak = series.cummax()
    return float((series / peak - 1.0).min())


def sharpe_ratio(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    sigma = float(r.std(ddof=1))
    if sigma == 0:
        return 0.0
    return float(r.mean() / sigma * math.sqrt(252))


def _friday_signals(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    """Last session of each ISO week, plus the final bar so the book is current."""
    stamps = pd.DatetimeIndex(index)
    week = stamps.to_series().dt.isocalendar().week.astype(int)
    year = stamps.to_series().dt.isocalendar().year.astype(int)
    key = year * 100 + week
    last = stamps.to_series().groupby(key.values).tail(1)
    signals = set(pd.DatetimeIndex(last.index))
    if len(stamps):
        signals.add(pd.Timestamp(stamps[-1]))
    return signals


def run_backtest(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    meta: Mapping[str, tuple[str, str]],
    start: str = "2024-06-03",
    mode: str = "trailing",
) -> pd.DataFrame:
    """Weekly defensive-momentum book. Weights set at the close earn the next session.

    Cash earns zero. BOXX earns its own return. Trades cost 5 bps of notional.
    The stress window here is the trailing 60 sessions, so the path is not
    the autumn-2026 snapshot used for the live book.
    """
    prices = close.sort_index()
    start_ts = pd.Timestamp(start)
    if "SPY" not in prices.columns:
        raise KeyError("SPY is required to define the US session calendar")
    calendar = prices.index[prices["SPY"].notna()]
    asset_ret = prices.pct_change(fill_method=None)
    signals = _friday_signals(calendar)

    dates = list(calendar)
    target = pd.Series(0.0, index=list(meta) + [BALLAST, "CASH"])
    prev = target.copy()
    rows = []
    for i, dt in enumerate(dates):
        dt = pd.Timestamp(dt)
        day_ret = 0.0
        cost = 0.0
        if i > 0:
            held = prev[prev > 0]
            for ticker, weight in held.items():
                if ticker == "CASH":
                    continue
                if ticker not in asset_ret.columns:
                    continue
                r = asset_ret.at[dt, ticker]
                if pd.notna(r):
                    day_ret += float(weight) * float(r)
        if dt >= start_ts and dt in signals:
            result = screen_frame(prices, volume, meta, dt, mode=mode)
            names = [r.ticker for r in result.chosen]
            trail = asset_ret.loc[:dt, names].tail(CORR_LOOKBACK) if names else pd.DataFrame()
            weights = sleeve_weights(result.chosen, trail)
            new = pd.Series(0.0, index=target.index)
            for ticker, weight in weights.items():
                if ticker in new.index:
                    new.at[ticker] = weight
            new.at["CASH"] = max(0.0, 1.0 - float(new.drop(labels=["CASH"]).sum()))
            traded = float((new - prev).abs().sum())
            # The change from the previous close's weights. Charged once, on this close.
            # Skip the charge on the first bar of the loop before the book exists:
            # `prev` starts at zero, so the first signal pays to enter. That is intended.
            cost = traded * COST_ONE_WAY
            prev = new
        held_names = [
            t
            for t in prev.index
            if t not in ("CASH", BALLAST) and float(prev.at[t]) > 0
        ]
        rows.append(
            {
                "date": dt,
                "ret": day_ret - cost,
                "gross": float(prev.drop(labels=["CASH"]).sum()) if len(prev) else 0.0,
                "n_names": len(held_names),
                "held": ",".join(held_names),
            }
        )
    frame = pd.DataFrame(rows).set_index("date")
    frame = frame.loc[start_ts:]
    frame["equity"] = (1.0 + frame["ret"]).cumprod()
    return frame


def path_return(close: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    series = close.loc[start:end].dropna()
    if len(series) < 2 or float(series.iloc[0]) <= 0:
        return None
    return float(series.iloc[-1] / series.iloc[0] - 1.0)


def joint_sleeve_path(
    close: pd.DataFrame,
    tickers: Sequence[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    """Equal-weight sleeve, rebased to 1 at the first common close on or after `start`."""
    cols = [t for t in tickers if t in close.columns]
    window = close.loc[start:end, cols].dropna(how="any")
    if window.empty:
        return pd.Series(dtype=float)
    rebased = window / window.iloc[0]
    return rebased.mean(axis=1)
