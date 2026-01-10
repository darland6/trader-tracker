"""
Dashboard Generator with MOCK/REAL Data Toggle
Reads toggle setting from Excel and generates appropriate dashboard

Usage: python generate_dashboard.py Financial_Planning_v2.0_with_mock.xlsx
"""

import pandas as pd
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime

def read_data_mode(filename):
    """Read the toggle setting to determine which data to use"""
    try:
        toggle_df = pd.read_excel(filename, sheet_name='TOGGLE - Data Mode')
        mode = toggle_df.iloc[0]['Value'].strip().upper()
        print(f"📊 Data Mode: {mode}")
        return mode
    except Exception as e:
        print(f"Warning: Could not read toggle, defaulting to REAL. Error: {e}")
        return 'REAL'

def generate_dashboard(filename):
    """Generate visual dashboard from version history"""
    print("\n" + "="*60)
    print("📊 Generating dashboard...")
    
    # Read toggle
    mode = read_data_mode(filename)
    
    # Read appropriate version history sheet
    if mode == 'MOCK':
        sheet_name = 'Version History - MOCK'
        print("   Using MOCK data (3 months of simulated trading)")
    else:
        sheet_name = 'Version History - REAL'
        print("   Using REAL data (your actual portfolio snapshots)")
    
    try:
        version_df = pd.read_excel(filename, sheet_name=sheet_name)
    except Exception as e:
        print(f"Error reading sheet '{sheet_name}': {e}")
        return
    
    # Filter out rows with NaN Version
    version_df = version_df[version_df['Version'].notna()].copy()
    
    if len(version_df) < 1:
        print("⚠️  No data points found!")
        return
    
    if len(version_df) < 2:
        print("⚠️  Need at least 2 data points for meaningful charts.")
        print("    For REAL data: Run price update script a few times.")
        print("    For MOCK data: Toggle is already set to MOCK with 14 weeks!")
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
    
    print(f"   Data points: {len(dates)}")
    print(f"   Date range: {pd.to_datetime(dates[0]).strftime('%Y-%m-%d')} to {pd.to_datetime(dates[-1]).strftime('%Y-%m-%d')}")
    
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
    title_suffix = ' [DEMO - Mock Data]' if mode == 'MOCK' else ' [Live Data]'
    fig.suptitle(f'Financial Independence Dashboard{title_suffix}', fontsize=20, fontweight='bold', y=0.98)
    
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
CURRENT METRICS (as of {pd.to_datetime(dates[-1]).strftime('%b %d, %Y')}) - MODE: {mode}:
Portfolio: ${portfolio_values[-1]:,.0f}  |  Gain: ${gain:,.0f} ({gain_pct:+.1f}%)  |  Income: ${ytd_income[-1]:,.0f} ({progress_pct:.0f}% of goal)

Top Holdings: BMNR ${bmnr_values[-1]:,.0f} | SPOT ${spot_values[-1]:,.0f} | TSLA ${tsla_values[-1]:,.0f}

Snapshots: {len(dates)}  |  Period: {len(dates)} weeks  |  Avg Weekly Income: ${ytd_income[-1]/len(dates):,.0f}
"""
    
    plt.figtext(0.5, 0.02, stats_text, ha='center', fontsize=10, 
                bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8),
                family='monospace')
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.94])
    
    # Save with mode indicator
    base_name = filename.rsplit('.', 1)[0]
    mode_suffix = '_MOCK' if mode == 'MOCK' else '_REAL'
    png_file = f"{base_name}_Dashboard{mode_suffix}.png"
    pdf_file = f"{base_name}_Dashboard{mode_suffix}.pdf"
    
    plt.savefig(png_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(pdf_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"\n✅ Dashboard saved: {png_file}")
    print(f"✅ PDF version: {pdf_file}")
    print(f"\n💡 Showing {mode} data with {len(dates)} snapshots")
    if mode == 'MOCK':
        print("   To see your real data: Change TOGGLE sheet to 'REAL' and re-run")
    else:
        print("   To see mock demo: Change TOGGLE sheet to 'MOCK' and re-run")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_dashboard.py <filename.xlsx>")
        sys.exit(1)
    
    filename = sys.argv[1]
    generate_dashboard(filename)
    print("\n✨ Dashboard generation complete!")

