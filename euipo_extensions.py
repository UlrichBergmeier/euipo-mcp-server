"""Bounded structured search and image retrieval per EUIPO Trademark Search 1.1.0."""
from __future__ import annotations
from datetime import date, datetime, timezone
import re
import httpx
from euipo import (API_BASE_URL, BASES, FEATURES, STATUSES, _substring,
                   validate_application_number)

SORT_FIELDS = frozenset({"applicationNumber", "applicationReference", "applicationDate",
    "designationDate", "registrationDate", "markFeature", "wordMarkSpecification.verbalElement",
    "updateDate", "sectionA1PublicationDate"})
IMAGE_FORMATS = {"image/png": "png", "image/jpeg": "jpeg", "image/gif": "gif", "image/webp": "webp"}


def _enum_list(values, allowed, label):
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 45 or any(
            not isinstance(v, str) or v not in allowed for v in values):
        raise ValueError(f"Ungültiger Filter: {label}")
    return list(dict.fromkeys(values))


def _name_filter(value, label):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100:
        raise ValueError(f"Ungültiger {label}")
    return _substring(value)


def _date_filter(value, label):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{label} muss JJJJ-MM-TT sein")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Ungültiges Datum: {label}") from None
    return value


def build_advanced_query(*, suchbegriff: str = "", nizza_klassen: list[int] | None = None,
    klassenmodus: str = "ANY", registerstatus: list[str] | None = None,
    markenformen: list[str] | None = None, markenbasis: str = "ALL",
    anmelder: str = "", vertreter: str = "", angemeldet_ab: str = "",
    angemeldet_bis: str = "") -> str:
    clauses = []
    if suchbegriff:
        clauses.append(f"wordMarkSpecification.verbalElement=={_substring(suchbegriff)}")
    if markenbasis not in BASES:
        raise ValueError("Ungültige Registerbasis")
    if markenbasis != "ALL":
        clauses.append(f"markBasis=={markenbasis}")
    if klassenmodus not in ("ANY", "ALL"):
        raise ValueError("Klassenmodus muss ANY oder ALL sein")
    if nizza_klassen is not None:
        if (not isinstance(nizza_klassen, list) or len(nizza_klassen) > 45 or
            any(type(v) is not int or not 1 <= v <= 45 for v in nizza_klassen)):
            raise ValueError("Nizza-Klassen müssen Zahlen von 1 bis 45 sein")
        classes = list(dict.fromkeys(nizza_klassen))
        if len(classes) == 1:
            clauses.append(f"niceClasses=={classes[0]}")
        elif classes:
            op = "all" if klassenmodus == "ALL" else "in"
            clauses.append(f"niceClasses={op}=({','.join(map(str, classes))})")
    statuses = _enum_list(registerstatus, STATUSES, "Registerstatus")
    if len(statuses) == 1:
        clauses.append(f"status=={statuses[0]}")
    elif statuses:
        clauses.append(f"status=in=({','.join(statuses)})")
    features = _enum_list(markenformen, FEATURES, "Markenform")
    if len(features) == 1:
        clauses.append(f"markFeature=={features[0]}")
    elif features:
        clauses.append(f"markFeature=in=({','.join(features)})")
    applicant = _name_filter(anmelder, "Anmeldername")
    if applicant:
        clauses.append(f"applicants.name=={applicant}")
    representative = _name_filter(vertreter, "Vertretername")
    if representative:
        clauses.append(f"representatives.name=={representative}")
    start = _date_filter(angemeldet_ab, "angemeldet_ab")
    end = _date_filter(angemeldet_bis, "angemeldet_bis")
    if start and end and start > end:
        raise ValueError("Enddatum liegt vor dem Anfangsdatum")
    if start:
        clauses.append(f"applicationDate>={start}")
    if end:
        clauses.append(f"applicationDate<={end}")
    if not clauses:
        raise ValueError("Mindestens ein Suchfilter ist erforderlich")
    return " and ".join(clauses)


async def advanced_search(client, *, seite: int = 0, seitenumfang: int = 20,
                          sortierfeld: str = "applicationDate", sortierrichtung: str = "desc", **filters):
    if type(seite) is not int or seite < 0:
        raise ValueError("Ungültige Seite")
    if type(seitenumfang) is not int or not 10 <= seitenumfang <= 100:
        raise ValueError("Seitengröße 10 bis 100")
    if sortierfeld not in SORT_FIELDS or sortierrichtung not in ("asc", "desc"):
        raise ValueError("Ungültige Sortierung")
    query = build_advanced_query(**filters)
    async with httpx.AsyncClient(timeout=25.0) as http:
        token = await client._token(http)
        response = await http.get(f"{API_BASE_URL}/trademarks",
            params={"query": query, "page": seite, "size": seitenumfang,
                    "sort": f"{sortierfeld}:{sortierrichtung}"},
            headers=client._headers(token))
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("trademarks"), list):
        raise RuntimeError("Unerwartetes EUIPO-Suchergebnis")
    return {"recherchestand": "API-Teilrecherche durchgeführt",
        "quelle": "EUIPO Trademark Search API 1.1.0",
        "abgerufen_utc": datetime.now(timezone.utc).isoformat(),
        "query": query, "seite": data.get("page", seite),
        "seitenumfang": data.get("size", seitenumfang),
        "treffer_gesamt": data.get("totalElements"),
        "seiten_gesamt": data.get("totalPages"), "marken": data["trademarks"],
        "vollstaendigkeit": "Nur eine Ergebnisseite; Folgeseiten für vollständige Trefferliste abrufen.",
        "hinweis": "Recherchekandidaten, keine rechtliche Verwechslungsgefahrbewertung."}


async def get_trademark_image(client, application_number: str, thumbnail: bool = True):
    """Download a bounded authenticated image, not a reusable unauthenticated URL."""
    number = validate_application_number(application_number)
    if type(thumbnail) is not bool:
        raise ValueError("vorschaubild muss wahr oder falsch sein")
    suffix = "/image/thumbnail" if thumbnail else "/image"
    cap = 512_000 if thumbnail else 2_000_000
    async with httpx.AsyncClient(timeout=25.0) as http:
        token = await client._token(http)
        headers = client._headers(token)
        headers["Accept"] = "image/*"
        async with http.stream("GET", f"{API_BASE_URL}/trademarks/{number}{suffix}", headers=headers) as response:
            response.raise_for_status()
            mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if mime not in IMAGE_FORMATS:
                raise ValueError("Nicht unterstütztes Markenabbildungsformat")
            size_str = response.headers.get("Content-Length", "")
            if size_str.isdecimal() and int(size_str) > cap:
                raise ValueError("Markenabbildung ist zu groß für die MCP-Ausgabe")
            parts = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > cap:
                    raise ValueError("Markenabbildung ist zu groß für die MCP-Ausgabe")
                parts.append(chunk)
    if total == 0:
        raise ValueError("Leere Markenabbildung")
    return b"".join(parts), IMAGE_FORMATS[mime]
