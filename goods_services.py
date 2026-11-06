"""Read-only EUIPO Goods and Services API 1.2.0, separate EUIPO application.

The inputs are grouped by Nice class. Normalisation removes only surrounding
whitespace and final full stops, never internal punctuation or word components.
Live API validation is authoritative; our code never invents HDB matches.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

GS_URL = "https://api.euipo.europa.eu/goods-and-services"
TOKEN_URL = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"
LANGUAGES = frozenset(
    "bg cs da de el en es et fi fr hr hu it lt lv mt nl pl pt ro sk sl sv".split()
)


def _language(value: str) -> str:
    if not isinstance(value, str) or value not in LANGUAGES:
        raise ValueError("Ungültiger Sprachcode (z. B. de, en, fr)")
    return value


def _nice_class(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 45:
        raise ValueError("Nizza-Klasse muss zwischen 1 und 45 liegen")
    return value


def _clean_term(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("W/D-Begriffe müssen Text sein")
    # Only remove an obvious final list-item full stop, not abbreviations
    # or punctuation *within* the term. The original is retained in output.
    text = value.strip()
    text = re.sub(r"\\.\\s*$", "", text).rstrip()
    if not text or len(text) > 500:
        raise ValueError("Leerer oder zu langer W/D-Begriff (max. 500 Zeichen)")
    return text


def _entries(entries: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    if not isinstance(entries, list) or not 1 <= len(entries) <= 45:
        raise ValueError("1 bis 45 Klasseneinträge erforderlich")
    payload, originals = [], []
    seen_classes = set()
    count = 0
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Eintrag benötigt classNumber und terms")
        cls = _nice_class(item.get("classNumber"))
        if cls in seen_classes:
            raise ValueError("Eine Nizza-Klasse darf nur einmal vorkommen")
        seen_classes.add(cls)
        terms = item.get("terms")
        if not isinstance(terms, list) or not terms:
            raise ValueError("terms muss eine nichtleere Liste sein")
        count += len(terms)
        if count > 200:
            raise ValueError("Maximal 200 Begriffe je Anfrage")
        cleaned = [_clean_term(t) for t in terms]
        payload.append({"classNumber": cls, "terms": cleaned})
        originals.append({"classNumber": cls, "terms": list(terms)})
    return payload, originals


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class GoodsServicesClient:
    """API keys never leave the server; no URL or headers can be user-supplied."""

    def __init__(self) -> None:
        try:
            self.client_id = Path("/run/secrets/euipo_gs_client_id").read_text(
                encoding="utf-8"
            ).strip()
            self.client_secret = Path("/run/secrets/euipo_gs_client_secret").read_text(
                encoding="utf-8"
            ).strip()
        except (OSError, UnicodeError):
            raise RuntimeError(
                "EUIPO Goods and Services ist noch nicht freigeschaltet/konfiguriert"
            ) from None
        if not self.client_id or not self.client_secret:
            raise RuntimeError("EUIPO Goods and Services Zugangsdaten fehlen")

    async def _call(self, method: str, path: str, *, payload: dict,
                    params: dict | None = None) -> dict:
        if method != "POST" or path not in {
            "/classification-validation",
            "/terms-suggestion-list",
            "/classification-translation",
        }:
            raise ValueError("Nicht erlaubter EUIPO-Endpunkt")
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth = await client.post(
                TOKEN_URL, data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "uid",
                }
            )
            auth.raise_for_status()
            token = auth.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise RuntimeError("Kein EUIPO-Zugriffstoken erhalten")
            response = await client.post(
                GS_URL + path, json=payload, params=params,
                headers={
                    "X-IBM-Client-Id": self.client_id,
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json",
                }
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise RuntimeError("Unerwartetes Antwortformat der EUIPO-API")
            return result

    async def validate(self, payload: dict) -> dict:
        return await self._call("POST", "/classification-validation", payload=payload)

    async def suggest(self, payload: dict, maximum: int) -> dict:
        return await self._call("POST", "/terms-suggestion-list",
                                payload=payload, params={"maxSuggestions": maximum})

    async def translate(self, payload: dict) -> dict:
        return await self._call("POST", "/classification-translation", payload=payload)


async def harmonize(
    waren_dienstleistungen: list[dict],
    sprache: str = "de",
    *,
    client: Any = None,
) -> dict:
    language = _language(sprache)
    payload, original = _entries(waren_dienstleistungen)
    api = client if client is not None else GoodsServicesClient()
    response = await api.validate({
        "sourceLanguage": language, "goodsAndServices": payload
    })
    groups = response.get("goodsAndServices")
    if not isinstance(groups, list):
        raise RuntimeError("EUIPO-Validierungsantwort enthält keine Klasseneinträge")

    results = []
    for index, wanted in enumerate(payload):
        orig = original[index]
        candidate = groups[index] if index < len(groups) else None
        correct_class = (
            isinstance(candidate, dict) and
            candidate.get("classNumber") == wanted["classNumber"]
        )
        server_terms = candidate.get("terms") if correct_class else None
        rows = []
        for j, clean in enumerate(wanted["terms"]):
            incoming = (
                server_terms[j] if isinstance(server_terms, list)
                and j < len(server_terms) and isinstance(server_terms[j], dict)
                else None
            )
            # Never attribute another term's decision to the original input.
            verified = (
                incoming is not None and incoming.get("text") == clean
                and type(incoming.get("harmonized")) is bool
            )
            rows.append({
                "original": orig["terms"][j],
                "abgefragt": clean,
                "abschlusspunkt_entfernt": orig["terms"][j].strip() != clean,
                "status": (
                    "harmonisiert" if incoming["harmonized"]
                    else "nicht_harmonisiert"
                ) if verified else "manuell_pruefen",
                "conceptId": incoming.get("conceptId") if verified else None,
                "errors": incoming.get("errors", []) if verified else [],
                "warnings": incoming.get("warnings", []) if verified else [],
                "hinweis": None if verified else (
                    "Antwort lässt sich dem Begriff nicht sicher zuordnen"
                ),
            })
        results.append({"classNumber": wanted["classNumber"], "terms": rows})
    return {
        "quelle": "EUIPO Goods and Services API 1.2.0",
        "abgerufen_utc": _utc(),
        "recherchestand": "live validiert",
        "sprache": language,
        "goodsAndServices": results,
        "hinweis": (
            "Harmonisierter HDB-Begriff ist keine Garantie der markenrechtlichen "
            "Zulässigkeit oder des Schutzumfangs. Originaltext bleibt erhalten."
        ),
    }


async def suggestions(
    begriffe: list[str],
    sprache: str = "de",
    nizza_klasse: int = 0,
    max_vorschlaege: int = 20,
    *,
    client: Any = None,
) -> dict:
    language = _language(sprache)
    if not isinstance(begriffe, list) or not 1 <= len(begriffe) <= 50:
        raise ValueError("1 bis 50 Suchbegriffe angeben")
    cleaned = [_clean_term(term) for term in begriffe]
    if type(max_vorschlaege) is not int or not 1 <= max_vorschlaege <= 200:
        raise ValueError("max_vorschlaege muss zwischen 1 und 200 liegen")
    if type(nizza_klasse) is not int or not 0 <= nizza_klasse <= 45:
        raise ValueError("Nizza-Klasse: 0 oder 1 bis 45")
    payload: dict[str, Any] = {"language": language, "texts": cleaned}
    if nizza_klasse:
        payload["classNumber"] = nizza_klasse
    api = client if client is not None else GoodsServicesClient()
    raw = await api.suggest(payload, max_vorschlaege)
    if not isinstance(raw.get("suggestions"), list):
        raise RuntimeError("EUIPO-Vorschlagsantwort unerwartet")
    return {
        "quelle": "EUIPO Goods and Services API 1.2.0",
        "abgerufen_utc": _utc(),
        "sprache": language,
        "klasse": nizza_klasse or None,
        "normalisierte_suchbegriffe": [
            {"original": a, "abgefragt": b} for a, b in zip(begriffe, cleaned)
        ],
        "vorschlaege": raw["suggestions"],
        "hinweis": "Vorschläge müssen fachlich auf passende Waren/DL geprüft werden.",
    }


async def translations(
    waren_dienstleistungen: list[dict],
    quell_sprache: str,
    ziel_sprachen: list[str],
    *,
    client: Any = None,
) -> dict:
    source = _language(quell_sprache)
    if not isinstance(ziel_sprachen, list) or not 1 <= len(ziel_sprachen) <= 10:
        raise ValueError("1 bis 10 Zielsprachen erforderlich")
    targets = [_language(lang) for lang in ziel_sprachen]
    if len(set(targets)) != len(targets) or source in targets:
        raise ValueError("Zielsprachen müssen eindeutig und von Quelle verschieden sein")
    payload, original = _entries(waren_dienstleistungen)
    api = client if client is not None else GoodsServicesClient()
    raw = await api.translate({
        "sourceLanguage": source,
        "languagesToTranslate": targets,
        "goodsAndServices": payload,
    })
    if not isinstance(raw.get("translations"), dict):
        raise RuntimeError("EUIPO-Übersetzungsantwort unerwartet")
    return {
        "quelle": "EUIPO Goods and Services API 1.2.0",
        "abgerufen_utc": _utc(),
        "quell_sprache": source,
        "ziel_sprachen": targets,
        "original": original,
        "uebersetzungen": raw["translations"],
        "hinweis": (
            "API übersetzt HDB-Begriffe; nicht harmonisierte Begriffe vorher "
            "validieren und ggf. geeignete HDB-Alternativen auswählen."
        ),
    }
