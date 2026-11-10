"""Read-only EUIPO Trademark Search API 1.1.0 client. Keys from protected files."""
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime, timezone
import httpx

API_BASE_URL = "https://api.euipo.europa.eu/trademark-search"
TOKEN_URL = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"
STATUSES = {"RECEIVED","UNDER_EXAMINATION","APPLICATION_PUBLISHED","REGISTRATION_PENDING","REGISTERED","WITHDRAWN","REFUSED","OPPOSITION_PENDING","APPEALED","CANCELLATION_PENDING","CANCELLED","SURRENDERED","EXPIRED","APPEALABLE","START_OF_OPPOSITION_PERIOD","ACCEPTANCE_PENDING","ACCEPTED","REMOVED_FROM_REGISTER"}
BASES = {"ALL","EU_TRADEMARK","INTERNATIONAL_TRADEMARK"}
FEATURES = {"WORD","FIGURATIVE","SHAPE_3D","COLOUR","SOUND","HOLOGRAM","OLFACTORY","POSITION","PATTERN","MOTION","MULTIMEDIA","OTHER"}
# Official OpenAPI ApplicationNumber pattern; do not remove leading zeroes.
APPLICATION_NUMBER = re.compile(r"(?:\d{9}|W\d{8}[A-Z]?)\Z")


def validate_application_number(value: str) -> str:
    if not isinstance(value, str) or not APPLICATION_NUMBER.fullmatch(value):
        raise ValueError("Ungültige Anmeldenummer: neun Ziffern oder W + acht Ziffern und optionaler Großbuchstabe")
    return value


def _safe_search_term(term: str) -> str:
    if not isinstance(term, str):
        raise ValueError("Suchbegriff muss Text sein")
    term = term.strip()
    # Restrict unsafe RSQL syntax; user input is never interpreted as a selector/operator.
    if not 1 <= len(term) <= 100 or not re.fullmatch(r"[\wÄÖÜäöüß .&+\-]+", term, flags=re.UNICODE):
        raise ValueError("Ungültiger Suchbegriff")
    return term


def _substring(term: str) -> str:
    term = _safe_search_term(term)
    return f'"*{term}*"' if " " in term else f"*{term}*"


def _word_value(term: str, mode: str = "ENTHAELT") -> str:
    """Server-owned RSQL patterns; never accept wildcard/operator syntax from callers."""
    term = _safe_search_term(term)
    if mode not in {"EXAKT", "WORTANFANG", "ENTHAELT"}:
        raise ValueError("Suchmodus muss EXAKT, WORTANFANG oder ENTHAELT sein")
    value = term if mode == "EXAKT" else term + "*" if mode == "WORTANFANG" else "*" + term + "*"
    return f'"{value}"' if " " in term else value


def build_query(term: str, nice_class: int | None, status: str | None = None,
                mark_basis: str = "ALL", mark_feature: str = "WORD",
                match_mode: str = "ENTHAELT") -> str:
    value = _word_value(term, match_mode)
    if nice_class is not None and (type(nice_class) is not int or not 1 <= nice_class <= 45):
        raise ValueError("Nizza-Klasse muss zwischen 1 und 45 liegen")
    if status is not None and status not in STATUSES:
        raise ValueError("Ungültiger Registerstatus")
    if mark_basis not in BASES:
        raise ValueError("Ungültige Registerbasis")
    if mark_feature not in FEATURES | {"ALL"}:
        raise ValueError("Ungültige Markenform")
    clauses = []
    if mark_feature != "ALL":
        clauses.append(f"markFeature=={mark_feature}")
    clauses.append(f"wordMarkSpecification.verbalElement=={value}")
    if mark_basis != "ALL":
        clauses.append(f"markBasis=={mark_basis}")
    if nice_class is not None:
        clauses.append(f"niceClasses=={nice_class}")
    if status is not None:
        clauses.append(f"status=={status}")
    return " and ".join(clauses)


class EUIPOClient:
    def __init__(self):
        try:
            self.client_id = Path("/run/secrets/euipo_client_id").read_text(encoding="utf-8").strip()
            self.client_secret = Path("/run/secrets/euipo_client_secret").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise RuntimeError("EUIPO-Zugang ist serverseitig noch nicht konfiguriert.") from None
        if not self.client_id or not self.client_secret:
            raise RuntimeError("EUIPO-Zugang ist serverseitig noch nicht konfiguriert.")

    async def _token(self, client: httpx.AsyncClient) -> str:
        response = await client.post(TOKEN_URL, data={"client_id": self.client_id,
            "client_secret": self.client_secret, "grant_type": "client_credentials", "scope": "uid"})
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("Kein EUIPO-Zugriffstoken")
        return token

    def _headers(self, token: str) -> dict[str, str]:
        return {"X-IBM-Client-Id": self.client_id, "Authorization": f"Bearer {token}",
                "Accept": "application/json", "Accept-Language": "de"}

    async def search_wordmarks(self, term, nice_class, status=None, page=0, size=20,
                               mark_basis="ALL", mark_feature="WORD", match_mode="ENTHAELT",
                               sort_field="applicationDate"):
        if type(page) is not int or page < 0:
            raise ValueError("Ungültige Seite")
        if type(size) is not int or not 10 <= size <= 100:
            raise ValueError("Seitengröße 10 bis 100")
        if sort_field not in {"applicationDate", "registrationDate"}:
            raise ValueError("Sortierfeld muss applicationDate oder registrationDate sein")
        query = build_query(term, nice_class, status, mark_basis, mark_feature, match_mode)
        async with httpx.AsyncClient(timeout=25.0) as client:
            token = await self._token(client)
            response = await client.get(f"{API_BASE_URL}/trademarks",
                params={"query": query, "page": page, "size": size, "sort": f"{sort_field}:desc"},
                headers=self._headers(token))
            response.raise_for_status()
            data = response.json()
        return {"recherchestand": "live durchgeführt", "quelle": "EUIPO Trademark Search API 1.1.0",
            "abgerufen_utc": datetime.now(timezone.utc).isoformat(), "query": query,
            "suchmodus": match_mode, "sortierfeld": sort_field,
            "seite": data.get("page", page), "seitenumfang": data.get("size", size),
            "treffer_gesamt": data.get("totalElements"), "seiten_gesamt": data.get("totalPages"),
            "marken": data.get("trademarks", []),
            "hinweis": "Nizza-Klassen sind nur Vorfilter; Waren/DL und Registerstatus gesondert prüfen."}

    async def search_verbal_marks(self, term, nice_class, status=None, page=0, size=20,
                                  mark_basis="ALL"):
        """Search all mark types with a verbalElement, including figurative marks."""
        return await self.search_wordmarks(term, nice_class, status, page, size, mark_basis,
                                           mark_feature="ALL")

    async def trademark_detail(self, application_number):
        number = validate_application_number(application_number)
        async with httpx.AsyncClient(timeout=25.0) as client:
            token = await self._token(client)
            response = await client.get(f"{API_BASE_URL}/trademarks/{number}", headers=self._headers(token))
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Unerwartetes EUIPO-Antwortformat")
        # Return the full register record (including priorities, applicants,
        # oppositions, cancellations and appeals) without silently dropping fields.
        return {**data, "recherchestand": "live durchgeführt",
            "quelle": "EUIPO Trademark Search API 1.1.0",
            "abgerufen_utc": datetime.now(timezone.utc).isoformat(),
            "hinweis": "Status und Verfahren rechtlich prüfen; Registerdaten sind keine Kollisionsentscheidung."}
