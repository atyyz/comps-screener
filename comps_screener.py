"""
comps_screener.py — a simple equity comparable-company ("comps") screener.

Pulls valuation, profitability, leverage and growth metrics from Yahoo Finance
for a list of tickers, prints them as a table sorted by P/E, writes a CSV, and
saves a bar chart comparing P/E across the peer set.

Run with:  python comps_screener.py
"""

import math

import matplotlib

matplotlib.use("Agg")  # render to a file; no display/GUI needed

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# CONFIG — swap this list for any sector or peer set you want to compare.
# e.g. banks:  ["JPM", "BAC", "WFC", "C", "GS"]
#      energy: ["XOM", "CVX", "COP", "SLB", "EOG"]
# ---------------------------------------------------------------------------
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

CAGR_YEARS = 3  # lookback for the revenue growth CAGR
CSV_OUT = "comps_output.csv"
CHART_OUT = "comps_chart.png"


def to_float(value):
    """Coerce a yfinance value to float, or None if it isn't usable.

    yfinance returns missing fields as None, as the string "Infinity", or
    occasionally as NaN, so everything gets funnelled through here.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def revenue_cagr(ticker_obj, years=CAGR_YEARS):
    """Annualised revenue growth over `years`, in percent (None if unavailable).

    yfinance exposes the annual income statement as a DataFrame with one column
    per fiscal year (newest first) and metrics as rows. We grab "Total Revenue",
    take the newest figure and the one `years` periods back, then annualise:
        CAGR = (newest / oldest) ** (1 / periods) - 1

    Only ~4 years of annual statements are available, so if a company has fewer
    than `years + 1` reported years we fall back to the longest span we do have.
    """
    # income_stmt is the modern attribute; financials is the older alias.
    for attribute in ("income_stmt", "financials"):
        try:
            statement = getattr(ticker_obj, attribute)
        except Exception:
            continue
        if statement is None or statement.empty:
            continue

        # Row label varies slightly between tickers/yfinance versions.
        row = None
        for label in ("Total Revenue", "TotalRevenue", "Operating Revenue"):
            if label in statement.index:
                row = statement.loc[label]
                break
        if row is None:
            continue
        if isinstance(row, pd.DataFrame):  # duplicate index labels
            row = row.iloc[0]

        revenue = row.dropna().sort_index()  # oldest -> newest
        if len(revenue) < 2:
            continue

        periods = min(years, len(revenue) - 1)
        newest = to_float(revenue.iloc[-1])
        oldest = to_float(revenue.iloc[-1 - periods])
        # Negative or zero revenue makes the root meaningless — skip it.
        if not newest or not oldest or newest <= 0 or oldest <= 0:
            continue

        return ((newest / oldest) ** (1 / periods) - 1) * 100

    return None


def fetch_metrics(ticker):
    """Return one row of comps data for `ticker`. Missing values come back None."""
    stock = yf.Ticker(ticker)

    # .info is a single bulk request; if Yahoo hiccups we still want the row.
    try:
        info = stock.info or {}
    except Exception as exc:
        print(f"  ! could not load profile for {ticker}: {exc}")
        info = {}

    roe = to_float(info.get("returnOnEquity"))  # decimal fraction, e.g. 0.147
    debt_to_equity = to_float(info.get("debtToEquity"))  # percent, e.g. 154.5

    try:
        cagr = revenue_cagr(stock)
    except Exception as exc:
        print(f"  ! could not compute revenue CAGR for {ticker}: {exc}")
        cagr = None

    row = {
        "Ticker": ticker,
        "Company": info.get("shortName") or info.get("longName") or ticker,
        "P/E": to_float(info.get("trailingPE")),
        "EV/EBITDA": to_float(info.get("enterpriseToEbitda")),
        "ROE %": roe * 100 if roe is not None else None,
        "Debt/Equity": debt_to_equity / 100 if debt_to_equity is not None else None,
        f"Rev CAGR {CAGR_YEARS}Y %": cagr,
    }

    # A row with nothing in it usually means a typo'd or delisted symbol, which
    # is worth calling out rather than leaving as a silent line of N/A.
    metrics = [v for k, v in row.items() if k not in ("Ticker", "Company")]
    if all(v is None for v in metrics):
        print(f"  ! no metrics returned for {ticker} - check the symbol is valid")

    return row


def format_for_display(df):
    """Copy of `df` with numbers rounded to 2dp and blanks shown as 'N/A'."""
    display = df.copy()
    for column in display.columns:
        if column in ("Ticker", "Company"):
            continue
        display[column] = display[column].map(
            lambda v: "N/A" if pd.isna(v) else f"{v:,.2f}"
        )
    return display


def save_pe_chart(df, path=CHART_OUT):
    """Bar chart of P/E across the peer set. Tickers with no P/E are skipped."""
    charted = df.dropna(subset=["P/E"])
    missing = sorted(set(df["Ticker"]) - set(charted["Ticker"]))

    if charted.empty:
        print("No P/E data available — skipping chart.")
        return

    fig, ax = plt.subplots(figsize=(max(6, len(charted) * 1.4), 5))
    bars = ax.bar(charted["Ticker"], charted["P/E"], color="#4C72B0")

    # Print each value above its bar so the chart is readable on its own.
    for bar, value in zip(bars, charted["P/E"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:,.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.set_title("P/E Ratio Comparison")
    ax.set_xlabel("Ticker")
    ax.set_ylabel("Trailing P/E")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)

    if missing:
        ax.set_xlabel(f"Ticker  (no P/E data: {', '.join(missing)})")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved chart to {path}")


def main():
    print(f"Pulling data for {len(TICKERS)} tickers...\n")

    rows = []
    for ticker in TICKERS:
        print(f"  {ticker}")
        rows.append(fetch_metrics(ticker))

    df = pd.DataFrame(rows)

    # Cheapest first; anything without a P/E sorts to the bottom.
    df = df.sort_values("P/E", ascending=True, na_position="last").reset_index(drop=True)

    print("\n" + "=" * 90)
    # ASCII only in printed output - Windows consoles fall back to a legacy
    # codepage when stdout is piped to a file, which mangles characters like em dashes.
    print(f"COMPS TABLE - sorted by P/E ascending ({len(df)} companies)")
    print("=" * 90)
    print(format_for_display(df).to_string(index=False))
    print("=" * 90 + "\n")

    # Numbers stay numeric in the CSV (easier to re-open in Excel); gaps show N/A.
    df.round(2).to_csv(CSV_OUT, index=False, na_rep="N/A")
    print(f"Saved table to {CSV_OUT}")

    save_pe_chart(df)


if __name__ == "__main__":
    main()
