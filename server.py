"""Local-only EUIPO MCP service; require Auth0 bearer authorization for all tools."""
from __future__ import annotations
import json
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from auth0_verifier import Auth0TokenVerifier, AUTH0_ISSUER, RESOURCE_URL, REQUIRED_PERMISSION
from core import create_variants, comparative_age
from euipo import EUIPOClient
from similarity import euipo_similarity_search

mcp=FastMCP(
    "Markenpruefassistent",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
    json_response=True,
    auth=AuthSettings(
        issuer_url=AUTH0_ISSUER,
        resource_server_url=RESOURCE_URL,
        required_scopes=[REQUIRED_PERMISSION],
        validate_token_resource=False,  # Auth0 audience is validated strictly in verifier.
    ),
    token_verifier=Auth0TokenVerifier(),
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

@mcp.tool()
async def euipo_aehnlichkeitsrecherche(
    zeichen: str,
    nizza_klasse: int = 0,
    weitere_suchbegriffe: list[str] | None = None,
    seiten_pro_suche: int = 2,
    seitenumfang: int = 25,
    nur_potenziell_lebende: bool = True,
    markenbasis: str = "ALL",
) -> dict:
    """Begrenzte EUIPO-Wortmarken-Kandidatensuche: identische und technisch ähnliche Zeichen.

    Berücksichtigt angemeldete/eingetragene Status, markiert unklare Status.
    Keine vollständige Kollisionsrecherche. Klang-/Begriffsvarianten gesondert vorgeben.
    """
    try:
        return await euipo_similarity_search(
            zeichen=zeichen,
            nizza_klasse=nizza_klasse,
            weitere_suchbegriffe=weitere_suchbegriffe,
            seiten_pro_suche=seiten_pro_suche,
            seitenumfang=seitenumfang,
            nur_potenziell_lebende=nur_potenziell_lebende,
            markenbasis=markenbasis,
        )
    except (RuntimeError, ValueError) as e:
        return {"fehler": str(e), "recherchestand": "nicht durchgeführt"}
    except Exception:
        return {
            "fehler": "Ähnlichkeitsrecherche fehlgeschlagen; serverseitig prüfen",
            "recherchestand": "nicht durchgeführt",
        }


if __name__=="__main__":
    mcp.run(transport="streamable-http")
