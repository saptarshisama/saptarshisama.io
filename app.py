from flask import Flask, render_template, request, redirect, url_for, flash
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import os
from datetime import datetime, timedelta
import time
import warnings

warnings.filterwarnings('ignore')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for flash messages


def safe_download_data(symbols, start_date, end_date, max_retries=3):
    """
    Safely download data with multiple fallback strategies
    """
    for attempt in range(max_retries):
        try:
            data = yf.download(
                symbols,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                progress=False,
                threads=False
            )
            # Extract 'Close' if multi-index
            if isinstance(data.columns, pd.MultiIndex) and 'Close' in data.columns.get_level_values(0):
                data = data['Close']
            # Convert Series to DataFrame
            if isinstance(data, pd.Series):
                data = data.to_frame(name=symbols[0] if len(symbols)==1 else 'Close')
            return data
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < max_retries-1:
                time.sleep(2**attempt)
                continue
            raise e


def get_fallback_data(ticker, start_date, end_date):
    """Fallback approaches for problematic tickers"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date, auto_adjust=True)
        if not hist.empty:
            return hist['Close']
    except:
        pass
    try:
        short_start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        data = yf.download(ticker, start=short_start, auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data = data['Close']
        if not data.empty:
            return data
    except:
        pass
    return None


@app.route('/', methods=['GET', 'POST'])
def home():
    plot_url = None
    summary_text = None
    final_returns = None

    # Default date range
    start_date = request.form.get('start_date') or '2024-01-01'
    end_date = request.form.get('end_date') or datetime.today().strftime('%Y-%m-%d')
    theme = request.form.get('theme', 'dark')

    if request.method == 'POST':
        # Use a clean white background style
        plt.style.use('default')

        # Gather inputs
        raw_tickers = request.form.getlist('ticker')
        raw_exchanges = request.form.getlist('exchange')
        raw_units = request.form.getlist('units')
        raw_prices = request.form.getlist('avg_price')

        tickers, units, avg_prices, errors = [], [], [], []
        for i, t_raw in enumerate(raw_tickers):
            if not t_raw.strip(): continue
            base = t_raw.strip().upper().split('.')[0]
            suffix = f".{raw_exchanges[i]}"
            tk = base if base.endswith(suffix) else base+suffix
            try:
                u = int(raw_units[i]); p = float(raw_prices[i])
                if u<=0 or p<=0:
                    errors.append(f"Units and price must be positive for {t_raw}"); continue
            except:
                errors.append(f"Invalid units or price for {t_raw}"); continue
            tickers.append(tk); units.append(u); avg_prices.append(p)

        if errors:
            for msg in errors: flash(msg,'error')
            return redirect(url_for('home'))
        if not tickers:
            flash('Please enter at least one valid ticker','error')
            return redirect(url_for('home'))

        try:
            ticker_data = safe_download_data(tickers, start_date, end_date)
            # Benchmarks
            benchmark_data = {}
            for bm, name in [('^NSEI','NIFTY 50'), ('^BSESN','SENSEX')]:
                try:
                    bd = safe_download_data([bm], start_date, end_date)
                    if not bd.empty:
                        series = bd.iloc[:,0]
                        benchmark_data[name] = series
                except:
                    pass

            # Merge data
            all_data = pd.DataFrame(index=ticker_data.index)
            for t in tickers:
                if t in ticker_data.columns and not ticker_data[t].dropna().empty:
                    all_data[t] = ticker_data[t]
                else:
                    fb = get_fallback_data(t, start_date, end_date)
                    if fb is not None and not fb.empty:
                        all_data[t] = fb
                    else:
                        flash(f"No data available for {t}.", 'error')
                        return redirect(url_for('home'))
            for name, series in benchmark_data.items():
                all_data[name] = series
            all_data = all_data.fillna(method='ffill').fillna(method='bfill')
        except Exception as e:
            flash(f'Error fetching data: {e}','error')
            return redirect(url_for('home'))

        # Compute metrics
        units_dict = dict(zip(tickers, units))
        invested = {t: units_dict[t]*avg_prices[i] for i,t in enumerate(tickers)}
        df = pd.DataFrame(index=tickers)
        df['Invested'] = pd.Series(invested)
        last_prices = all_data[tickers].iloc[-1]
        df['Current'] = last_prices.mul(pd.Series(units_dict))
        df['P/L'] = df['Current'] - df['Invested']

        total_cost = df['Invested'].sum()
        portfolio_series = all_data[tickers].mul(pd.Series(units_dict)).sum(axis=1)
        returns = pd.DataFrame({
            'Portfolio': portfolio_series/total_cost - 1,
            **({} if 'NIFTY 50' not in all_data.columns else {'NIFTY 50': all_data['NIFTY 50']/all_data['NIFTY 50'].iloc[0] -1}),
            **({} if 'SENSEX' not in all_data.columns else {'SENSEX': all_data['SENSEX']/all_data['SENSEX'].iloc[0] -1})
        })

        # Convert to percentage
        returns *= 100

        # Summary calculation
        final_returns = returns.iloc[-1]
        if 'NIFTY 50' in final_returns and 'SENSEX' in final_returns:
            market_avg = final_returns[['NIFTY 50','SENSEX']].mean()
            diff = final_returns['Portfolio'] - market_avg
            perf = 'outperformed' if diff >= 0 else 'underperformed'
            summary_text = f"Your portfolio {perf} the market by {abs(diff):.2f}%"
        else:
            summary_text = None

        # Plotting with improved aesthetics
        fig, axes = plt.subplots(3,1,figsize=(12,16), constrained_layout=True)
        fig.patch.set_facecolor('white')
        for ax in axes:
            ax.set_facecolor('#f9f9f9')
            # Hide top/right spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            # Grid
            ax.grid(color='gray', linestyle='--', alpha=0.3)
            # Ticks styling
            ax.tick_params(axis='x', rotation=0, labelsize=12)
            ax.tick_params(axis='y', labelsize=12)

        # Returns chart
        returns.plot(ax=axes[0], title='Cumulative % Returns Comparison', linewidth=2)
        axes[0].set_ylabel('Cumulative % Return', fontsize=14)

        # Invested vs Current
        df[['Invested','Current']].plot(kind='bar', ax=axes[1], title='Invested vs Current Value', width=0.7)
        axes[1].set_ylabel('Value (₹)', fontsize=14)
        for i,(idx,row) in enumerate(df.iterrows()):
            axes[1].text(i-0.2, row['Invested']+total_cost*0.01, f"₹{row['Invested']:,.0f}", ha='center', va='bottom', fontsize=10)
            axes[1].text(i+0.2, row['Current']+total_cost*0.01, f"₹{row['Current']:,.0f}", ha='center', va='bottom', fontsize=10)

        # Profit/Loss
        colors = ['#2ca02c' if x>=0 else '#d62728' for x in df['P/L']]
        df['P/L'].plot(kind='bar', ax=axes[2], title='Profit / Loss', color=colors, width=0.7)
        axes[2].set_ylabel('P/L (₹)', fontsize=14)
        axes[2].axhline(0, color='gray', linewidth=0.8)
        for i,(idx,val) in enumerate(df['P/L'].items()):
            axes[2].text(i, val + (max(abs(df['P/L']))*0.02*(1 if val>=0 else -1)), f"₹{val:,.0f}", ha='center', va='bottom' if val>=0 else 'top', fontsize=10)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
        plot_url = base64.b64encode(buf.getvalue()).decode()
        buf.close()
        plt.close(fig)

    return render_template('index.html', plot_url=plot_url,
                           start_date=start_date, end_date=end_date,
                           theme=theme,
                           summary_text=summary_text,
                           final_returns=final_returns.to_dict() if final_returns is not None else None)


if __name__ == '__main__':
    app.run(debug=True)
