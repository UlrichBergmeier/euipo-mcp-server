"""Local-only EUIPO MCP service; require Auth0 bearer authorization for all tools."""
from __future__ import annotations
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Image
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from mcp.server.auth.settings import AuthSettings
from auth0_verifier import Auth0TokenVerifier, AUTH0_ISSUER, RESOURCE_URL, REQUIRED_PERMISSION
from core import create_variants, comparative_age
from euipo import EUIPOClient, validate_application_number
from euipo_extensions import advanced_search, get_trademark_image
from similarity import euipo_similarity_search
from class_goods import parse_class_goods, validate_reference_terms

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
    registerstatus: str = "ALLE",
    seite: int = 0,
    seitenumfang: int = 20,
    markenbasis: str = "ALL",
)->dict:
    """EUIPO-Wortmarken; standardmäßig alle Registerstatus einschließlich Anmeldungen.

    Für nur eingetragene Marken registerstatus='REGISTERED' angeben.
    """
    try:
        status = None if registerstatus in ("ALLE", "ALL", "") else registerstatus
        return await EUIPOClient().search_wordmarks(suchbegriff,nizza_klasse or None,
                        status,seite,seitenumfang,markenbasis)
    except (RuntimeError,ValueError) as e:
        return {"fehler":str(e),"recherchestand":"nicht durchgeführt"}
    except Exception:
        return {"fehler":"EUIPO-Abfrage fehlgeschlagen; serverseitig prüfen","recherchestand":"nicht durchgeführt"}

@mcp.tool()
async def euipo_markendetails(anmeldenummer: str)->dict:
    """Rufe vollständige Registerdaten einschließlich Prioritäten und Verfahren ab."""
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



@mcp.tool()
async def euipo_erweiterte_markenrecherche(
    suchbegriff: str = "",
    nizza_klassen: list[int] | None = None,
    klassenmodus: str = "ANY",
    registerstatus: list[str] | None = None,
    markenformen: list[str] | None = None,
    markenbasis: str = "ALL",
    anmelder: str = "",
    vertreter: str = "",
    angemeldet_ab: str = "",
    angemeldet_bis: str = "",
    seite: int = 0,
    seitenumfang: int = 20,
    sortierfeld: str = "applicationDate",
    sortierrichtung: str = "desc",
) -> dict:
    """Strukturierte EUIPO-Teilrecherche: Text, Klassen (ANY/ALL), mehrere
    Registerstatus, Markenformen, EU/IR-Basis, Namen, Anmeldedatum und Sortierung.

    Keine Statusangabe = alle Registerstatus. Auch FIGURATIVE mit indexiertem
    Textelement recherchierbar. Je Aufruf eine Ergebnisseite; keine vollständige
    Kollisionsrecherche.
    """
    try:
        return await advanced_search(
            EUIPOClient(), suchbegriff=suchbegriff,
            nizza_klassen=nizza_klassen, klassenmodus=klassenmodus,
            registerstatus=registerstatus, markenformen=markenformen,
            markenbasis=markenbasis, anmelder=anmelder, vertreter=vertreter,
            angemeldet_ab=angemeldet_ab, angemeldet_bis=angemeldet_bis,
            seite=seite, seitenumfang=seitenumfang, sortierfeld=sortierfeld,
            sortierrichtung=sortierrichtung,
        )
    except (RuntimeError, ValueError) as e:
        return {"fehler": str(e), "recherchestand": "nicht durchgeführt"}
    except Exception:
        return {
            "fehler": "Erweiterte EUIPO-Abfrage fehlgeschlagen; serverseitig prüfen",
            "recherchestand": "nicht durchgeführt",
        }


@mcp.tool()
async def euipo_markenabbildung(anmeldenummer: str, vorschaubild: bool = True):
    """EUIPO-Markenabbildung direkt als geschütztes MCP-Bild abrufen.

    Thumbnail bis 512 KB, Original bis 2 MB. Keine EUIPO-URLs oder API-Schlüssel
    an ChatGPT ausgeben. Wortmarken können ohne Bild geführt sein.
    """
    try:
        data, fmt = await get_trademark_image(EUIPOClient(), anmeldenummer, vorschaubild)
        return Image(data=data, format=fmt)
    except (RuntimeError, ValueError) as e:
        return {"fehler": str(e), "recherchestand": "nicht durchgeführt"}
    except Exception:
        return {
            "fehler": "Markenabbildung nicht verfügbar; serverseitig prüfen",
            "recherchestand": "nicht durchgeführt",
        }



# MCP Apps: standalone UI-bound render tool. The existing seven tools and
# OAuth validation remain unchanged. The iframe fetches image bytes with the
# existing euipo_markenabbildung tool through the authenticated MCP bridge.
_VIEWER_URI = "ui://euipo/markenanzeige-v1.html"

@mcp.resource(
    _VIEWER_URI,
    name="euipo-markenanzeige",
    title="EUIPO Markenabbildung",
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {"csp": {"connectDomains": [], "resourceDomains": []}},
        "openai/ui": {"availableDisplayModes": ["inline", "fullscreen"]},
    },
)
def euipo_markenanzeige_ui() -> str:
    """Trusted, static EUIPO image viewer, without API credentials or external assets."""
    return Path(__file__).with_name("trademark_viewer.html").read_text(encoding="utf-8")


@mcp.tool(
    name="euipo_markenanzeige",
    title="EUIPO Markenabbildung im Chat anzeigen",
    description=(
        "Zeige eine EUIPO-Markenabbildung als interaktive MCP-App direkt im Chat an. "
        "Verwenden, wenn die Benutzerin oder der Benutzer ein Markenbild sehen möchte. "
        "Die Ansicht lädt zunächst ein Vorschaubild und kann das Original darstellen. "
        "Wenn der Chat keine MCP Apps unterstützt, ist nur eine textuelle Bestätigung möglich."
    ),
    structured_output=False,
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
    meta={
        "ui": {"resourceUri": _VIEWER_URI, "visibility": ["model", "app"]},
        "openai/outputTemplate": _VIEWER_URI,
        "openai/toolInvocation/invoking": "EUIPO-Markenbild wird geöffnet …",
        "openai/toolInvocation/invoked": "EUIPO-Bildansicht bereitgestellt",
    },
)
def euipo_markenanzeige(anmeldenummer: str) -> CallToolResult:
    """Bereite die geschützte MCP-App-Bildanzeige vor; rendert nicht in Text-Clients."""
    try:
        number = validate_application_number(anmeldenummer)
    except ValueError:
        return CallToolResult(
            content=[TextContent(type="text", text="Ungültige EUIPO-Anmeldenummer.")],
            isError=True,
        )
    return CallToolResult(
        content=[TextContent(
            type="text",
            text=(
                f"EUIPO-MCP-Bildansicht für die Marke {number} angefordert. "
                "Die Abbildung wird nur angezeigt, wenn der Chat MCP Apps darstellen "
                "und den geschützten Bildabruf autorisieren kann. "
                "Ohne sichtbare Ansicht bitte nicht behaupten, das Bild sei angezeigt worden."
            ),
        )],
        structuredContent={"anmeldenummer": number},
    )



# Visuelle Kandidatenliste: gesonderte, begrenzte UI-Darstellung der bestehenden
# Ähnlichkeitssuche. Die bisherige Suchfunktion und das Markenbildwerkzeug
# bleiben funktional unverändert.
_GALLERY_URI = "ui://euipo/aehnlichkeitsgalerie-v1.html"

@mcp.resource(
    _GALLERY_URI,
    name="euipo-aehnlichkeitsgalerie",
    title="EUIPO Ähnlichkeitsrecherche mit Markenabbildungen",
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {"csp": {"connectDomains": [], "resourceDomains": []}},
        "openai/ui": {"availableDisplayModes": ["inline", "fullscreen"]},
    },
)
def euipo_aehnlichkeitsgalerie_ui() -> str:
    """Statische, selbstständige Vergleichsansicht ohne Browserzugriff auf EUIPO-Secrets."""
    return Path(__file__).with_name("similarity_gallery.html").read_text(encoding="utf-8")


@mcp.tool(
    name="euipo_aehnlichkeitsgalerie",
    title="EUIPO-Ähnlichkeitsrecherche mit Vergleichsbildern",
    description=(
        "Führe die bestehende begrenzte EUIPO-Ähnlichkeitsrecherche durch und zeige "
        "ihre Kandidaten mit Registerstatus, Klassen und tatsächlichen Markenabbildungen "
        "in einer Vergleichsgalerie direkt in ChatGPT an. Klassen sind anklickbar; "
        "dort werden tatsächliche EUIPO-Waren-/DL-Verzeichnisse angezeigt. "
        "Wenn vom Nutzer konkrete Waren oder Dienstleistungen vorgegeben sind, "
        "diese in referenzwaren_dienstleistungen übergeben: Nur dann wird pro Klasse "
        "textlich identische und technisch ähnliche Begriffe hervorgehoben werden. "
        "Die Galerie priorisiert Treffer mit einem ausdrücklich nicht statistischen "
        "Risikoindex als Arbeitshilfe; juristische Zeichenähnlichkeit, Warenähnlichkeit "
        "und Kennzeichnungskraft dürfen nicht als geprüft ausgegeben werden. "
        "Nicht die gesuchten Markennamen als Waren unterstellen. Nur verfügbare "
        "Abbildungen laden; Wortmarken bleiben Wortmarken. Keine Vollständigkeit "
        "oder rechtliche Warenähnlichkeit bzw. Verwechslungsgefahr behaupten."
    ),
    structured_output=False,
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    meta={
        "ui": {"resourceUri": _GALLERY_URI, "visibility": ["model", "app"]},
        "openai/outputTemplate": _GALLERY_URI,
        "openai/toolInvocation/invoking": "EUIPO-Vergleichsmarken werden recherchiert …",
        "openai/toolInvocation/invoked": "EUIPO-Vergleichsgalerie bereitgestellt",
    },
)
async def euipo_aehnlichkeitsgalerie(
    zeichen: str,
    nizza_klasse: int = 0,
    weitere_suchbegriffe: list[str] | None = None,
    nur_potenziell_lebende: bool = True,
    markenbasis: str = "ALL",
    referenzwaren_dienstleistungen: list[str] | None = None,
) -> CallToolResult:
    """Erstellt eine begrenzte visuelle Kandidatenliste, ohne Bilddaten in JSON auszugeben."""
    try:
        references = validate_reference_terms(referenzwaren_dienstleistungen)
        result = await euipo_similarity_search(
            zeichen=zeichen,
            nizza_klasse=nizza_klasse,
            weitere_suchbegriffe=weitere_suchbegriffe,
            seiten_pro_suche=1,
            seitenumfang=25,
            nur_potenziell_lebende=nur_potenziell_lebende,
            markenbasis=markenbasis,
        )
        if not result.get("abfragen"):
            raise RuntimeError("Keine erfolgreiche EUIPO-Teilabfrage")
    except (ValueError, RuntimeError):
        return CallToolResult(
            content=[TextContent(type="text", text="EUIPO-Vergleichsrecherche konnte nicht ausgeführt werden.")],
            isError=True,
        )
    except Exception:
        return CallToolResult(
            content=[TextContent(type="text", text="EUIPO-Abfrage fehlgeschlagen; serverseitig prüfen.")],
            isError=True,
        )
    candidates = (
        result["potenziell_lebende_marken"]
        + result["status_manuell_pruefen"]
        + result["nicht_lebende_marken"]
    )
    # No exhaustive register clearance. Keep tool responses bounded and
    # preserve their actual returned rank/status (never fabricate images).
    limit = 40
    summary = {
        "zeichen": result["zeichen"],
        "nizza_klasse": result["nizza_klasse_vorfilter"],
        "recherchestand": result["recherchestand"],
        "gesamt_kandidaten": len(candidates),
        "kandidaten": candidates[:limit],
        "abfragefehler": len(result["abfragefehler"]),
        "vollstaendigkeit": result["vollstaendigkeit"],
        "referenzwaren_dienstleistungen": references,
    }
    message = (
        f"EUIPO-Ähnlichkeitsgalerie für {result['zeichen']}: "
        f"{len(candidates)} Kandidaten aus begrenzten Teilabfragen, "
        f"{min(limit,len(candidates))} für die Galerie bereitgestellt. "
        f"Teilabfragefehler: {len(result['abfragefehler'])}. "
        "Markenabbildungen werden ausschließlich in der eingebetteten MCP-App "
        "über das geschützte EUIPO-Werkzeug geladen. "
        "Ohne tatsächlich sichtbare Galerie keine Bilddarstellung behaupten. "
        "Keine vollständige Kollisionsrecherche oder rechtliche Risikoabschätzung."
    )
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structuredContent=summary,
    )




@mcp.tool(
    name="euipo_klassendetails",
    title="EUIPO: tatsächliche Waren/Dienstleistungen je Klasse",
    description=(
        "Rufe für eine konkrete EUIPO-Marke und Nizza-Klasse die tatsächlich im "
        "Register eingetragenen Waren/Dienstleistungen bevorzugt auf Deutsch ab. "
        "Mit nizza_klasse=0 werden alle Klassen dieser Marke in einem einzigen "
        "Registerdetailabruf geliefert. Optional aus Referenzwaren die "
        "textlich identischen oder technisch ähnlichsten Positionen ermitteln. "
        "Diese technische Vorauswahl ist ausdrücklich keine rechtliche "
        "Ähnlichkeitsbewertung; fremdsprachige Texte nicht als Deutsch ausgeben."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
)
async def euipo_klassendetails(
    anmeldenummer: str,
    nizza_klasse: int,
    referenzwaren: list[str] | None = None,
) -> dict:
    """Gezielter, authentifizierter Detailabruf erst nach dem Klassen-Klick."""
    try:
        validate_application_number(anmeldenummer)
        if type(nizza_klasse) is not int or not 0 <= nizza_klasse <= 45:
            raise ValueError("Nizza-Klasse muss zwischen 0 und 45 liegen")
        validate_reference_terms(referenzwaren)
        detail = await EUIPOClient().trademark_detail(anmeldenummer)
        if nizza_klasse == 0:
            goods = detail.get("goodsAndServices")
            if not isinstance(goods, list):
                raise RuntimeError("EUIPO-Warenverzeichnis ist nicht verfügbar")
            classes = sorted({
                item["classNumber"] for item in goods
                if isinstance(item, dict) and type(item.get("classNumber")) is int
                and 1 <= item["classNumber"] <= 45
            })
            return {
                "anmeldenummer": anmeldenummer,
                "nizza_klasse": 0,
                "klassen": [parse_class_goods(detail, c, referenzwaren) for c in classes],
                "hinweis": "Nur tatsächliche Registerverzeichnisse; technische Texttreffer ohne Rechtsbewertung.",
            }
        return parse_class_goods(detail, nizza_klasse, referenzwaren)
    except (RuntimeError, ValueError):
        return {"fehler": "Waren-/Dienstleistungsverzeichnis nicht verfügbar oder Eingabe ungültig."}
    except Exception:
        return {"fehler": "EUIPO-Detailabruf fehlgeschlagen; serverseitig prüfen."}


if __name__=="__main__":
    mcp.run(transport="streamable-http")
