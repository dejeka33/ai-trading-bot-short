"""
Lehká bezpečnostní kontrola BEZ volání AI - běží častěji než denní rozhodování
(viz .github/workflows/intraday_check.yml), aby ochránila portfolio před
prudkým intradenním propadem u inverzních ETF, aniž by to stálo další
Anthropic API volání.

Kontroluje aktuální otevřené pozice proti stop_loss_pct z config/risk_limits.yaml
a v případě překročení pozici okamžitě prodá (tržní příkaz). Je to čistě
pravidlová pojistka MEZI dvěma denními AI rozhodnutími, ne náhrada za ně -
plné rozhodování (co koupit) pořád dělá jen main.py jednou denně.
"""
import os
from datetime import datetime, timezone

from data_fetch import get_clients, get_account_snapshot
from risk_rules import load_risk_limits
from execute import execute_trades
from webpush_notify import send_web_push


def find_stop_loss_breaches(account_snapshot, stop_loss_pct):
    breaches = []
    for p in account_snapshot["positions"]:
        loss_pct = -p["unrealized_plpc"] * 100  # kladné číslo = ztráta v %
        if loss_pct >= stop_loss_pct:
            breaches.append(p)
    return breaches


def main():
    limits = load_risk_limits()
    stop_loss_pct = limits["risk_controls"]["stop_loss_pct"]

    trading_client, *_ = get_clients()
    account = get_account_snapshot(trading_client)

    breaches = find_stop_loss_breaches(account, stop_loss_pct)

    timestamp = datetime.now(timezone.utc).isoformat()
    if not breaches:
        print(f"[{timestamp}] Intraday kontrola: žádná pozice nepřekročila stop-loss ({stop_loss_pct}%).")
        return

    trades = [
        {
            "symbol": p["symbol"], "side": "sell", "qty": p["qty"], "order_type": "market",
            "reasoning": (
                f"Automatický stop-loss - ztráta {(-p['unrealized_plpc'] * 100):.2f}% "
                f"přesáhla práh {stop_loss_pct}% (bez zásahu AI, čistě pravidlová pojistka)."
            ),
        }
        for p in breaches
    ]
    results = execute_trades(trading_client, trades)

    os.makedirs("reports", exist_ok=True)
    log_path = f"reports/intraday-stoploss-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    lines = [f"# Intraday stop-loss kontrola - {timestamp}", ""]
    for r in results:
        status = "prodáno" if r["status"] == "submitted" else f"chyba: {r.get('error')}"
        lines.append(f"- {r['symbol']}: {status} - {r.get('reasoning', '')}")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")

    print("\n".join(lines))

    # Tohle je jediná situace, kdy appka jedná úplně bez AI - proto stojí za
    # samostatnou (urgentní) notifikaci, na rozdíl od běžné klidné kontroly
    # "nic se neděje", která by jen zbytečně spamovala telefon 4x denně.
    symbols = ", ".join(p["symbol"] for p in breaches)
    send_web_push("AI Bearish Bot — stop-loss", f"Automaticky prodáno: {symbols}")

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))


if __name__ == "__main__":
    main()
