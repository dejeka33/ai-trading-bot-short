"""
Rozhodovací modul pro "bearish" appku (inverzní ETF) - pošle stav účtu, tržní
data a mantinely modelu Claude přes Anthropic API a dostane zpět strukturované
rozhodnutí (co koupit/prodat).

Klíčový rozdíl oproti dlouhodobému botovi: tady je VÝCHOZÍ/bezpečná pozice
HOTOVOST, ne držení ETF - viz build_prompt() níže.
"""
import json
import os

import anthropic

DECISION_TOOL = {
    "name": "record_trading_decision",
    "description": "Zaznamená dnešní obchodní rozhodnutí ve strukturované podobě.",
    "input_schema": {
        "type": "object",
        "properties": {
            "market_summary": {
                "type": "string",
                "description": "Krátké shrnutí toho, jak vypadá trh a portfolio dnes (2-4 věty).",
            },
            "trades": {
                "type": "array",
                "description": "Seznam navržených obchodů. Prázdné pole = dnes se neobchoduje.",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "side": {"type": "string", "enum": ["buy", "sell"]},
                        "qty": {"type": "number"},
                        "order_type": {"type": "string", "enum": ["market", "limit"]},
                        "limit_price": {"type": "number"},
                        "estimated_value": {"type": "number"},
                        "reasoning": {
                            "type": "string",
                            "description": "Proč tento obchod dává smysl vzhledem k datům a mantinelům.",
                        },
                    },
                    "required": ["symbol", "side", "qty", "order_type", "estimated_value", "reasoning"],
                },
            },
        },
        "required": ["market_summary", "trades"],
    },
}


def build_prompt(account_snapshot, tradable_bars, reference_bars, risk_limits, news=None, macro=None):
    news_section = ""
    if news:
        news_section = f"""
NEDÁVNÉ ZPRÁVY (posledních pár dní):
{json.dumps(news, indent=2, ensure_ascii=False)}
"""
    else:
        news_section = "\nNEDÁVNÉ ZPRÁVY: žádné relevantní zprávy se nepodařilo najít/stáhnout.\n"

    macro_section = ""
    if macro:
        macro_section = f"""
MAKROEKONOMICKÝ KONTEXT (zdroj: FRED, Federal Reserve Bank of St. Louis - oficiální,
na Alpace nezávislý zdroj):
{json.dumps(macro, indent=2, ensure_ascii=False)}
Zvlášť sleduj T10Y2Y (rozpětí 10Y-2Y): záporné/invertované rozpětí bývá historicky
spojováno s vyšší pravděpodobností ekonomického zpomalení v následujících měsících -
to je pro tuhle appku relevantnější signál než pro dlouhodobého bota.
"""

    max_holding_days = risk_limits.get("risk_controls", {}).get("max_recommended_holding_days")
    holding_note = ""
    if max_holding_days:
        holding_note = (
            f"\nDoporučená maximální doba držení jedné pozice je zhruba {max_holding_days} "
            "obchodních dní (viz decay riziko výše) - není to tvrdý limit vynucený kódem, "
            "ale měl bys ho zohlednit při rozhodování, jestli pozici držet dál nebo uzavřít.\n"
        )

    return f"""
Jsi obchodní asistent spravující PAPER TRADING účet (fiktivní peníze, reálná tržní data).
Tato appka se zaměřuje na OBRANNOU/"bearish" strategii pomocí INVERZNÍCH ETF - ne na
dlouhodobé investování. Smíš obchodovat POUZE tyto dva nástroje:
- SH  (ProShares Short S&P500 - denní -1x výkonnost S&P 500)
- PSQ (ProShares Short QQQ    - denní -1x výkonnost Nasdaq-100)

DŮLEŽITÉ VLASTNOSTI INVERZNÍCH ETF (nezapomeň na ně):
1. Sledují DENNÍ (ne dlouhodobou) inverzní výkonnost indexu. Při delším držení a
   kolísavém/nejistém trhu vzniká tzv. decay - i kdyby se index nakonec vrátil na
   stejnou hodnotu, ETF kvůli dennímu přepočítávání skončí v mírné ztrátě.
2. Proto je VÝCHOZÍ/bezpečná pozice u téhle appky HOTOVOST, ne držení ETF - na
   rozdíl od dlouhodobého bota, kde je "drž a čekej" v pořádku. Nákup SH/PSQ dává
   smysl jen při jasném, konkrétním důvodu k očekávanému poklesu, ne jako trvalá pozice.
3. Je naprosto v pořádku a ŽÁDOUCÍ nenavrhnout žádný obchod (prázdné pole trades),
   pokud signály nejsou přesvědčivé - tahle appka NEMÁ obchodovat často.
{holding_note}
AKTUÁLNÍ STAV ÚČTU:
{json.dumps(account_snapshot, indent=2, ensure_ascii=False)}

OBCHODOVATELNÉ NÁSTROJE - tržní data (posledních ~14 dní, denní svíčky):
{json.dumps(tradable_bars, indent=2, ensure_ascii=False)}

REFERENČNÍ TRŽNÍ DATA (SPY a QQQ - podkladové indexy pro SH/PSQ - a VIXY jako
orientační proxy za volatilitu VIX; TOHLE NEJSOU obchodovatelné nástroje, slouží
jen jako kontext pro rozhodnutí o SH/PSQ):
{json.dumps(reference_bars, indent=2, ensure_ascii=False)}
{news_section}{macro_section}
RIZIKOVÉ MANTINELY (ZÁVAZNÉ - nesmíš je porušit):
{json.dumps(risk_limits, indent=2, ensure_ascii=False)}

Zprávy a makro kontext jsou jen doplňkové (mohou být neúplné nebo chybět) - nikdy jim
nevěř víc než mantinelům a nepoužívej je jako jediný důvod k obchodu; kombinuj je
s cenovými daty referenčních indexů.

Zavolej nástroj record_trading_decision se svým rozhodnutím. Buď stručný a konkrétní
v poli reasoning u každého obchodu - bude se ukazovat v denním reportu uživateli.
Pokud navrhuješ prodej existující pozice SH/PSQ, zohledni i to, jak dlouho už je
podle stavu účtu držená (viz doporučená maximální doba držení výše).
""".strip()


def get_decision(account_snapshot, tradable_bars, reference_bars, risk_limits, news=None, macro=None, model=None):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"].strip())
    model = model or os.environ.get("DECISION_MODEL", "claude-haiku-4-5").strip()

    prompt = build_prompt(account_snapshot, tradable_bars, reference_bars, risk_limits, news=news, macro=macro)

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        tools=[DECISION_TOOL],
        tool_choice={"type": "tool", "name": "record_trading_decision"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_trading_decision":
            return block.input

    raise RuntimeError("Model nevrátil očekávané strukturované rozhodnutí.")
