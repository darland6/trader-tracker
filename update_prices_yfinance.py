"""
Stock Price Updater using yfinance
"""

import pandas as pd
import yfinance as yf
import sys
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

def get_stock_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.get("lastPrice")
        if price is None:
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
        return float(price) if price else None
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def update_workbook_prices(filename):
    print(f"Updating prices in {filename}...")
    print("="*60)

    df = pd.read_excel(filename, sheet_name="Portfolio Positions")
    tickers = df["Ticker"].dropna()
    tickers = [t for t in tickers if t not in ["", "TOTAL", "CASH", "GRAND TOTAL"]]

    updated_prices = {}
    for ticker in tickers:
        print(f"Fetching {ticker}...", end=" ")
        price = get_stock_price(ticker)
        if price:
            updated_prices[ticker] = price
            print(f"${price:.2f}")
        else:
            print("FAILED")

    for ticker, price in updated_prices.items():
        mask = df["Ticker"] == ticker
        df.loc[mask, "Current Price"] = price
        df.loc[mask, "Last Update"] = datetime.now().strftime("%m/%d")
        shares = df.loc[mask, "Shares"].values[0]
        if pd.notna(shares):
            df.loc[mask, "Market Value"] = shares * price

    total_value = df[df["Ticker"].notna() & ~df["Ticker"].isin(["TOTAL", "CASH", "GRAND TOTAL"])]["Market Value"].sum()
    for ticker in tickers:
        mask = df["Ticker"] == ticker
        mkt_val = df.loc[mask, "Market Value"].values[0]
        df.loc[mask, "% of Portfolio"] = round((mkt_val / total_value) * 100, 1)

    df.loc[df["Ticker"] == "TOTAL", "Market Value"] = total_value

    with pd.ExcelWriter(filename, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name="Portfolio Positions", index=False)

    print("="*60)
    print(f"Updated {len(updated_prices)} stocks")
    print(f"Total Portfolio Value: ${total_value:,.2f}")
    return total_value, updated_prices

def create_version_snapshot(filename):
    portfolio_df = pd.read_excel(filename, sheet_name="Portfolio Positions")
    income_df = pd.read_excel(filename, sheet_name="Monthly Income")
    
    try:
        version_df = pd.read_excel(filename, sheet_name="Version History")
        sheet_name = "Version History"
    except:
        version_df = pd.read_excel(filename, sheet_name="Version History - REAL")
        sheet_name = "Version History - REAL"

    total_portfolio = portfolio_df[portfolio_df["Ticker"] == "TOTAL"]["Market Value"].values[0]
    ytd_income = income_df["Total"].sum()

    positions = {}
    for ticker in ["BMNR", "NBIS", "TSLA", "META", "RKLB", "PLTR", "SPOT"]:
        val = portfolio_df[portfolio_df["Ticker"] == ticker]["Market Value"].values
        positions[ticker] = val[0] if len(val) > 0 else 0

    existing_versions = version_df["Version"].dropna().tolist()
    if existing_versions:
        last_version = existing_versions[-1]
        next_version = round(float(last_version) + 0.1, 1) if isinstance(last_version, (int, float)) else 1.2
    else:
        next_version = 1.0

    new_row = {
        "Version": next_version,
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Portfolio Value": total_portfolio,
        "BMNR": positions["BMNR"],
        "NBIS": positions["NBIS"],
        "TSLA": positions["TSLA"],
        "META": positions["META"],
        "RKLB": positions["RKLB"],
        "PLTR": positions["PLTR"],
        "SPOT": positions["SPOT"],
        "YTD Income": ytd_income
    }

    version_df = pd.concat([version_df, pd.DataFrame([new_row])], ignore_index=True)
    
    with pd.ExcelWriter(filename, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        version_df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Snapshot saved as v{next_version}")
    return version_df

def generate_dashboard(filename):
    print("Generating dashboard...")

    try:
        version_df = pd.read_excel(filename, sheet_name="Version History")
    except:
        version_df = pd.read_excel(filename, sheet_name="Version History - REAL")

    version_df = version_df[version_df["Version"].notna()].copy()
    if len(version_df) < 2:
        print("Need at least 2 data points for dashboard.")
        return

    version_df["Date"] = pd.to_datetime(version_df["Date"])
    dates = version_df["Date"].values
    portfolio_values = version_df["Portfolio Value"].values
    ytd_income = version_df["YTD Income"].values

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Financial Independence Dashboard", fontsize=16, fontweight="bold")

    axes[0,0].plot(dates, portfolio_values, "b-o", linewidth=2)
    axes[0,0].fill_between(dates, portfolio_values, alpha=0.3)
    axes[0,0].set_title("Portfolio Value")
    axes[0,0].grid(True, alpha=0.3)

    axes[0,1].plot(dates, ytd_income, "g-o", linewidth=2)
    axes[0,1].axhline(y=30000, color="r", linestyle="--", label="$30K Goal")
    axes[0,1].set_title("YTD Income vs Goal")
    axes[0,1].legend()
    axes[0,1].grid(True, alpha=0.3)

    tickers = ["BMNR", "NBIS", "TSLA", "META", "RKLB", "PLTR", "SPOT"]
    for t in tickers:
        if t in version_df.columns:
            axes[1,0].plot(dates, version_df[t].values, label=t, linewidth=1.5)
    axes[1,0].set_title("Individual Holdings")
    axes[1,0].legend(fontsize=8)
    axes[1,0].grid(True, alpha=0.3)

    latest = [version_df[t].iloc[-1] for t in tickers if t in version_df.columns]
    axes[1,1].pie(latest, labels=tickers, autopct="%1.1f%%")
    axes[1,1].set_title("Current Allocation")

    plt.tight_layout()
    base_name = filename.rsplit(".", 1)[0]
    plt.savefig(f"{base_name}_Dashboard.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Dashboard saved: {base_name}_Dashboard.png")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_prices_yfinance.py <filename.xlsx>")
        sys.exit(1)

    filename = sys.argv[1]
    total_value, prices = update_workbook_prices(filename)
    version_df = create_version_snapshot(filename)
    generate_dashboard(filename)
    print("All done!")
