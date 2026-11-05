"""Bounded candidate search for EUIPO wordmarks; NOT an exhaustive clearance search."""
from __future__ import annotations
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from euipo import EUIPOClient, build_query

# Only a preliminary register-status classification, not legal enforceability.
ACTIVE = frozenset({
    "RECEIVED", "UNDER_EXAMINATION", "APPLICATION_PUBLISHED",
    "REGISTRATION_PENDING", "REGISTERED", "OPPOSITION_PENDING",
    "CANCELLATION_PENDING", "START_OF_OPPOSITION_PERIOD",
    "ACCEPTANCE_PENDING", "ACCEPTED",
})
DEAD = frozenset({
    "WITHDRAWN", "REFUSED", "CANCELLED", "SURRENDERED",
    "EXPIRED", "REMOVED_FROM_REGISTER",
})

def _compact(s: str) -> str:
    s=unicodedata.normalize("NFKC",s).casefold()
    return "".join(c for c in s if c.isalnum())

def _literal(s: str) -> str:
    # Preserve punctuation and word boundaries when assessing exact identity.
    return " ".join(unicodedata.normalize("NFKC",s).casefold().split())

def _word(mark: dict[str,Any]) -> str:
    value=mark.get("wordMarkSpecification")
    if isinstance(value,str): return value
    if isinstance(value,dict):
        elem=value.get("verbalElement")
        if isinstance(elem,str):return elem
        if isinstance(elem,dict):
            for key in ("value","text","literal"):
                if isinstance(elem.get(key),str):return elem[key]
    return ""

def _status(value: object) -> str:
    s=str(value or "").strip().upper()
    if s in ACTIVE:return "potenziell lebend"
    if s in DEAD:return "laut Status nicht lebend"
    # APPEALED/APPEALABLE and unknown statuses require examination.
    return "Status manuell prüfen"

def _validate(term: str) -> str:
    build_query(term,None,None)
    result=term.strip()
    if not _compact(result):raise ValueError("Suchbegriff ohne Buchstaben oder Ziffern")
    return result

def _candidate(mark: dict[str,Any], target: str, via: str) -> dict[str,Any]:
    name=_word(mark)
    return {
        "zeichen":name or None,
        "anmeldenummer":mark.get("applicationNumber"),
        "markenbasis":mark.get("markBasis"),
        "registerstatus":mark.get("status"),
        "statusbewertung":_status(mark.get("status")),
        "anmeldedatum":mark.get("applicationDate"),
        "eintragungsdatum":mark.get("registrationDate"),
        "nizza_klassen":mark.get("niceClasses"),
        "identischer_wortlaut":bool(name) and _literal(name)==_literal(target),
        "schriftbild_aehnlichkeit_technisch":round(SequenceMatcher(None,_compact(target),_compact(name)).ratio(),3) if name else None,
        "gefunden_ueber":[via],
    }

async def euipo_similarity_search(
    zeichen: str,
    nizza_klasse: int=0,
    weitere_suchbegriffe: list[str] | None=None,
    seiten_pro_suche: int=2,
    seitenumfang: int=25,
    nur_potenziell_lebende: bool=True,
    markenbasis: str="ALL",
    *,
    client: Any=None,
) -> dict[str,Any]:
    """Research typed substrings; caller supplies phonetic/conceptual variants.
    
    Search covers only a limited number of pages for each query. It does not
    search all European national registers or guarantee exhaustive similarity.
    """
    zeichen=_validate(zeichen)
    if type(nizza_klasse) is not int or not 0<=nizza_klasse<=45:
        raise ValueError("Nizza-Klasse: 0 (alle) oder 1 bis 45")
    if type(seiten_pro_suche) is not int or not 1<=seiten_pro_suche<=3:
        raise ValueError("Seiten pro Suchbegriff: 1 bis 3")
    if type(seitenumfang) is not int or not 10<=seitenumfang<=100:
        raise ValueError("Seitengröße: 10 bis 100")
    if weitere_suchbegriffe is not None and (
        not isinstance(weitere_suchbegriffe,list) or len(weitere_suchbegriffe)>5 or
        any(not isinstance(x,str) for x in weitere_suchbegriffe)
    ):
        raise ValueError("Maximal fünf zusätzliche Suchbegriffe")
    terms=[zeichen]+[_validate(x) for x in (weitere_suchbegriffe or [])]
    # Case-insensitive deduplication; do NOT merge 'XY' and 'X-Y'.
    seen=set()
    terms=[t for t in terms if not (_literal(t) in seen or seen.add(_literal(t)))]
    if client is None:client=EUIPOClient()

    found={}
    queries=[]
    errors=[]
    limited=False
    for term in terms:
        for page in range(seiten_pro_suche):
            try:
                result=await client.search_wordmarks(
                    term,nizza_klasse or None,status=None,
                    page=page,size=seitenumfang,mark_basis=markenbasis
                )
                hits=result.get("marken")
                if not isinstance(hits,list):
                    raise RuntimeError("EUIPO-Trefferformat unbekannt")
            except Exception:
                # Deliberately avoid leaking token, client secret or request headers.
                errors.append({"suchbegriff":term,"seite":page,"hinweis":"EUIPO-Antwort fehlgeschlagen oder nicht auswertbar"})
                limited=True
                break
            queries.append({
                "suchbegriff":term,"seite":page,
                "treffer_gesamt_gemeldet":result.get("treffer_gesamt"),
                "seiten_gesamt_gemeldet":result.get("seiten_gesamt"),
                "treffer_dieser_seite":len(hits),
            })
            for item in hits:
                if not isinstance(item,dict):continue
                mark=_candidate(item,zeichen,term)
                # Same registered mark can be returned by multiple searches.
                number=mark["anmeldenummer"]
                key=str(mark["markenbasis"] or "")+":"+str(number) if number else "unknown:"+str(len(found))
                if key in found:
                    if term not in found[key]["gefunden_ueber"]:
                        found[key]["gefunden_ueber"].append(term)
                else:found[key]=mark
            total=result.get("seiten_gesamt")
            if isinstance(total,int) and page+1>=total:break
            if len(hits)<seitenumfang:break
            if page+1==seiten_pro_suche:limited=True

    candidates=list(found.values())
    active=[x for x in candidates if x["statusbewertung"]=="potenziell lebend"]
    review=[x for x in candidates if x["statusbewertung"]=="Status manuell prüfen"]
    dead=[x for x in candidates if x["statusbewertung"]=="laut Status nicht lebend"]
    def rank(x):
        return (not x["identischer_wortlaut"],
                -(x["schriftbild_aehnlichkeit_technisch"] or 0),x["zeichen"] or "")
    for group in (active,review,dead):group.sort(key=rank)
    return {
        "recherchestand":"teilweise durchgeführt" if limited or errors else "API-Teilrecherche durchgeführt",
        "zeichen":zeichen,
        "schutzbereich":"EUIPO-Unionsmarken und ggf. IR mit EU-Benennung; keine vollständige Europarecherche",
        "nizza_klasse_vorfilter":nizza_klasse or None,
        "abfragen":queries,
        "potenziell_lebende_marken":active,
        "status_manuell_pruefen":review,
        "nicht_lebende_marken":[] if nur_potenziell_lebende else dead,
        "nicht_lebende_ausgefiltert":len(dead) if nur_potenziell_lebende else 0,
        "anzahl_identischer_lebender_treffer":sum(x["identischer_wortlaut"] for x in active),
        "abfragefehler":errors,
        "vollstaendigkeit":"NICHT garantiert; begrenzte Teilstringabfragen, keine systematische phonetische/begriffliche Suche",
        "hinweise":[
            "Schriftbildliche Rangfolge ist technisch, nicht rechtsverbindlich.",
            "Klangliche/begriffliche Varianten gesondert als Suchbegriffe vorgeben.",
            "Streitige oder unbekannte Registerstatus manuell überprüfen.",
            "Waren/DL anhand des Detailverzeichnisses prüfen, Nizza-Klasse nur als Vorfilter.",
            "Nationale Marken und sonstige ältere Rechte nicht vollständig erfasst.",
        ],
    }
