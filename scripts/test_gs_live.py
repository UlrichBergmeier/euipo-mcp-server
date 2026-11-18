"""Isolated live smoke test of EUIPO Goods & Services, with protected credentials.

Run only inside a disposable container with read-only secret mounts.
Print no client IDs, secrets, access tokens, request headers or traceback.
"""
import asyncio
from goods_services import harmonize, suggestions, translations

async def run():
    data = [{"classNumber": 19, "terms": ["Beton."]}]
    print("Starte drei EUIPO-Goods-and-Services-Liveabfragen...", flush=True)
    try:
        validate = await harmonize(data, "de")
        row = validate["goodsAndServices"][0]["terms"][0]
        print("Harmonisierung:", row["status"], "Begriff:", row["abgefragt"],
              "Klasse: 19", flush=True)
        if row["status"] != "harmonisiert":
            print("STOP: Ergebnis nicht eindeutig zugeordnet", flush=True)
            return 2

        suggested = await suggestions(["Betonfertigteilee."], "de", 19, 5)
        groups = suggested["vorschlaege"]
        print("Vorschlagssuche: OK; Ergebnisgruppen:", len(groups), flush=True)
        if not groups:
            print("STOP: Keine Vorschlagsgruppen", flush=True)
            return 3

        translated = await translations(data, "de", ["en"])
        en = translated["uebersetzungen"].get("en")
        if not isinstance(en, list) or not en:
            print("STOP: Keine englischen Übersetzungen", flush=True)
            return 4
        first = en[0]
        term = first.get("terms") if isinstance(first, dict) else None
        print("Übersetzung nach Englisch:", str(term)[:200], flush=True)
        if not isinstance(term, list) or not term:
            print("STOP: Übersetzungsformat unerwartet", flush=True)
            return 5
        print("Alle drei Live-Tests erfolgreich", flush=True)
        return 0
    except Exception as exc:
        # Deliberately no traceback or raw HTTP response.
        print("Live-Test fehlgeschlagen:", type(exc).__name__, flush=True)
        return 1

if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
