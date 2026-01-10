"""
Stock Price Updater + Dashboard Generator for Financial Planning Workbook
Uses Alpha Vantage API to fetch real-time stock prices and creates visual dashboard

Setup:
1. Get free API key from https://www.alphavantage.co/support/#api-key
2. Set environment variable: ALPHA_VANTAGE_API_KEY=your_key_here
3. Run: python update_prices_with_dashboard.py Financial_Planning_v1.0.xlsx

Requirements: pip install pandas openpyxl requests matplotlib --break-system-packages
"""

import pandas as pd
import requests
import sys
from datetime import datetime
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

def get_stock_price(symbol, api_key):
    """Fetch current stock price from Alpha Vantage"""
    url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}'
    try:
        response = requests.get(url)
        data = response.json()
        
        if 'Global Quote' in data and '05. price' in data['Global Quote']:
            return float(data['Global Quote']['05. price'])
        else:
            print(f"Warning: Could not fetch price for {symbol}")
            return None
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def update_workbook_prices(filename, api_key):
    """Update all stock prices in the Portfolio Positions sheet"""
    print(f"\nUpdating prices in {filename}...")
    print("="*60)
    
    # Read the portfolio sheet
    df = pd.read_excel(filename, sheet_name='Portfolio Positions')
    
    # Get tickers (exclude empty rows and totals)
    tickers = df['Ticker'].dropna()
    tickers = [t for t in tickers if t not in ['', 'TOTAL', 'CASH', 'GRAND TOTAL']]
    
    # Fetch prices
    updated_prices = {}
    for ticker in tickers:
        print(f"Fetching {ticker}...", end=' ')
        price = get_stock_price(ticker, api_key)
        if price:
            updated_prices[ticker] = price
            print(f"${price:.2f}")
        else:
            print("FAILED")
    
    # Update the dataframe
    for ticker, price in updated_prices.items():
        mask = df['Ticker'] == ticker
        df.loc[mask, 'Current Price'] = price
        df.loc[mask, 'Last Update'] = datetime.now().strftime('%m/%d')
        
        # Recalculate market value
        shares = df.loc[mask, 'Shares'].values[0]
        if pd.notna(shares):
            df.loc[mask, 'Market Value'] = shares * price
    
    # Recalculate portfolio percentages
    total_value = df[df['Ticker'].notna() & ~df['Ticker'].isin(['TOTAL', 'CASH', 'GRAND TOTAL'])]['Market Value'].sum()
    for ticker in tickers:
        mask = df['Ticker'] == ticker
        mkt_val = df.loc[mask, 'Market Value'].values[0]
        df.loc[mask, '% of Portfolio'] = round((mkt_val / total_value) * 100, 1)
    
    # Update TOTAL row
    total_mask = df['Ticker'] == 'TOTAL'
    df.loc[total_mask, 'Market Value'] = total_value
    
    # Write back to Excel
    with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name='Portfolio Positions', index=False)
    
    print("="*60)
    print(f"✅ Updated {len(updated_prices)} stocks")
    print(f"📊 Total Portfolio Value: ${total_value:,.2f}")
    print(f"⏰ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return total_value, updated_prices

def create_version_snapshot(filename):
    """Create a version snapshot in Version History sheet"""
    # Read current data
    portfolio_df = pd.read_excel(filename, sheet_name='Portfolio Positions')
    income_df = pd.read_excel(filename, sheet_name='Monthly Income')
    version_df = pd.read_excel(filename, sheet_name='Version History')
    
    # Calculate totals
    total_portfolio = portfolio_df[portfolio_df['Ticker'] == 'TOTAL']['Market Value'].values[0]
    cash = portfolio_df[portfolio_df['Ticker'] == 'CASH']['Market Value'].values[0]
    ytd_income = income_df['Total Income'].sum()
    
    # Get individual position values
    positions = {}
    for ticker in ['BMNR', 'NBIS', 'TSLA', 'META', 'RKLB', 'PLTR', 'SPOT']:
        val = portfolio_df[portfolio_df['Ticker'] == ticker]['Market Value'].values
        positions[ticker] = val[0] if len(val) > 0 else 0
    
    # Find next version number
    existing_versions = version_df['Version'].dropna().tolist()
    if existing_versions:
        last_version = existing_versions[-1]
        if isinstance(last_version, str) and last_version.startswith('v'):
            next_num = float(last_version[1:]) + 0.1
            next_version = f"v{next_num:.1f}"
        else:
            next_version = "v1.1"
    else:
        next_version = "v1.0"
    
    # Create new row
    new_row = {
        'Version': next_version,
        'Date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Portfolio Value': total_portfolio,
        'Cash': cash,
        'YTD Income': ytd_income,
        'Major Changes': 'Price update',
        'BMNR': positions['BMNR'],
        'NBIS': positions['NBIS'],
        'TSLA': positions['TSLA'],
        'META': positions['META'],
        'RKLB': positions['RKLB'],
        'PLTR': positions['PLTR'],
        'SPOT': positions['SPOT'],
        'Notes': 'Automated price refresh'
    }
    
    # Append to version history
    version_df = pd.concat([version_df, pd.DataFrame([new_row])], ignore_index=True)
    
    # Write back
    with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        version_df.to_excel(writer, sheet_name='Version History', index=False)
    
    print(f"📸 Snapshot saved as {next_version}")
    return version_df

def generate_dashboard(filename):
    """Generate visual dashboard from version history"""
    print("\n" + "="*60)
    print("📊 Generating dashboard...")
    
    # Read version history
    version_df = pd.read_excel(filename, sheet_name='Version History')
    income_df = pd.read_excel(filename, sheet_name='Monthly Income')
    
    # Filter out rows with NaN Version
    version_df = version_df[version_df['Version'].notna()].copy()
    
    if len(version_df) < 2:
        print("⚠️  Need at least 2 data points for dashboard. Run this script a few more times!")
        return
    
    # Parse dates
    version_df['Date'] = pd.to_datetime(version_df['Date'])
    
    # Extract data
    dates = version_df['Date'].values
    portfolio_values = version_df['Portfolio Value'].values
    bmnr_values = version_df['BMNR'].values
    nbis_values = version_df['NBIS'].values
    tsla_values = version_df['TSLA'].values
    meta_values = version_df['META'].values
    rklb_values = version_df['RKLB'].values
    pltr_values = version_df['PLTR'].values
    spot_values = version_df['SPOT'].values
    ytd_income = version_df['YTD Income'].values
    
    # Color scheme
    colors = {
        'portfolio': '#2E86AB',
        'income': '#06A77D',
        'bmnr': '#D62828',
        'nbis': '#F77F00',
        'tsla': '#FCBF49',
        'meta': '#0077B6',
        'rklb': '#9D4EDD',
        'pltr': '#06FFA5',
        'spot': '#F72585'
    }
    
    # Create figure
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle('Financial Independence Dashboard - Portfolio Analytics', fontsize=20, fontweight='bold', y=0.98)
    
    # Add date range subtitle
    plt.figtext(0.5, 0.95, f'Period: {pd.to_datetime(dates[0]).strftime("%b %d, %Y")} - {pd.to_datetime(dates[-1]).strftime("%b %d, %Y")}', 
                ha='center', fontsize=12, style='italic')
    
    # PLOT 1: Total Portfolio Value Over Time
    ax1 = plt.subplot(3, 3, (1, 4))
    ax1.plot(dates, portfolio_values, color=colors['portfolio'], linewidth=3, marker='o', markersize=6)
    ax1.fill_between(dates, portfolio_values, alpha=0.3, color=colors['portfolio'])
    ax1.set_title('Total Portfolio Value', fontsize=14, fontweight='bold', pad=10)
    ax1.set_ylabel('Value ($)', fontsize=11, fontweight='bold')
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # Annotations
    ax1.annotate(f'${portfolio_values[0]:,.0f}', 
                xy=(dates[0], portfolio_values[0]), 
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                fontsize=9, fontweight='bold')
    ax1.annotate(f'${portfolio_values[-1]:,.0f}', 
                xy=(dates[-1], portfolio_values[-1]), 
                xytext=(-80, -20), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7),
                fontsize=9, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='green', lw=2))
    
    # Gain/loss
    gain = portfolio_values[-1] - portfolio_values[0]
    gain_pct = (gain / portfolio_values[0]) * 100
    color_gain = 'green' if gain > 0 else 'red'
    ax1.text(0.02, 0.98, f'Total Gain: ${gain:,.0f} ({gain_pct:+.1f}%)', 
             transform=ax1.transAxes, fontsize=10, fontweight='bold',
             verticalalignment='top', color=color_gain,
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # PLOT 2: Individual Position Values
    ax2 = plt.subplot(3, 3, (3, 6))
    ax2.plot(dates, bmnr_values, label='BMNR', color=colors['bmnr'], linewidth=2, marker='o', markersize=4)
    ax2.plot(dates, nbis_values, label='NBIS', color=colors['nbis'], linewidth=2, marker='s', markersize=4)
    ax2.plot(dates, tsla_values, label='TSLA', color=colors['tsla'], linewidth=2, marker='^', markersize=4)
    ax2.plot(dates, meta_values, label='META', color=colors['meta'], linewidth=2, marker='d', markersize=4)
    ax2.plot(dates, rklb_values, label='RKLB', color=colors['rklb'], linewidth=2, marker='v', markersize=4)
    ax2.plot(dates, pltr_values, label='PLTR', color=colors['pltr'], linewidth=2, marker='p', markersize=4)
    ax2.plot(dates, spot_values, label='SPOT', color=colors['spot'], linewidth=2, marker='*', markersize=4)
    
    ax2.set_title('Individual Holdings Performance', fontsize=14, fontweight='bold', pad=10)
    ax2.set_ylabel('Value ($)', fontsize=11, fontweight='bold')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))
    ax2.legend(loc='best', fontsize=9, framealpha=0.9)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    
    # PLOT 3: YTD Income Progress
    ax3 = plt.subplot(3, 3, 7)
    ax3.plot(dates, ytd_income, color=colors['income'], linewidth=3, marker='o', markersize=6)
    ax3.fill_between(dates, ytd_income, alpha=0.3, color=colors['income'])
    ax3.axhline(y=30000, color='red', linestyle='--', linewidth=2, label='Annual Goal ($30K)')
    ax3.set_title('YTD Income vs Goal', fontsize=12, fontweight='bold', pad=10)
    ax3.set_ylabel('Income ($)', fontsize=10, fontweight='bold')
    ax3.set_xlabel('Date', fontsize=10, fontweight='bold')
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3, linestyle='--')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)
    
    progress_pct = (ytd_income[-1] / 30000) * 100
    ax3.text(0.02, 0.98, f'Progress: {progress_pct:.0f}%', 
             transform=ax3.transAxes, fontsize=10, fontweight='bold',
             verticalalignment='top', color='green',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # PLOT 4: Income Growth Rate
    ax4 = plt.subplot(3, 3, 8)
    if len(ytd_income) > 1:
        income_growth = np.diff(ytd_income)
        bars = ax4.bar(range(len(income_growth)), income_growth, color=colors['income'], alpha=0.7, edgecolor='black')
        ax4.axhline(y=2500, color='red', linestyle='--', linewidth=2, label='Monthly Target')
        ax4.set_title('Income per Period', fontsize=12, fontweight='bold', pad=10)
        ax4.set_ylabel('Income ($)', fontsize=10, fontweight='bold')
        ax4.set_xlabel('Period', fontsize=10, fontweight='bold')
        ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.1f}K'))
        ax4.legend(fontsize=9)
        ax4.grid(True, alpha=0.3, linestyle='--', axis='y')
        
        # Color bars
        for i, bar in enumerate(bars):
            if income_growth[i] >= 2500:
                bar.set_color('green')
                bar.set_alpha(0.6)
    
    # PLOT 5: Portfolio Allocation Pie Chart
    ax5 = plt.subplot(3, 3, 9)
    latest_values = [bmnr_values[-1], nbis_values[-1], tsla_values[-1], meta_values[-1], 
                     rklb_values[-1], pltr_values[-1], spot_values[-1]]
    labels = ['BMNR', 'NBIS', 'TSLA', 'META', 'RKLB', 'PLTR', 'SPOT']
    pie_colors = [colors[label.lower()] for label in labels]
    
    wedges, texts, autotexts = ax5.pie(latest_values, labels=labels, autopct='%1.1f%%',
                                         colors=pie_colors, startangle=90)
    ax5.set_title('Current Allocation', fontsize=12, fontweight='bold', pad=10)
    
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(9)
    
    # Stats Box
    stats_text = f"""
CURRENT METRICS (as of {pd.to_datetime(dates[-1]).strftime('%b %d, %Y')}):
Portfolio: ${portfolio_values[-1]:,.0f}  |  Total Gain: ${gain:,.0f} ({gain_pct:+.1f}%)  |  YTD Income: ${ytd_income[-1]:,.0f} ({progress_pct:.0f}% of goal)

Top Holdings: BMNR ${bmnr_values[-1]:,.0f} | SPOT ${spot_values[-1]:,.0f} | TSLA ${tsla_values[-1]:,.0f}

Status: {'AHEAD OF TARGET' if ytd_income[-1] > (30000 * (len(dates)/52)) else 'BELOW TARGET'}  |  Snapshots: {len(dates)}
"""
    
    plt.figtext(0.5, 0.02, stats_text, ha='center', fontsize=10, 
                bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8),
                family='monospace')
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.94])
    
    # Save
    base_name = filename.rsplit('.', 1)[0]
    png_file = f"{base_name}_Dashboard.png"
    pdf_file = f"{base_name}_Dashboard.pdf"
    
    plt.savefig(png_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(pdf_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"✅ Dashboard saved: {png_file}")
    print(f"✅ PDF version: {pdf_file}")

if __name__ == "__main__":
    # Check for API key
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        print("❌ Error: ALPHA_VANTAGE_API_KEY environment variable not set")
        print("\nTo set it:")
        print("  Windows: set ALPHA_VANTAGE_API_KEY=your_key_here")
        print("  Mac/Linux: export ALPHA_VANTAGE_API_KEY=your_key_here")
        print("\nGet a free key at: https://www.alphavantage.co/support/#api-key")
        sys.exit(1)
    
    # Check for filename
    if len(sys.argv) < 2:
        print("Usage: python update_prices_with_dashboard.py <filename.xlsx>")
        sys.exit(1)
    
    filename = sys.argv[1]
    
    # Update prices
    total_value, prices = update_workbook_prices(filename, api_key)
    
    # Create version snapshot
    version_df = create_version_snapshot(filename)
    
    # Generate dashboard
    generate_dashboard(filename)
    
    print("\n✨ All done! Prices updated, snapshot saved, and dashboard generated!")

