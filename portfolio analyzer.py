import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from flask import Flask, render_template_string, request
import io
import base64

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>Portfolio Analyzer</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #1e1e2f;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 960px;
            margin: auto;
            background: #2a2a40;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        }
        h1 {
            text-align: center;
            color: #ffffff;
            margin-bottom: 20px;
        }
        form > div, .input-row {
            margin-bottom: 15px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        input {
            padding: 10px;
            border: none;
            border-radius: 5px;
            width: 30%;
            background: #3c3c52;
            color: #fff;
        }
        button {
            padding: 10px 20px;
            background-color: #4f46e5;
            border: none;
            border-radius: 5px;
            color: white;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #6366f1;
        }
        .actions {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        img {
            display: block;
            max-width: 100%;
            margin: 30px auto;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(255, 255, 255, 0.1);
        }
    </style>
</head>
<body>
<div class="container">
    <h1>📊 Stock Portfolio Analyzer</h1>
    <form method="post">
        <div id="inputs">
            <div class="input-row">
                <input name="ticker" placeholder="Stock Ticker (e.g., ETERNAL.NS)" required>
                <input name="units" placeholder="Units Bought" type="number" step="1" required>
                <input name="avg_price" placeholder="Average Buy Price" type="number" step="0.01" required>
            </div>
        </div>
        <div class="actions">
            <button type="button" onclick="addInput()">Add More</button>
            <button type="submit">Analyze Portfolio</button>
        </div>
    </form>
    {% if plot_url %}
        <img src="data:image/png;base64,{{ plot_url }}" alt="Portfolio Analysis Graph">
    {% endif %}
</div>

<script>
    function addInput() {
        var div = document.createElement('div');
        div.className = 'input-row';
        div.innerHTML = `
            <input name="ticker" placeholder="Stock Ticker (e.g., ETERNAL.NS)" required>
            <input name="units" placeholder="Units Bought" type="number" step="1" required>
            <input name="avg_price" placeholder="Average Buy Price" type="number" step="0.01" required>
        `;
        document.getElementById('inputs').appendChild(div);
    }
</script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    plot_url = None
    if request.method == "POST":
        tickers = request.form.getlist("ticker")
        units_list = request.form.getlist("units")
        prices_list = request.form.getlist("avg_price")

        units = {t: int(u) for t, u in zip(tickers, units_list)}
        avg_price = {t: float(p) for t, p in zip(tickers, prices_list)}
        invested = {ticker: units[ticker] * avg_price[ticker] for ticker in tickers}
        df_individual = pd.DataFrame(index=tickers)
        df_individual['Invested Value'] = pd.Series(invested)

        symbols = tickers + ['^NSEI', '^BSESN']
        start_date = '2025-01-01'
        end_date = datetime.today().strftime('%Y-%m-%d')
        data = yf.download(symbols, start=start_date, end=end_date, auto_adjust=True)['Close']

        last_prices = data.iloc[-1][tickers]
        current_vals = last_prices.mul(pd.Series(units))
        df_individual['Current Value'] = current_vals
        df_individual['P/L'] = df_individual['Current Value'] - df_individual['Invested Value']

        total_invested = df_individual['Invested Value'].sum()
        total_current = df_individual['Current Value'].sum()
        total_cost = total_invested

        portfolio_vals = data[tickers].mul(pd.Series(units)).sum(axis=1)
        returns = pd.DataFrame({
            'Portfolio vs Cost': portfolio_vals / total_cost - 1,
            'NIFTY 50': data['^NSEI'] / data['^NSEI'].iloc[0] - 1,
            'SENSEX': data['^BSESN'] / data['^BSESN'].iloc[0] - 1
        })

        fig, axes = plt.subplots(3, 1, figsize=(10, 15))

        ax = axes[0]
        for name in returns.columns:
            ax.plot(returns.index, returns[name], label=name)
        ax.set_title('Cumulative Return vs. Cost Basis YTD 2025')
        ax.set_xlabel('Date')
        ax.set_ylabel('Return')
        ax.legend()
        ax.grid(True)

        ax = axes[1]
        labels = df_individual.index.tolist()
        y = list(range(len(labels)))
        bar_height = 0.4
        ax.barh([i - bar_height/2 for i in y], df_individual['Invested Value'], height=bar_height, color='lightblue', label='Invested Value')
        colors_current = ['green' if cur >= inv else 'red' for cur, inv in zip(df_individual['Current Value'], df_individual['Invested Value'])]
        ax.barh([i + bar_height/2 for i in y], df_individual['Current Value'], height=bar_height, color=colors_current, label='Current Value')
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_title('Invested vs Current Value per Stock')
        ax.set_xlabel('Value (INR)')
        ax.legend()
        for i in y:
            inv = df_individual['Invested Value'].iloc[i]
            cur = df_individual['Current Value'].iloc[i]
            ax.text(inv + max(total_invested, total_current) * 0.005, i - bar_height/2, f'{inv:,.0f}', va='center')
            ax.text(cur + max(total_invested, total_current) * 0.005, i + bar_height/2, f'{cur:,.0f}', va='center')

        ax = axes[2]
        labels_tot = ['Total Invested', 'Total Current']
        values = [total_invested, total_current]
        colors_tot = ['red', 'green']
        ax.barh(labels_tot, values, color=colors_tot)
        ax.set_title('Total Invested vs Current Portfolio Value')
        ax.set_xlabel('Value (INR)')
        for i, v in enumerate(values):
            ax.text(v + max(values) * 0.01, i, f'{v:,.0f}', va='center')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plot_url = base64.b64encode(buf.getvalue()).decode('utf8')
        buf.close()

    return render_template_string(HTML_TEMPLATE, plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)