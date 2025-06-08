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
        :root {
            --bg: #1e1e2f;
            --fg: #e0e0e0;
            --container-bg: #2a2a40;
            --input-bg: #3c3c52;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg);
            color: var(--fg);
            margin: 0;
            padding: 20px;
            transition: background-color .3s, color .3s;
        }
        .container {
            max-width: 960px;
            margin: auto;
            background: var(--container-bg);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
            transition: background .3s;
        }
        input, select, button {
            padding: 10px;
            border: none;
            border-radius: 5px;
            background: var(--input-bg);
            color: var(--fg);
        }
        label { display: flex; align-items: center; gap: 8px; }
        .controls { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }
        .actions { display: flex; justify-content: space-between; margin-bottom: 20px; }
        button { cursor: pointer; transition: background-color .3s; }
        button:hover { background-color: #6366f1; }
        img { display: block; max-width: 100%; margin: 30px auto; border-radius: 10px; box-shadow: 0 0 20px rgba(255,255,255,0.1); }
        
        /* LIGHT MODE OVERRIDES */
        body.light-mode {
            --bg: #f5f5f5;
            --fg: #333;
            --container-bg: #ffffff;
            --input-bg: #e0e0e0;
        }
    </style>
</head>
<body>
  <div class="container">
    <h1>📊 Stock Portfolio Analyzer</h1>

    <form method="post">
      <div class="controls">
        <label>
          Start Date:
          <input type="date" name="start_date" value="{{ start_date }}">
        </label>
        <label>
          End Date:
          <input type="date" name="end_date" value="{{ end_date }}">
        </label>
        <label style="margin-left:auto">
          <input type="checkbox" id="modeToggle" onchange="toggleMode()">
          Light Mode
        </label>
      </div>

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
    const div = document.createElement('div');
    div.className = 'input-row';
    div.innerHTML = `
      <input name="ticker" placeholder="Stock Ticker (e.g., ETERNAL.NS)" required>
      <input name="units" placeholder="Units Bought" type="number" step="1" required>
      <input name="avg_price" placeholder="Average Buy Price" type="number" step="0.01" required>
    `;
    document.getElementById('inputs').appendChild(div);
  }
  function toggleMode() {
    document.body.classList.toggle('light-mode');
  }
</script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    plot_url = None

    # ─── NEW: grab user-selected timeframe ─────────────────────────────────────>
    # default to Jan 1, 2025 → today if not provided
    start_date = request.form.get("start_date") or "2025-01-01"
    end_date   = request.form.get("end_date")   or datetime.today().strftime("%Y-%m-%d")
    # ──────────────────────────────────────────────────────────────────────────<

    if request.method == "POST":
        # CAPITALIZE tickers as before
        tickers_raw = request.form.getlist("ticker")
        tickers = [t.strip().upper() for t in tickers_raw]

        units_list  = request.form.getlist("units")
        prices_list = request.form.getlist("avg_price")

        # rest of your processing unchanged…
        units     = {t: int(u)   for t, u in zip(tickers, units_list)}
        avg_price = {t: float(p) for t, p in zip(tickers, prices_list)}
        invested  = {t: units[t] * avg_price[t] for t in tickers}
        df_ind = pd.DataFrame(index=tickers)
        df_ind['Invested Value'] = pd.Series(invested)

        symbols = tickers + ['^NSEI', '^BSESN']
        data = yf.download(symbols,
                           start=start_date,
                           end=end_date,
                           auto_adjust=True)['Close']

        last_prices = data.iloc[-1][tickers]
        current_vals = last_prices.mul(pd.Series(units))
        df_ind['Current Value'] = current_vals
        df_ind['P/L'] = df_ind['Current Value'] - df_ind['Invested Value']

        total_cost = df_ind['Invested Value'].sum()
        portfolio_vals = data[tickers].mul(pd.Series(units)).sum(axis=1)

        # cumulative % returns:
        returns = pd.DataFrame({
            'Portfolio vs Cost': portfolio_vals / total_cost - 1,
            'NIFTY 50':    data['^NSEI'] / data['^NSEI'].iloc[0] - 1,
            'SENSEX':      data['^BSESN'] / data['^BSESN'].iloc[0] - 1
        })

        # …then your plotting code exactly as before, using `returns` for the first subplot.
        # save to buffer, base64-encode, etc.
        # [UNCHANGED]

    # pass timeframe back to template so date inputs stay populated
    return render_template_string(
        HTML_TEMPLATE,
        plot_url=plot_url,
        start_date=start_date,
        end_date=end_date
    )

if __name__ == '__main__':
    app.run(debug=True)
