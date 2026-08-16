# AI bearish bot (inverzní ETF, Alpaca paper trading + Claude)

Sesterský projekt k dlouhodobému [ai-trading-bot](https://github.com/dejeka33/ai-trading-bot),
zaměřený na OBRANNOU strategii - v době, kdy vypadá pravděpodobný pokles trhu,
nakoupí inverzní ETF (SH, PSQ), jinak zůstává v hotovosti. Běží ve VLASTNÍM
GitHub repozitáři a s VLASTNÍM (samostatným) Alpaca paper účtem, aby se
pozice a rozhodování nemísily s dlouhodobým botem.

Denní automatický běh: stáhne tržní data z Alpaca (SH/PSQ + referenční SPY/QQQ/VIXY),
volitelně makro kontext z FRED, pošle je Claude modelu k rozhodnutí, zkontroluje
návrh proti rizikovým mantinelům, provede schválené obchody a uloží/zveřejní
report. Navíc běží samostatná, levnější (bez AI) intradenní kontrola, která
hlídá stop-loss mezi dvěma denními rozhodnutími.

## Proč inverzní ETF, ne skutečné shortování

Skutečné shortování (short selling) má teoreticky neomezené riziko ztráty a
vyžaduje margin účet. Inverzní ETF (SH, PSQ) se kupují úplně stejně jako
normální ETF - žádná páka, žádné vypůjčování akcií, ztráta je omezená na
vloženou částku. Mají ale tzv. decay riziko: sledují DENNÍ (ne dlouhodobou)
inverzní výkonnost indexu, takže při delším držení v kolísavém trhu ztrácí
hodnotu i bez ohledu na celkový směr trhu. Proto je u téhle appky výchozí
bezpečná pozice HOTOVOST, ne držení ETF - viz `decision.py`.

## Co je potřeba nastavit (jednorázově)

1. **Vytvoř nový, samostatný GitHub repozitář** (klidně privátní) a nahraj
   do něj tento adresář - všechny soubory.

2. **Vytvoř druhý, samostatný Alpaca paper trading účet** (nebo aspoň
   samostatnou sadu API klíčů navázanou na jiný paper účet) - použití
   stejného účtu jako u dlouhodobého bota by mísilo pozice obou strategií
   do jednoho portfolia a matlo by to rozhodování obou AI.

3. **Anthropic API klíč** - lze použít stejný jako u dlouhodobého bota
   (je to jen otázka spotřeby/nákladů, ne oddělení účtů).

4. **Volitelně: FRED API klíč** (zdarma) - https://fred.stlouisfed.org/docs/api/api_key.html
   - bez něj bot jede úplně stejně, jen bez makro kontextu (výnosy dluhopisů,
   sazba Fedu) v promptu.

5. V nastavení GitHub repozitáře: **Settings → Secrets and variables →
   Actions → New repository secret** a přidej:
   - `ALPACA_API_KEY_ID` (z nového/druhého paper účtu)
   - `ALPACA_API_SECRET_KEY` (z nového/druhého paper účtu)
   - `ALPACA_API_BASE_URL` (hodnota: `https://paper-api.alpaca.markets/v2`)
   - `ANTHROPIC_API_KEY`
   - `FRED_API_KEY` (volitelné)

6. **Workflow soubory** (`.github/workflows/*.yml`) je potřeba do repozitáře
   přidat/commitnout ručně přes GitHub - obsah je připravený v tomto adresáři:
   - `daily_trading.yml` - denní AI rozhodnutí (21:30 UTC)
   - `intraday_check.yml` - bezpečnostní stop-loss kontrola 4x denně v
     obchodních hodinách, BEZ volání AI (žádné dodatečné náklady)

7. **Zapni GitHub Pages** pro tento repozitář (Settings → Pages → Deploy
   from branch → `main` → `/docs`), aby byl dashboard veřejně (jen podle
   odkazu) dostupný stejně jako u dlouhodobého bota.

8. Doporučuju první běh obou workflow spustit ručně (workflow_dispatch) a
   zkontrolovat výstup, než necháš běžet automaticky.

## Push notifikace přímo z ikony dashboardu (volitelné)

Appka umí po každém denním běhu poslat push notifikaci nainstalovaného
dashboardu (PWA) na telefonu - vypadá, že jde přímo z appky, žádná další
appka (Telegram apod.) není potřeba. Navíc pošle urgentní notifikaci,
kdykoliv zasáhne automatický intradenní stop-loss. Bez nastavení appka
funguje úplně stejně jako dřív, jen notifikace neposílá.

Obě hodnoty níže se ukládají jen jako GitHub Secrets, NIKDY jako obyčejný
soubor v repozitáři - i když je repozitář veřejný (kvůli GitHub Pages na
zdarma účtu typicky musí být), secrets zůstávají skryté stejně jako ostatní
API klíče.

1. Otevři si dashboard appky na telefonu (v prohlížeči, ideálně tu
   nainstalovanou verzi) a klikni na tlačítko **"Zapnout push notifikace"**
   nahoře pod nadpisem. Povol notifikace, když se o to prohlížeč zeptá.
   POZOR: udělej tohle na dashboardu TÉTO appky (ne dlouhodobé) - každá
   appka běží na jiné adrese, takže vyžaduje vlastní přihlášení.
2. Zobrazí se text (JSON) - zkopíruj ho celý.
3. Přidej do GitHub Secrets TOHOTO repozitáře (Settings → Secrets and
   variables → Actions → New repository secret):
   - `PUSH_SUBSCRIPTION_JSON` (text z kroku 2, vlož ho celý přesně jak je)
   - `VAPID_PRIVATE_KEY` - hodnotu ti dám já (je to vygenerovaný
     kryptografický klíč, ne heslo k ničemu tvému; stejný klíč jako
     u dlouhodobé appky, jen musí být zadaný znovu - secrets se mezi
     repozitáři nesdílí)
4. Pokud by notifikace časem přestaly chodit (prohlížeč umí odhlášení
   samo zneplatnit), stačí zopakovat kroky 1-3 (přepsat starý secret
   novým textem).

## Odhad nákladů

- GitHub Actions: zdarma (stejně jako u dlouhodobého bota).
- Anthropic API: řádově 2-3 centy na jedno denní rozhodnutí - intradenní
  kontrola AI vůbec nevolá, takže nepřidává žádné další náklady.
- FRED API: zdarma.

## Struktura projektu

- `config/risk_limits.yaml` - rizikové mantinely; `allowed_instruments` = jen
  SH/PSQ, `reference_instruments` = SPY/QQQ/VIXY (jen kontext, NEOBCHODOVATELNÉ)
- `data_fetch.py` - stahování dat z Alpaca
- `fred_data.py` - volitelný makro kontext z FRED
- `decision.py` - dotaz na Claude a strukturované rozhodnutí (prompt vysvětluje
  decay riziko a preferenci hotovosti)
- `risk_rules.py` - validace rozhodnutí proti mantinelům
- `execute.py` - provedení obchodů
- `intraday_check.py` - pravidlová (bez AI) stop-loss pojistka mezi denními běhy
- `webpush_notify.py` - volitelné push notifikace přímo do ikony dashboardu (Web Push)
- `report.py` - generování denního reportu
- `main.py` - spojuje denní běh dohromady
- `reports/` - sem se ukládají denní reporty a intradenní stop-loss logy
- `docs/` - dashboard publikovaný přes GitHub Pages
