# Defensive medical momentum

A long-only book for Diamond Strategy on the Singapore IBKR paper account (about 1,000,000 SGD, contest close 27 January 2027). It buys medical names that kept an uptrend and gave back the least in the autumn 2026 selloff, and holds BOXX so the account is not flat.

Nothing here is sent to a broker. The share list is a dry run for the next US cash session after the 25 November 2026 close. The 26th was Thanksgiving.

## Why this shape

The board, as the team has been reading it, puts 35% on Sharpe, 25% on return, 25% on max drawdown and 15% on stability. Drawdown and Sharpe are most of the score. From the September peak to 25 November, SPY was down about 8% and QQQ about 16%. Healthcare as a group was not. The pure computational-drug names were worse than the Nasdaq: Tempus and Recursion were down roughly 36% and 45% from their window highs.

The book takes the other side of that. It wants names that are still in a six-month uptrend, still above a rising 200-day average, and sitting within a few percent of the 50-day average, so the entry is not a chase. Among those, it prefers the smallest loss from the high since 1 September 2026. An AI-linked name can replace a plainer medical name only when its loss is within 3 percentage points.

The sleeve is 15% of NAV, split across six names. A repeat of the 8% eligibility loss in every name at once is 1.2% of NAV. BOXX brings the gross position ratio to 60%. Cash does not count toward the ratio, and the ten allowed flat days are already used. BOXX does count. There are no shorts.

The 50% holding floor is the team's reading of rule 4.2. The organizer defined the ratio as (absolute long market value + absolute short market value) / NAV and did not state 50% in the messages we have. Sixty percent clears that reading with room.

## Run

From this directory, with the packages in `requirements.txt`:

```bash
python3 -m unittest tests.test_strategy
python3 -m medmom
python3 -m medmom --refresh
```

The first run reads `data/close.csv` and `data/volume.csv` when those files are present. `--refresh` downloads adjusted Yahoo prices again. Output lands in `output/`.

Each Friday close, refresh and read `output/book.csv`. A name that leaves the band, loses its six-month gain, or breaks the 200-day average is sold and that weight stays in BOXX until the next name qualifies. Do not take the account to cash.

## Signal on 25 November 2026

USD/SGD 1.28935. Position ratio 0.600. Risk budget 1.2% of NAV.

| Order | Ticker | What it is | Stress loss | Six-month | vs 50-day | SGD |
| --- | --- | --- | --- | --- | --- | --- |
| Buy 266 | TECH | Bio-Techne | -0.2% | +43% | +0.2% | 24,917 |
| Buy 65 | ABBV | AbbVie | -1.9% | +36% | +5.1% | 24,680 |
| Buy 391 | QGEN | Qiagen | -2.7% | +36% | +4.0% | 24,960 |
| Buy 78 | RMD | ResMed | -2.7% | +21% | +4.9% | 24,710 |
| Buy 108 | A | Agilent | -2.8% | +32% | +3.3% | 24,848 |
| Buy 228 | DXCM | Dexcom | -5.9% | +17% | +1.2% | 24,941 |
| Buy 2,934 | BOXX | Treasury bill ETF | | | | ballast |

Dexcom is the AI-applied holding (algorithmic glucose sensing). It replaced Johnson & Johnson, which had a smaller stress loss (-3.7%) but no AI angle. The swap stays inside the 3-point slack. AbbVie is the most extended name still allowed: 5.1% above its 50-day, against a 6% cap.

GE HealthCare, IDEXX, Quest and Labcorp also held up, and they are closer to "AI in the product" than AbbVie is. They are 8% to 20% above the 50-day average, so they are on the watch list rather than in the order. Tempus, Recursion, Schrödinger, Guardant, Natera, Illumina and 10x failed the retrace test. Their losses from the window high were 18% to 45%.

## What the path actually did

Two tests, both charged 5 bps of traded notional, with cash earning zero and BOXX earning its own return. Sharpe uses a zero risk-free rate and the square root of 252, on the whole NAV.

The rolling rule (trailing 60-session loss, same trend and buy-band filters, weekly) from 3 June 2024 to 25 November 2026: Sharpe 1.50, return +10.1%, max drawdown -2.89%. Through the selloff from 1 September 2026 that same rolling rule made +2.66% with a max drawdown of -0.80%.

The rule behind today's orders fixes the stress window at 1 September 2026 and walks forward one week at a time. From 1 September to 25 November: Sharpe 1.79, return +1.14%, max drawdown -1.04%. The book on the last close is the order above. That path is short, and a Sharpe on sixty sessions moves around.

The equal-weight path of these six names from 1 September was +8.1%, with a path drawdown of -4.0%. That figure uses the window the screen just ranked. It is a description of the survivors, not a forecast through 27 January.

## Limits

Yahoo adjusted closes, downloaded 26 November 2026. Exact Sciences and Hologic returned no prices and are absent. The universe is the names in `medmom/universe.py` that are listed now, so the long backtest never sees a medical stock that has since disappeared. The contest's stability term is not defined in the messages we have, so it is not in the rank. The gold sleeve from the earlier study stays flat. This book is the risk sleeve.
