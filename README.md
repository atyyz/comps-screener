# Equity Comps Screener

A single-file Python script that builds a comparable-company ("comps") table for
any set of tickers using free Yahoo Finance data — no API key, no account.

For each ticker it pulls five metrics, prints them as a table sorted cheapest-first
by P/E, writes a CSV, and saves a bar chart comparing P/E across the peer set.

## What you get

Running the script produces three things:

| Output | What it is |
| --- | --- |
| Terminal table | All metrics, sorted by P/E ascending, missing values shown as `N/A` |
| `comps_output.csv` | The same table, numbers kept numeric so it opens cleanly in Excel |
| `comps_chart.png` | Bar chart of trailing P/E across the tickers, values labelled |

## Setup

Requires Python 3.9 or newer.

```bash
python -m pip install -r requirements.txt
```

**Windows note.** If `python` resolves to `...\AppData\Local\Microsoft\WindowsApps\python.exe`,
that is a packaged-app shim rather than the interpreter itself. It runs, but it
gets a sandboxed view of the filesystem and may fail to see files in folders
under `AppData\Roaming` — pip will report `Could not open requirements file` for
a path that plainly exists. If that happens, call the real interpreter directly,
e.g. `C:\Users\<you>\AppData\Local\Python\pythoncore-3.14-64\python.exe`, or
re-run the installer with "Add python.exe to PATH" ticked.

## Running it

```bash
python comps_screener.py
```

It takes a few seconds per ticker — each one is a live request to Yahoo Finance,
so you need an internet connection.

Actual output from a run on 15 September 2026 — the data is live, so your numbers
will differ:

```
Pulling data for 5 tickers...

  AAPL
  MSFT
  GOOGL
  AMZN
  META

==========================================================================================
COMPS TABLE - sorted by P/E ascending (5 companies)
==========================================================================================
Ticker               Company   P/E EV/EBITDA  ROE % Debt/Equity Rev CAGR 3Y %
 GOOGL         Alphabet Inc. 17.29     24.08  48.68        0.19         12.51
  AMZN      Amazon.com, Inc. 20.13     16.95  30.56        0.46         11.73
  META  Meta Platforms, Inc. 25.10     15.66  29.85        0.43         19.89
  MSFT Microsoft Corporation 27.84     19.59  34.04        0.29         16.12
  AAPL            Apple Inc. 37.75     29.07 148.75        0.78          1.81
==========================================================================================

Saved table to comps_output.csv
Saved chart to comps_chart.png
```

Tested on Python 3.14.7 with yfinance 1.7.0, pandas 3.0.5 and matplotlib 3.11.2.

## What each metric means

**P/E (trailing price-to-earnings)** — share price divided by the last twelve
months of earnings per share. Roughly "how many years of current earnings you're
paying for." Lower usually means cheaper, but it can also mean the market expects
earnings to fall. Companies that lost money have no meaningful P/E and will show
`N/A`.

**EV/EBITDA (enterprise value to EBITDA)** — enterprise value (market cap plus
net debt) divided by earnings before interest, tax, depreciation and amortisation.
The capital-structure-neutral cousin of P/E: because it uses enterprise value
rather than equity value, it compares fairly across companies with very different
debt loads. This is the multiple most often used in actual comps analysis.

**ROE % (return on equity)** — net income divided by shareholders' equity, as a
percentage. How much profit the company generates per dollar of equity capital.
Higher is better, but be careful: heavy debt or large buybacks shrink the equity
base and can inflate ROE without the business getting any better.

**Debt/Equity** — total debt divided by shareholders' equity, expressed as a
ratio (0.50 means fifty cents of debt per dollar of equity). A leverage gauge.
Yahoo reports this as a percentage, so the script divides by 100 to give the
conventional ratio. Companies with negative equity (often from large buybacks)
produce odd or negative values here.

**Rev CAGR 3Y %** — three-year compound annual growth rate of revenue, computed
from the annual income statement as `(newest / oldest) ** (1/3) - 1`. Smooths
year-to-year lumpiness into a single annualised growth number. If a company has
fewer than four years of reported annual statements, the script falls back to the
longest span available rather than dropping the metric.

## Swapping in a different ticker list

Edit the `TICKERS` list near the top of `comps_screener.py`:

```python
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
```

Replace it with whatever peer set you want. Use Yahoo Finance ticker symbols —
for non-US listings that means the exchange suffix (`SAP.DE`, `7203.T`,
`SHEL.L`, `RELIANCE.NS`). A few examples:

```python
TICKERS = ["JPM", "BAC", "WFC", "C", "GS"]            # US money-center banks
TICKERS = ["XOM", "CVX", "COP", "EOG", "SLB"]         # energy
TICKERS = ["PFE", "MRK", "JNJ", "ABBV", "LLY"]        # large-cap pharma
```

The list can be any length — the chart widens automatically. Two other knobs sit
right below it: `CAGR_YEARS` (default 3) changes the growth lookback, and
`CSV_OUT` / `CHART_OUT` change the output filenames.

## Handling of missing data

Yahoo doesn't have every metric for every company, and coverage is thinner
outside US large caps. The script never crashes on a gap — any metric it can't
retrieve becomes `N/A` in the table and CSV, tickers without a P/E sort to the
bottom of the table and are omitted from the chart (listed under the x-axis
label instead), and if a ticker's profile fails to load entirely you still get a
row with the ticker and `N/A` across, plus a warning line naming it.

Verified against a deliberately awkward list — `["AAPL", "ZZZZINVALID", "RIVN", "NKLA"]`,
mixing a valid symbol, a nonexistent one, an unprofitable company and a delisted one:

```
  ! no metrics returned for ZZZZINVALID - check the symbol is valid
  ! no metrics returned for NKLA - check the symbol is valid

     Ticker                 Company   P/E EV/EBITDA  ROE % Debt/Equity Rev CAGR 3Y %
       AAPL              Apple Inc. 37.75     29.07 148.75        0.78          1.81
ZZZZINVALID             ZZZZINVALID   N/A       N/A    N/A         N/A           N/A
       RIVN Rivian Automotive, Inc.   N/A     -8.48 -57.52        1.04         48.11
       NKLA                    NKLA   N/A       N/A    N/A         N/A           N/A
```

Two things to note in that output. Rivian shows `N/A` for P/E because it is
loss-making — there is no meaningful price-to-earnings multiple on negative
earnings — but its other metrics still come through, including a negative
EV/EBITDA and ROE. And for unknown symbols, yfinance prints its own
`HTTP Error 404: ... Quote not found for symbol: ...` line before the table.
That comes from the library, not from this script, and is not a crash.

## A caveat on the data

Yahoo Finance is free, convenient, and not audited. Figures can be stale,
occasionally wrong, and inconsistently defined across companies — trailing
metrics in particular lag recent results. It's good enough for a first-pass
screen or to frame a question; check anything that matters against the filings.
