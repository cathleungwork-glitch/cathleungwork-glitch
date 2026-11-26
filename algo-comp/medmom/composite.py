"""25% sleeve: 10% weekly dip-hold plus 15% three-day bounces.

The other 50–60% of the account is the teammates' book. Whatever is left,
including any of this 25% that the rules do not put into a stock, is BOXX.
This module does not trade BOXX and does not forecast the teammates.

Both pieces buy a retracement inside an uptrend. A name at its high is
skipped. Weights follow a score built from the six-month run and how close
the pullback is to a 7% dip. That score is the stand-in for a company
performance forecast: the backtest can recompute it every day. It is not
an earnings estimate.

A weekly hold is entered at Friday's close, or at the last session of a
holiday week, and earns from the next session. A bounce is a down day
followed by an up day while the shares are 3–10% under the 20-session high.
The bounce is held for the next three sessions.
"""

from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

from medmom.strategy import COST_ONE_WAY, _friday_signals, max_drawdown, sharpe_ratio
from medmom.universe import AI_RANK

NAV_SGD = 1_000_000.0
HOLD_BUDGET = 0.10
TRADE_BUDGET = 0.15
NAME_HOLD_CAP = 0.04
NAME_TRADE_CAP = 0.05
COMBINED_CAP = 0.08
HOLD_SLOTS = 4
TRADE_SLOTS = 5
HOLD_DAYS = 3
MIN_PRICE = 8.0
MIN_DOLLAR_VOL = 15_000_000.0
# Pullback band for the weekly hold. Shallower than 4% is still "at the top".
HOLD_DD_SHALLOW = -0.04
HOLD_DD_DEEP = -0.12
HOLD_DD_DEEP_RELAXED = -0.18
# A few-day dip for the bounce book.
TRADE_DD_SHALLOW = -0.03
TRADE_DD_DEEP = -0.10
SWEET_DD = -0.07
FORWARD_SESSIONS = 40


def hold_score(ret_126: float, drawdown: float, ai_rank: int) -> float:
    """Higher when the six-month run is strong and the dip is near 7%."""
    pull = 1.0 - abs(drawdown - SWEET_DD) / 0.08
    pull = max(0.0, min(1.0, pull))
    momentum = min(max(ret_126, 0.0), 0.50) / 0.50
    ai = ai_rank / 2.0
    return 0.55 * momentum + 0.35 * pull + 0.10 * ai


def trade_score(ret_126: float, prior_day: float, ai_rank: int) -> float:
    """Higher when the down day being reversed was sharper, inside a strong trend."""
    fuel = min(abs(min(prior_day, 0.0)), 0.04) / 0.04
    momentum = min(max(ret_126, 0.0), 0.50) / 0.50
    ai = ai_rank / 2.0
    return 0.60 * fuel + 0.30 * momentum + 0.10 * ai


def allocate_hold(scored: list[tuple[str, float]]) -> dict[str, float]:
    chosen = [(t, s) for t, s in scored if s > 0][:HOLD_SLOTS]
    if not chosen:
        return {}
    total = sum(s for _, s in chosen)
    weights = {t: HOLD_BUDGET * s / total for t, s in chosen}
    return {t: min(w, NAME_HOLD_CAP) for t, w in weights.items() if w > 0}


def allocate_trades(
    scored: list[tuple[str, float]],
    hold: Mapping[str, float],
    open_weights: Mapping[str, float],
) -> dict[str, float]:
    room = TRADE_BUDGET - sum(open_weights.values())
    if room <= 1e-9:
        return {}
    fresh = [(t, s) for t, s in scored if s > 0 and t not in open_weights][:TRADE_SLOTS]
    if not fresh:
        return {}
    total = sum(s for _, s in fresh)
    weights = {t: room * s / total for t, s in fresh}
    capped: dict[str, float] = {}
    for ticker, weight in weights.items():
        cap = min(NAME_TRADE_CAP, COMBINED_CAP - hold.get(ticker, 0.0))
        taken = min(weight, max(0.0, cap))
        if taken > 1e-6:
            capped[ticker] = taken
    return capped


def _panels(close: pd.DataFrame, volume: pd.DataFrame, meta: Mapping[str, tuple[str, str]]):
    calendar = close.index[close["SPY"].notna()]
    tickers = [t for t in meta if t in close.columns]
    px = close[tickers].reindex(calendar).astype(float)
    vol = volume.reindex(index=calendar, columns=tickers).astype(float)
    ret1 = px.pct_change(fill_method=None)
    return {
        "px": px,
        "ret1": ret1,
        "sma50": px.rolling(50).mean(),
        "sma200": px.rolling(200).mean(),
        "ret126": px / px.shift(126) - 1.0,
        "ret5": px / px.shift(5) - 1.0,
        "ret3": px / px.shift(3) - 1.0,
        "dd63": px / px.rolling(63).max() - 1.0,
        "dd20": px / px.rolling(20).max() - 1.0,
        "adv": (px * vol).rolling(20).mean(),
        "prior": ret1.shift(1),
        "ai": pd.Series({t: AI_RANK.get(meta[t][1], 0) for t in tickers}),
        "company": {t: meta[t][0] for t in tickers},
        "group": {t: meta[t][1] for t in tickers},
    }


def _trend_mask(panels, dt: pd.Timestamp) -> pd.Series:
    px = panels["px"].loc[dt]
    return (
        (px >= MIN_PRICE)
        & (panels["adv"].loc[dt] >= MIN_DOLLAR_VOL)
        & (px > panels["sma200"].loc[dt])
        & (panels["sma50"].loc[dt] > panels["sma200"].loc[dt])
        & (panels["ret126"].loc[dt] > 0)
    )


def _scored_hold(panels, dt: pd.Timestamp, deep: float, turn: pd.Series) -> list[tuple[str, float]]:
    mask = (
        _trend_mask(panels, dt)
        & (panels["dd63"].loc[dt] <= HOLD_DD_SHALLOW)
        & (panels["dd63"].loc[dt] >= deep)
        & (turn > 0)
    )
    scored = []
    for ticker in mask.index[mask.fillna(False)]:
        dd = float(panels["dd63"].at[dt, ticker])
        ret = float(panels["ret126"].at[dt, ticker])
        scored.append((ticker, hold_score(ret, dd, int(panels["ai"][ticker]))))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def pick_hold(panels, dt: pd.Timestamp) -> dict[str, float]:
    strict = _scored_hold(panels, dt, HOLD_DD_DEEP, panels["ret5"].loc[dt])
    pool = strict if len(strict) >= 3 else _scored_hold(panels, dt, HOLD_DD_DEEP_RELAXED, panels["ret3"].loc[dt])
    return allocate_hold(pool)


def pick_trades(panels, dt: pd.Timestamp, hold: Mapping[str, float], open_weights: Mapping[str, float]) -> dict[str, float]:
    prior = panels["prior"].loc[dt]
    today = panels["ret1"].loc[dt]
    mask = (
        _trend_mask(panels, dt)
        & (panels["dd20"].loc[dt] <= TRADE_DD_SHALLOW)
        & (panels["dd20"].loc[dt] >= TRADE_DD_DEEP)
        & (today > 0)
        & (prior < 0)
    )
    scored = []
    for ticker in mask.index[mask.fillna(False)]:
        scored.append(
            (
                ticker,
                trade_score(
                    float(panels["ret126"].at[dt, ticker]),
                    float(prior[ticker]),
                    int(panels["ai"][ticker]),
                ),
            )
        )
    scored.sort(key=lambda item: item[1], reverse=True)
    return allocate_trades(scored, hold, open_weights)


def run_composite(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    meta: Mapping[str, tuple[str, str]],
    start: str = "2024-06-03",
) -> tuple[pd.DataFrame, dict]:
    """Walk the sleeve forward. Weights decided at a close earn from the next session."""
    panels = _panels(close, volume, meta)
    dates = list(panels["px"].index)
    signals = _friday_signals(panels["px"].index)
    start_ts = pd.Timestamp(start)
    hold_active: dict[str, float] = {}
    trade_active: dict[str, float] = {}
    trade_left: dict[str, int] = {}
    queued: dict[str, float] = {}
    rows = []
    live: dict = {"date": None, "hold": {}, "new_trades": {}, "open_trades": {}, "left": {}}

    for i, dt in enumerate(dates):
        dt = pd.Timestamp(dt)
        if queued:
            for ticker, weight in queued.items():
                trade_active[ticker] = weight
                trade_left[ticker] = HOLD_DAYS
            queued = {}

        hold_ret = 0.0
        trade_ret = 0.0
        hold_cost = 0.0
        trade_cost = 0.0
        if i > 0:
            for ticker, weight in hold_active.items():
                change = panels["ret1"].at[dt, ticker]
                if pd.notna(change):
                    hold_ret += weight * float(change)
            for ticker, weight in trade_active.items():
                change = panels["ret1"].at[dt, ticker]
                if pd.notna(change):
                    trade_ret += weight * float(change)

        finished = [t for t, left in trade_left.items() if left <= 1]
        for ticker in finished:
            trade_cost += trade_active.pop(ticker, 0.0) * COST_ONE_WAY
            trade_left.pop(ticker, None)
        for ticker in list(trade_left):
            trade_left[ticker] -= 1

        if dt >= start_ts and dt in signals:
            new_hold = pick_hold(panels, dt)
            for ticker in list(new_hold):
                room = COMBINED_CAP - trade_active.get(ticker, 0.0)
                new_hold[ticker] = min(new_hold[ticker], max(0.0, room))
                if new_hold[ticker] <= 1e-6:
                    del new_hold[ticker]
            hold_cost += _traded(hold_active, new_hold) * COST_ONE_WAY
            hold_active = new_hold
            fresh = pick_trades(panels, dt, hold_active, trade_active)
            # A Friday bounce is still a three-day trade. The hold rebalance
            # does not cancel it. pick_trades already skips names with an open trade.
            for ticker, weight in fresh.items():
                trade_cost += weight * COST_ONE_WAY
            queued = fresh
        elif dt >= start_ts:
            fresh = pick_trades(panels, dt, hold_active, trade_active)
            for ticker, weight in fresh.items():
                trade_cost += weight * COST_ONE_WAY
            queued = fresh

        if dt >= start_ts:
            live = {
                "date": dt,
                "hold": dict(hold_active),
                "new_trades": dict(queued),
                "open_trades": dict(trade_active),
                "left": dict(trade_left),
            }
            rows.append(
                {
                    "date": dt,
                    "ret": hold_ret + trade_ret - hold_cost - trade_cost,
                    "hold_ret": hold_ret - hold_cost,
                    "trade_ret": trade_ret - trade_cost,
                    "hold_gross": sum(hold_active.values()),
                    "trade_gross": sum(trade_active.values()) + sum(queued.values()),
                    "n_hold": len(hold_active),
                    "n_trade": len(trade_active) + len(queued),
                    "hold": ",".join(sorted(hold_active)),
                    "trades": ",".join(sorted(set(trade_active) | set(queued))),
                }
            )

    frame = pd.DataFrame(rows).set_index("date")
    frame["equity"] = (1.0 + frame["ret"]).cumprod()
    return frame, live


def _traded(old: Mapping[str, float], new: Mapping[str, float]) -> float:
    keys = set(old) | set(new)
    return float(sum(abs(new.get(k, 0.0) - old.get(k, 0.0)) for k in keys))


def forward_returns(returns: pd.Series, sessions: int = FORWARD_SESSIONS) -> pd.Series:
    """Return from each close to the close `sessions` trading days later."""
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    return equity.shift(-sessions) / equity - 1.0


def summarize(frame: pd.DataFrame) -> dict:
    returns = frame["ret"]
    window = forward_returns(returns).dropna()
    equity = frame["equity"]
    return {
        "sessions": int(len(returns)),
        "sharpe": sharpe_ratio(returns),
        "return": float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
        "max_drawdown": max_drawdown(equity),
        "avg_hold_gross": float(frame["hold_gross"].mean()) if len(frame) else 0.0,
        "avg_trade_gross": float(frame["trade_gross"].mean()) if len(frame) else 0.0,
        "days_with_a_trade": int((frame["n_trade"] > 0).sum()) if len(frame) else 0,
        "hold_return": float((1.0 + frame["hold_ret"]).prod() - 1.0) if "hold_ret" in frame else None,
        "trade_return": float((1.0 + frame["trade_ret"]).prod() - 1.0) if "trade_ret" in frame else None,
        "hold_max_drawdown": max_drawdown((1.0 + frame["hold_ret"]).cumprod()) if "hold_ret" in frame else None,
        "trade_max_drawdown": max_drawdown((1.0 + frame["trade_ret"]).cumprod()) if "trade_ret" in frame else None,
        "forward_40": {
            "median": float(window.median()) if len(window) else None,
            "p10": float(window.quantile(0.10)) if len(window) else None,
            "p25": float(window.quantile(0.25)) if len(window) else None,
            "p75": float(window.quantile(0.75)) if len(window) else None,
        },
    }


def shares_for_sleeve(
    weights: Mapping[str, float],
    prices: Mapping[str, float],
    fx_sgd_per_usd: float,
    nav_sgd: float = NAV_SGD,
) -> dict[str, int]:
    if fx_sgd_per_usd <= 0:
        raise ValueError("fx must be SGD per USD")
    usd = nav_sgd / fx_sgd_per_usd
    out = {}
    for ticker, weight in weights.items():
        px = prices.get(ticker)
        if px is None or px <= 0 or weight <= 0:
            continue
        out[ticker] = int(math.floor(weight * usd / px))
    return {t: n for t, n in out.items() if n > 0}


def main() -> None:
    import json
    from pathlib import Path

    from medmom.__main__ import _meta, load_prices

    close, volume = load_prices(refresh="--refresh" in __import__("sys").argv)
    frame, live = run_composite(close, volume, _meta())
    panels = _panels(close, volume, _meta())
    asof = pd.Timestamp(live["date"])
    hold_rows = describe_book(panels, asof, live["hold"], "hold")
    open_rows = describe_book(panels, asof, live["open_trades"], "open_trade")
    new_rows = describe_book(panels, asof, live["new_trades"], "new_trade")
    # Orders to place from a standing start are the weekly hold plus any bounce
    # that signalled at this close. Trades opened on earlier days are only
    # still on if this book was already running.
    to_place: dict[str, float] = {}
    for row in hold_rows + new_rows:
        to_place[row["ticker"]] = to_place.get(row["ticker"], 0.0) + row["weight"]
    fx = float(close["SGD=X"].dropna().loc[:asof].iloc[-1])
    prices = {t: float(panels["px"].at[asof, t]) for t in list(to_place) + [r["ticker"] for r in open_rows]}
    holding = shares_for_sleeve(to_place, prices, fx)
    stats = summarize(frame)
    pre = frame.loc[: pd.Timestamp("2026-08-31"), "ret"]
    pre_fwd = forward_returns(pre).dropna()
    selloff = frame.loc[pd.Timestamp("2026-09-01") :]
    selloff_eq = (1.0 + selloff["ret"]).cumprod()
    boxx = close["BOXX"].reindex(frame.index).dropna()
    boxx_fwd = forward_returns(boxx.pct_change(fill_method=None).dropna()).dropna()
    summary = {
        "asof": str(asof.date()),
        "fx_sgd_per_usd": fx,
        "stats": stats,
        "forward_40_before_sep_2026": {
            "median": float(pre_fwd.median()) if len(pre_fwd) else None,
            "p10": float(pre_fwd.quantile(0.10)) if len(pre_fwd) else None,
            "p25": float(pre_fwd.quantile(0.25)) if len(pre_fwd) else None,
            "p75": float(pre_fwd.quantile(0.75)) if len(pre_fwd) else None,
            "windows": int(len(pre_fwd)),
        },
        "selloff_return": float(selloff_eq.iloc[-1] - 1.0) if len(selloff_eq) else None,
        "selloff_max_drawdown": max_drawdown(selloff_eq) if len(selloff_eq) else None,
        "boxx_forward_40_median": float(boxx_fwd.median()) if len(boxx_fwd) else None,
        "hold": hold_rows,
        "open_trades": open_rows,
        "new_trades": new_rows,
        "trade_days_left": live["left"],
        "shares": holding,
        "sleeve_gross": sum(to_place.values()),
    }
    out = Path(__file__).resolve().parents[1] / "output"
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "composite_backtest.csv")
    pd.DataFrame(hold_rows + open_rows + new_rows).to_csv(out / "composite_book.csv", index=False)
    (out / "composite_summary.json").write_text(json.dumps(summary, indent=2))
    _print(summary)


def _print(summary: dict) -> None:
    stats = summary["stats"]
    fwd = summary["forward_40_before_sep_2026"]
    print(f"signal {summary['asof']}  sleeve gross {summary['sleeve_gross']:.1%} of NAV")
    print(
        f"since Jun 2024: sharpe {stats['sharpe']:.2f}  "
        f"return {stats['return']:+.2%}  max dd {stats['max_drawdown']:+.2%}  "
        f"avg hold {stats['avg_hold_gross']:.1%}  avg trades {stats['avg_trade_gross']:.1%}"
    )
    print(
        f"hold piece {stats['hold_return']:+.2%}  max dd {stats['hold_max_drawdown']:+.2%}  "
        f"trade piece {stats['trade_return']:+.2%}  max dd {stats['trade_max_drawdown']:+.2%}"
    )
    print(
        f"40-session sleeve return before Sep 2026, median {fwd['median']:+.2%}, "
        f"p10 {fwd['p10']:+.2%}, p75 {fwd['p75']:+.2%}  ({fwd['windows']} windows)"
    )
    print(
        f"this rule from 1 Sep 2026: {summary['selloff_return']:+.2%}  "
        f"max dd {summary['selloff_max_drawdown']:+.2%}"
    )
    print("weekly hold")
    for row in summary["hold"]:
        shares = summary["shares"].get(row["ticker"], 0)
        print(
            f"  {row['ticker']:5} {row['weight']:.1%}  {shares:5d} sh  "
            f"off 63d high {row['dd63']:+.1%}  6m {row['ret126']:+.1%}  {row['company']}"
        )
    print("trades already open")
    if not summary["open_trades"]:
        print("  none")
    for row in summary["open_trades"]:
        left = summary["trade_days_left"].get(row["ticker"])
        print(f"  {row['ticker']:5} {row['weight']:.1%}  sessions left {left}  {row['company']}")
    print("new three-day trades, first session is the next open")
    if not summary["new_trades"]:
        print("  none")
    for row in summary["new_trades"]:
        print(
            f"  {row['ticker']:5} {row['weight']:.1%}  off 20d high {row['dd20']:+.1%}  {row['company']}"
        )


def describe_book(panels, dt: pd.Timestamp, weights: Mapping[str, float], kind: str) -> list[dict]:
    rows = []
    for ticker, weight in sorted(weights.items(), key=lambda item: -item[1]):
        rows.append(
            {
                "sleeve": kind,
                "ticker": ticker,
                "company": panels["company"].get(ticker, ticker),
                "group": panels["group"].get(ticker, ""),
                "weight": weight,
                "price": float(panels["px"].at[dt, ticker]),
                "dd63": float(panels["dd63"].at[dt, ticker]),
                "dd20": float(panels["dd20"].at[dt, ticker]),
                "ret126": float(panels["ret126"].at[dt, ticker]),
                "ret5": float(panels["ret5"].at[dt, ticker]),
            }
        )
    return rows


if __name__ == "__main__":
    main()
