"""Download prices, screen the medical universe, and write the dry-run book.

No order is sent. The share list is for the next US session after the
signal close. US cash equities were shut on 26 November 2026.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

from medmom.strategy import (
    BASE_SLEEVE,
    BALLAST,
    CONTEST_START,
    COST_ONE_WAY,
    MAX_STRESS_LOSS,
    MIN_DOLLAR_VOL,
    MIN_PRICE,
    NAV_SGD,
    TARGET_GROSS,
    THIS_SELLOFF_START,
    joint_sleeve_path,
    max_drawdown,
    path_return,
    position_ratio,
    run_backtest,
    screen_frame,
    select,
    sharpe_ratio,
    shares_for,
    sleeve_weights,
)
from medmom.universe import BENCHMARKS, UNIVERSE

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output"
PRICE_START = "2023-01-01"


def _flatten(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = raw.columns.get_level_values(0)
        if "Close" in level0:
            close = raw["Close"].copy()
            volume = raw["Volume"].copy() if "Volume" in level0 else pd.DataFrame(index=raw.index)
        else:
            close = raw.xs("Close", axis=1, level=1).copy()
            volume = raw.xs("Volume", axis=1, level=1).copy()
    else:
        close = raw[["Close"]].copy()
        volume = raw[["Volume"]].copy()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    volume.index = pd.to_datetime(volume.index).tz_localize(None)
    return close.sort_index(), volume.sort_index()


def download(tickers: list[str], start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    closes = []
    volumes = []
    for i in range(0, len(tickers), 40):
        chunk = tickers[i : i + 40]
        raw = yf.download(
            chunk,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if raw is None or raw.empty:
            continue
        close, volume = _flatten(raw)
        closes.append(close)
        volumes.append(volume)
    close = pd.concat(closes, axis=1, sort=True)
    volume = pd.concat(volumes, axis=1, sort=True)
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]
    return close.sort_index(), volume.reindex(close.index)


def load_prices(refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    DATA.mkdir(parents=True, exist_ok=True)
    close_path = DATA / "close.csv"
    volume_path = DATA / "volume.csv"
    if close_path.exists() and volume_path.exists() and not refresh:
        close = pd.read_csv(close_path, index_col=0, parse_dates=True)
        volume = pd.read_csv(volume_path, index_col=0, parse_dates=True)
        return close, volume
    tickers = [n.ticker for n in UNIVERSE] + list(BENCHMARKS)
    # `end` is exclusive in yfinance. Step past the signal day.
    close, volume = download(tickers, PRICE_START, "2026-11-27")
    close.to_csv(close_path)
    volume.to_csv(volume_path)
    return close, volume


def _meta():
    return {n.ticker: (n.company, n.group) for n in UNIVERSE}


def _window_stats(returns: pd.Series, equity: pd.Series) -> dict:
    if returns.empty:
        return {"sharpe": 0.0, "return": 0.0, "max_drawdown": 0.0, "sessions": 0}
    eq = (1.0 + returns).cumprod()
    return {
        "sharpe": sharpe_ratio(returns),
        "return": float(eq.iloc[-1] - 1.0),
        "max_drawdown": max_drawdown(eq),
        "sessions": int(len(returns)),
    }


def _positive_week_share(returns: pd.Series) -> float | None:
    if returns.empty:
        return None
    weekly = (1.0 + returns).resample("W-FRI").prod() - 1.0
    weekly = weekly.dropna()
    if weekly.empty:
        return None
    return float((weekly > 0).mean())


def main() -> None:
    close, volume = load_prices(refresh="--refresh" in sys.argv)
    meta = _meta()
    if "SPY" not in close.columns or BALLAST not in close.columns:
        raise SystemExit("price cache is missing SPY or BOXX")
    asof = pd.Timestamp(close["SPY"].dropna().index[-1])
    fx_series = close["SGD=X"].dropna().loc[:asof]
    fx = float(fx_series.iloc[-1])

    live = screen_frame(close, volume, meta, asof, mode="this_selloff")
    names = [r.ticker for r in live.chosen]
    trail = close[names].pct_change(fill_method=None).loc[:asof].tail(60) if names else pd.DataFrame()
    weights = sleeve_weights(live.chosen, trail)
    prices = {r.ticker: r.price for r in live.chosen}
    prices[BALLAST] = float(close[BALLAST].loc[:asof].dropna().iloc[-1])
    holding = shares_for(weights, prices, fx)
    ratio = position_ratio(holding, prices, fx)

    book = run_backtest(close, volume, meta, start="2024-06-03", mode="trailing")
    anchored = run_backtest(
        close, volume, meta, start="2026-09-01", mode="this_selloff"
    )
    stats = {
        "full": _window_stats(book["ret"], book["equity"]),
        "before_selloff": _window_stats(
            book.loc[: THIS_SELLOFF_START - pd.Timedelta(days=1), "ret"],
            book["equity"],
        ),
        "selloff": _window_stats(book.loc[THIS_SELLOFF_START:, "ret"], book["equity"]),
        "contest": _window_stats(book.loc[CONTEST_START:, "ret"], book["equity"]),
    }
    anchored_stats = _window_stats(anchored["ret"], anchored["equity"])
    stats["full"]["positive_weeks"] = _positive_week_share(book["ret"])

    # Descriptive path of the names chosen today. This uses the same window
    # the screen just ranked, so it is not a forecast.
    sleeve = joint_sleeve_path(close, names, THIS_SELLOFF_START, asof)
    sleeve_dd = max_drawdown(sleeve) if len(sleeve) else None
    sleeve_ret = float(sleeve.iloc[-1] - 1.0) if len(sleeve) else None
    boxx_ret = path_return(close[BALLAST], THIS_SELLOFF_START, asof)
    spy_dd_window = close["SPY"].loc[THIS_SELLOFF_START:asof].dropna()
    spy_stress = float(spy_dd_window.iloc[-1] / spy_dd_window.max() - 1.0)

    def bench_stats(ticker: str) -> dict:
        # Close-to-close from the first session in the book. The first print
        # is the entry, so its prior-day gap is not a return we earned.
        px = close[ticker].reindex(book.index).dropna()
        r = px.pct_change(fill_method=None).dropna()
        return _window_stats(r, (1.0 + r).cumprod())

    summary = {
        "asof": str(asof.date()),
        "fx_sgd_per_usd": fx,
        "nav_sgd": NAV_SGD,
        "relaxed": live.relaxed,
        "band": list(live.band),
        "max_stress_loss": live.max_stress_loss,
        "n_eligible": len(live.eligible),
        "sleeve_budget": BASE_SLEEVE,
        "target_gross": TARGET_GROSS,
        "cost_one_way": COST_ONE_WAY,
        "weights": weights,
        "shares": holding,
        "position_ratio": ratio,
        "spy_stress_drawdown": spy_stress,
        "chosen_joint_selloff_return": sleeve_ret,
        "chosen_joint_selloff_drawdown": sleeve_dd,
        "boxx_selloff_return": boxx_ret,
        "risk_budget_nav": sum(weights[t] for t in names) * MAX_STRESS_LOSS,
        "backtest": stats,
        "spy": bench_stats("SPY"),
        "xlv": bench_stats("XLV"),
        "anchored_selloff": anchored_stats,
        "held_into_contest": _held_on(book, CONTEST_START),
        "held_on_signal_trailing": _held_on(book, asof),
        "held_on_signal_anchored": _held_on(anchored, asof),
    }

    pure = select(live.eligible, min_ai=0)
    summary["pure_least_drawdown"] = [r.ticker for r in pure]
    summary["ai_in_book"] = [r.ticker for r in live.chosen if r.ai]

    OUT.mkdir(parents=True, exist_ok=True)
    _write_rows(OUT / "screen.csv", live.eligible)
    _write_measured(OUT / "measured.csv", live)
    _write_rows(OUT / "book.csv", live.chosen, weights, holding, prices, fx)
    _write_rows(OUT / "watch.csv", live.watch)
    book.to_csv(OUT / "backtest.csv")
    anchored.to_csv(OUT / "backtest_anchored.csv")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=_json))
    _print(summary, live, prices)


def _held_on(book: pd.DataFrame, when: pd.Timestamp) -> str:
    prior = book.loc[:when]
    if prior.empty:
        return ""
    return str(prior["held"].iloc[-1])


def _reason(row, result) -> str:
    if any(r.ticker == row.ticker for r in result.chosen):
        return "in the book"
    if row.price < MIN_PRICE:
        return "price under $8"
    if row.dollar_vol < MIN_DOLLAR_VOL:
        return "thin dollar volume"
    if row.price <= row.sma200:
        return "below the 200-day average"
    if row.sma50 <= row.sma200:
        return "50-day average still under the 200-day"
    if row.ret_126 <= 0:
        return "six-month momentum negative"
    if row.stress_dd < -result.max_stress_loss:
        return "retraced more than the cap"
    ratio = row.price / row.sma50
    if ratio > result.band[1]:
        return "above the buy band"
    if ratio < result.band[0]:
        return "below the buy band"
    return "eligible, not selected"


def _write_measured(path: Path, result) -> None:
    records = []
    for row in result.measured:
        records.append(
            {
                "ticker": row.ticker,
                "company": row.company,
                "group": row.group,
                "price": row.price,
                "stress_dd": row.stress_dd,
                "ret_126": row.ret_126,
                "ret_contest": row.ret_contest,
                "dist_sma50": row.dist_sma50,
                "dollar_vol": row.dollar_vol,
                "reason": _reason(row, result),
            }
        )
    pd.DataFrame(records).to_csv(path, index=False)


def _write_rows(path: Path, rows, weights=None, holding=None, prices=None, fx=None) -> None:
    records = []
    for row in rows:
        rec = {
            "ticker": row.ticker,
            "company": row.company,
            "group": row.group,
            "price": row.price,
            "stress_dd": row.stress_dd,
            "ret_126": row.ret_126,
            "ret_contest": row.ret_contest,
            "dist_sma50": row.dist_sma50,
            "sma50": row.sma50,
            "sma200": row.sma200,
            "dd_20": row.dd_20,
            "dollar_vol": row.dollar_vol,
        }
        if weights is not None:
            rec["weight"] = weights.get(row.ticker, 0.0)
            rec["shares"] = holding.get(row.ticker, 0)
            rec["market_value_sgd"] = holding.get(row.ticker, 0) * prices[row.ticker] * fx
        records.append(rec)
    pd.DataFrame(records).to_csv(path, index=False)


def _json(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    raise TypeError(type(value))


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2%}"


def _print(summary: dict, live, prices: dict) -> None:
    print(f"signal close {summary['asof']}  USD/SGD {summary['fx_sgd_per_usd']:.5f}")
    print(
        f"eligible {summary['n_eligible']}  relaxed {summary['relaxed']}  "
        f"position ratio {summary['position_ratio']:.3f}  "
        f"risk budget {summary['risk_budget_nav']:.2%} of NAV"
    )
    print(
        f"SPY stress drawdown {_pct(summary['spy_stress_drawdown'])}  "
        f"today's sleeve over that same window {_pct(summary['chosen_joint_selloff_return'])} "
        f"path dd {_pct(summary['chosen_joint_selloff_drawdown'])}"
    )
    print("book")
    for row in live.chosen:
        sh = summary["shares"].get(row.ticker, 0)
        print(
            f"  BUY {sh:5d} {row.ticker:5} {row.group:11} "
            f"px {row.price:8.2f}  stress {row.stress_dd:+.2%}  "
            f"6m {row.ret_126:+.2%}  vs 50d {row.dist_sma50:+.2%}  {row.company}"
        )
    boxx = summary["shares"].get(BALLAST, 0)
    print(f"  BUY {boxx:5d} BOXX  px {prices[BALLAST]:8.2f}  ballast")
    bt = summary["backtest"]
    print(
        "trailing-60d rule, weekly, 2024-06-03 to signal: "
        f"sharpe {bt['full']['sharpe']:.2f}  "
        f"return {_pct(bt['full']['return'])}  "
        f"max dd {_pct(bt['full']['max_drawdown'])}"
    )
    print(
        "same trailing rule through the selloff from 2026-09-01: "
        f"sharpe {bt['selloff']['sharpe']:.2f}  "
        f"return {_pct(bt['selloff']['return'])}  "
        f"max dd {_pct(bt['selloff']['max_drawdown'])}"
    )
    anch = summary["anchored_selloff"]
    print(
        "selloff-window rule from 2026-09-01 (the rule behind today's book): "
        f"sharpe {anch['sharpe']:.2f}  "
        f"return {_pct(anch['return'])}  "
        f"max dd {_pct(anch['max_drawdown'])}  "
        f"last book {summary['held_on_signal_anchored']}"
    )
    print("dry run only. nothing was sent to IBKR.")


if __name__ == "__main__":
    main()
