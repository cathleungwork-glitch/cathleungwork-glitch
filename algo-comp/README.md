# 25% medical sleeve

This book uses 25% of the 1,000,000 SGD account. Teammates use about 50–60%. Whatever is left, including any of this 25% that is not in a stock, goes to BOXX. The code does not trade BOXX and does not forecast the teammates. Nothing is sent to a broker.

The 25% is split in two.

- **10%, reviewed every Friday.** A medical name in an uptrend, with positive six-month momentum, 4–12% below its 63-session high, and a positive last five sessions. A name at its high is skipped. If fewer than three names qualify, the dip may be as deep as 18% and the turn may be three sessions. Up to four names. The weight is a score that prefers a strong six-month run and a dip near 7%. No name is more than 4% of NAV.
- **15%, held for three sessions.** The same uptrend, 3–10% below the 20-session high, on the day an up close follows a down close. The weight follows the size of that down day and the six-month run. No name is more than 5% of NAV, and a name cannot exceed 8% across both pieces. If nothing signals, this 15% stays out.

From this directory:

```bash
python3 -m unittest tests.test_composite tests.test_strategy
python3 -m medmom.composite
python3 -m medmom.composite --refresh
```

## Backtest

Yahoo adjusted closes, 3 June 2024 through 25 November 2026. Cash earns zero. Each buy or sell costs 5 bps. The figures are fractions of the whole account.

The combined sleeve: Sharpe -0.16, return -2.76%, worst dip -10.63%. The weekly hold alone was +0.93% with a worst dip of -3.60%. The three-day book was -3.51% with a worst dip of -9.54%. The short trades are what blows the drawdown. They stay in the code because the sleeve was asked to keep a 15% short-term book. The record does not support filling that 15% when the contest score is heavy on drawdown.

Before September 2026, 523 completed 40-session windows had a median sleeve contribution of -0.22%, a 10th percentile of -3.12%, and a 75th percentile of +1.13%. Forty sessions reaches from the 27 November 2026 open to about the 27 January 2027 close. From 1 September 2026 to 25 November the same rule lost 2.54%, and the worst dip was 4.32% of the account.

The median is the base case for this sleeve only. It is the middle of the rule's own history, not a price target. Teammates' 50–60% is outside it. BOXX on the residual earns a Treasury-bill drift, which is small next to these swings.

## Orders to place from a standing start

Signal close 25 November 2026, USD/SGD 1.28935. No three-day signal fired, so the 15% stays out. Buy the weekly hold at the 27 November open.

| Order | Off the 63-session high | Six months | About |
| --- | --- | --- | --- |
| Buy 119 ICLR | -7.8% | +45% | 30,500 SGD |
| Buy 1,020 RLAY | -10.5% | +31% | 24,000 SGD |
| Buy 168 ABT | -6.5% | +27% | 23,400 SGD |
| Buy 200 DXCM | -6.8% | +17% | 21,900 SGD |

Relay is the computational-discovery name. Dexcom is the device. ICON is contract research. Abbott is the large-cap. Weights follow the score. Revvity, Medpace, Bruker, Waters and Thermo Fisher still had one session left inside the backtest. Their entry was on an earlier day, so they are not orders for a book that starts now.

Run the script each Friday for the 10%, and each afternoon for the 15%. A three-day name comes off after the third session.

## The earlier resilience screen

`python3 -m medmom` is the previous screen: names that gave back the least and were still near the 50-day average. From June 2024 that path had Sharpe 1.50, return +10.1%, and a worst dip of -2.89%. It buys the names that did not fall. This sleeve buys the dip instead, which is why the backtest looks different. Exact Sciences and Hologic had no prices. The universe is the names listed in `medmom/universe.py` today, so a stock that has disappeared is missing from the long path.
