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
    :root { --bg: #1e1e2f; --fg: #e0e0e0; --container-bg: #2a2a40; --input-bg: #3c3c52; }
    body { background: var(--bg); color: var(--fg); font-family: sans-serif; margin:0; padding:20px; transition: .3s; }
    body.light-mode { --bg: #f5f5f5; --fg: #333; --container-bg: #fff; --input-bg: #e0e0e0; }
    .container { max-width:960px; margin:auto; background:var(--container-bg); padding:30px; border-radius:10px; box-shadow:0 4px 10px rgba(0,0,0,0.3); }
    .controls { display:flex; gap:20px; flex-wrap:wrap; margin-bottom:20px; }
    input, button, select { padding:10px; border:none; border-radius:5px; background:var(--input-bg); color:var(--fg); }
    .input-row { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:15px; align-items:center; }
    .actions { display:flex; justify-content:space-between; margin:30px 0; }
    button, a.button { background:#4f46e5; color:#fff; text-decoration:none; cursor:pointer; transition:.3s; margin-left:10px; }
    button:hover, a.button:hover { background:#6366f1; }
    .chart-actions { display:flex; justify-content:flex-end; gap:10px; margin-bottom:10px; }
    img { max-width:100%; margin:0 auto 30px; border-radius:10px; box-shadow:0 0 20px rgba(255,255,255,0.1); }
    .delete-btn { background:#e74c3c; }
    .delete-btn:hover { background:#c0392b; }
  </style>
</head>
<body class="{{ 'light-mode' if theme=='light' }}">
  <div class="container">
    <h1>📊 Stock Portfolio Analyzer</h1>
    <form method="post">
      <input type="hidden" id="themeInput" name="theme" value="{{ theme }}">
      <div class="controls">
        <label>Start Date: <input type="date" name="start_date" value="{{ start_date }}"></label>
        <label>End Date: <input type="date" name="end_date" value="{{ end_date }}"></label>
        <label style="margin-left:auto"><input type="checkbox" id="modeToggle" onchange="toggleMode()" {{ 'checked' if theme=='light' else '' }}> Light Mode</label>
      </div>
      <div id="inputs">
        <div class="input-row">
          <select name="exchange">
            <option value="NS">NSE (.NS)</option>
            <option value="BO">BSE (.BO)</option>
          </select>
          <input name="ticker" placeholder="Stock Ticker (e.g., TCS)" required>
          <input name="units" placeholder="Units Bought" type="number" step="1" required>
          <input name="avg_price" placeholder="Average Buy Price" type="number" step="0.01" required>
          <button type="button" class="delete-btn" onclick="removeRow(this)">Delete</button>
        </div>
      </div>
      <div class="actions">
        <button type="button" onclick="addInput()">Add More</button>
        <button type="submit">Analyze Portfolio</button>
      </div>
    </form>

    {% if error_message %}
      <script>alert("{{ error_message }}");</script>
    {% endif %}

    {% if plot_url %}
      <div class="chart-actions">
        <button type="button" onclick="goBack()">Go Back</button>
        <a class="button" href="data:image/png;base64,{{ plot_url }}" download="analysis.png">Download Analysis</a>
      </div>
      <img src="data:image/png;base64,{{ plot_url }}" alt="Portfolio Analysis Graph">
    {% endif %}
  </div>

  <script>
    function updateDeleteButtons() {
      const rows = document.querySelectorAll('.input-row');
      rows.forEach(r => {
        const btn = r.querySelector('.delete-btn');
        btn.style.display = rows.length > 1 ? 'inline-block' : 'none';
      });
    }

    function addInput() {
      const div = document.createElement('div');
      div.className = 'input-row';
      div.innerHTML =
        '<select name="exchange">' +
        '<option value="NS">NSE (.NS)</option>' +
        '<option value="BO">BSE (.BO)</option>' +
        '</select>' +
        '<input name="ticker" placeholder="Stock Ticker (e.g., TCS)" required>' +
        '<input name="units" placeholder="Units Bought" type="number" step="1" required>' +
        '<input name="avg_price" placeholder="Average Buy Price" type="number" step="0.01" required>' +
        '<button type="button" class="delete-btn" onclick="removeRow(this)">Delete</button>';
      document.getElementById('inputs').appendChild(div);
      updateDeleteButtons();
    }

    function removeRow(btn) {
      const row = btn.closest('.input-row');
      row.remove();
      updateDeleteButtons();
    }

    function toggleMode() {
      const isLight = document.body.classList.toggle('light-mode');
      document.getElementById('themeInput').value = isLight ? 'light' : 'dark';
    }

    function goBack() { window.location.href = '/'; }

    window.addEventListener('load', () => {
      updateDeleteButtons();
      const nav = performance.getEntriesByType('navigation')[0];
      if (nav && nav.type === 'reload') goBack();
    });
  </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    plot_url = None
    error_message = None

    start_date = request.form.get("start_date") or "2025-01-01"
    end_date   = request.form.get("end_date")   or datetime.today().strftime("%Y-%m-%d")
    theme      = request.form.get("theme", "dark")

    if request.method == "POST":
        plt.style.use("dark_background" if theme=="dark" else "default")

        raw_tickers   = request.form.getlist("ticker")
        raw_exchanges = request.form.getlist("exchange")
        tickers = []
        for t_raw, exch in zip(raw_tickers, raw_exchanges):
            t = t_raw.strip().upper().split('.')[0]
            suffix = f".{exch}"
            ticker = t if t.endswith(suffix) else t + suffix
            tickers.append(ticker)

        symbols = tickers + ["^NSEI", "^BSESN"]
        data = yf.download(symbols, start=start_date, end=end_date, auto_adjust=True)["Close"]

        for t in tickers:
            if t not in data.columns or data[t].dropna().empty:
                error_message = f"Invalid ticker: {t}"
                break

        if error_message is None:
            units     = {t:int(u) for t,u in zip(tickers, request.form.getlist("units"))}
            avg_price = {t:float(p) for t,p in zip(tickers, request.form.getlist("avg_price"))}
            invested  = {t: units[t]*avg_price[t] for t in tickers}

            df_ind = pd.DataFrame(index=tickers)
            df_ind["Invested Value"] = pd.Series(invested)
            last = data.iloc[-1][tickers]
            current = last.mul(pd.Series(units))
            df_ind["Current Value"] = current
            df_ind["P/L"] = df_ind["Current Value"] - df_ind["Invested Value"]

            total_cost = df_ind["Invested Value"].sum()
            port_vals  = data[tickers].mul(pd.Series(units)).sum(axis=1)
            returns = pd.DataFrame({
                "Portfolio vs Cost": port_vals/total_cost - 1,
                "NIFTY 50":          data["^NSEI"]/data["^NSEI"].iloc[0] - 1,
                "SENSEX":            data["^BSESN"]/data["^BSESN"].iloc[0] - 1
            })

            fig, axes = plt.subplots(3,1,figsize=(10,15))
            returns.plot(ax=axes[0], title="Cumulative Returns: Portfolio vs NIFTY 50 vs SENSEX")
            axes[0].set_ylabel("Return (%)")
            axes[0].legend(loc="upper left")

            bars = df_ind[["Invested Value","Current Value"]].plot(
                kind="bar", ax=axes[1], title="Invested vs Current Value"
            ).patches
            axes[1].set_ylabel("Value (₹)")
            for bar in bars:
                height = bar.get_height()
                axes[1].annotate(f"{height:,.0f}", xy=(bar.get_x()+bar.get_width()/2, height), xytext=(0,3), textcoords="offset points", ha='center', va='bottom')

            bars_pl = df_ind["P/L"].plot(
                kind="bar", ax=axes[2], title="Profit / Loss"
            ).patches
            axes[2].axhline(0, linewidth=0.8)
            axes[2].set_ylabel("P/L (₹)")
            for bar in bars_pl:
                h = bar.get_height()
                axes[2].annotate(f"{h:,.0f}", xy=(bar.get_x()+bar.get_width()/2, h), xytext=(0,3 if h>=0 else -12), textcoords="offset points", ha='center', va='bottom' if h>=0 else 'top')

            for ax in (axes[1], axes[2]):
                ax.tick_params(axis='x', rotation=0, labelsize=10)
            fig.subplots_adjust(bottom=0.25)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight")
            buf.seek(0)
            plot_url = base64.b64encode(buf.getvalue()).decode("utf8")
            buf.close()
            plt.close(fig)

    return render_template_string(
        HTML_TEMPLATE,
        plot_url=plot_url,
        start_date=start_date,
        end_date=end_date,
        theme=theme,
        error_message=error_message
    )

if __name__ == "__main__":
    app.run(debug=True)
