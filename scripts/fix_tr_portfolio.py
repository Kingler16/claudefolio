"""Fix Trade Republic positions based on screenshot data."""
import json
from pathlib import Path

PORTFOLIO_PATH = Path(__file__).parent.parent / "config" / "portfolio.json"

with open(PORTFOLIO_PATH) as f:
    p = json.load(f)

# TR Screenshot 06.04.2026: links = Investiert (Kaufwert EUR), rechts = P&L EUR
# invested_eur = der linke Wert
tr_invested = {
    "ASML.AS":  2643.80,
    "RHM.DE":   2516.33,
    "BNTX":     1616.00,
    "XYZ":       920.48,   # Block
    "SAP.DE":    870.34,
    "CVX":       861.20,
    "LLY":       854.01,
    "AVGO":      737.53,
    "AMZN":      630.50,
    "META":      621.53,
    "NVO":       561.84,
    "BMY":       558.59,
    "GOOGL":     513.00,
    "PYPL":      403.46,
    "EUNL.DE":    49.21,
}

# EUR/USD rate for converting EUR invested to USD buy_in
EUR_USD = 1.09

for acc_name, acc in p["accounts"].items():
    if "trade" not in acc_name.lower():
        continue
    for pos in acc["positions"]:
        ticker = pos.get("ticker", "")
        if ticker not in tr_invested:
            continue

        invested_eur = tr_invested[ticker]
        shares = pos["shares"]
        buy_in_eur = invested_eur / shares

        old_buy_in = pos["buy_in"]
        currency = pos.get("currency", "EUR")

        if currency == "USD":
            # TR shows invested in EUR, but buy_in is stored in USD
            new_buy_in = buy_in_eur * EUR_USD
        else:
            new_buy_in = buy_in_eur

        pos["buy_in"] = round(new_buy_in, 4)
        print(f"  {pos['name']:25s} {ticker:10s} {shares:6.2f} Stk | "
              f"buy_in: {old_buy_in:8.2f} -> {pos['buy_in']:8.2f} {currency} | "
              f"invested: {invested_eur:.2f} EUR")

p["last_updated"] = "2026-04-06"
with open(PORTFOLIO_PATH, "w") as f:
    json.dump(p, f, indent=2, ensure_ascii=False)

print("\nportfolio.json updated!")
