"""LOCAL-ONLY MCP test server. Never publish without user OAuth protection."""
from __future__ import annotations
import json
from mcp.server.fastmcp import FastMCP
from core import create_variants, comparative_age
from euipo import EUIPOClient

mcp=FastMCP(
    "Markenpruefassistent",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
    json_response=True,
    instructions=(
        "Alle Waren und Dienstleistungen getrennt beurteilen. "
        "Keine Wegprägung interner Wortbestandteile. "
        "Das Gesamtzeichen immer abschließend prüfen. "
        "EUIPO-Registerdaten sind keine rechtliche Entscheidung. "
        "Keine erfundenen Treffer. Wortmarke zuerst, danach separate Bildmarke, "
        "kombinierte Wort-/Bildmarke als Alternative."
    )
)

@mcp.tool()
def markenvarianten_erstellen(
    zeichen: str,
    waren_dienstleistungen: str,
    schutzgebiet: str = "DE",
    wortbewertungen_json: str = "{}",
    zusammensetzungen_json: str = "{}",
    logo_vorhanden: bool = False,
    logo_unterscheidungskraft: str = "unbekannt",
    nur_eine_anmeldung: bool = False,
    stets_gemeinsam_benutzt: bool = False,
) -> dict:
    """Erzeuge priorisierte Varianten aus fachlich bewerteten vollständigen Wörtern."""
    return create_variants(zeichen,waren_dienstleistungen,schutzgebiet,
      json.loads(wortbewertungen_json),logo_vorhanden,logo_unterscheidungskraft,
      nur_eine_anmeldung,stets_gemeinsam_benutzt,json.loads(zusammensetzungen_json))

@mcp.tool()
def alter_vergleichsmarke(anmeldedatum: str)->dict:
    """Berechne Alter ohne eine rechtsverbindliche Wahrscheinlichkeit zu behaupten."""
    return comparative_age(anmeldedatum)

@mcp.tool()
async def euipo_wortmarkenrecherche(
    suchbegriff: str,
    nizza_klasse: int = 0,
    registerstatus: str = "REGISTERED",
    seite: int = 0,
    seitenumfang: int = 20,
    markenbasis: str = "ALL",
)->dict:
    """Recherchiere EUIPO-Wortmarken. Benötigt serverseitige EUIPO-Zugangsdaten."""
    try:
        return await EUIPOClient().search_wordmarks(suchbegriff,nizza_klasse or None,
                        registerstatus,seite,seitenumfang,markenbasis)
    except (RuntimeError,ValueError) as e:
        return {"fehler":str(e),"recherchestand":"nicht durchgeführt"}
    except Exception:
        return {"fehler":"EUIPO-Abfrage fehlgeschlagen; serverseitig prüfen","recherchestand":"nicht durchgeführt"}

@mcp.tool()
async def euipo_markendetails(anmeldenummer: str)->dict:
    """Rufe Registerdaten und Waren-/Dienstleistungsverzeichnis einer Marke ab."""
    try:
        return await EUIPOClient().trademark_detail(anmeldenummer)
    except (RuntimeError,ValueError) as e:
        return {"fehler":str(e),"recherchestand":"nicht durchgeführt"}
    except Exception:
        return {"fehler":"EUIPO-Detailabruf fehlgeschlagen; serverseitig prüfen","recherchestand":"nicht durchgeführt"}

if __name__=="__main__":
    mcp.run(transport="streamable-http")
