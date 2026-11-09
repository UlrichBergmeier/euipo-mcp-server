"""EUIPO register goods/services by Nice class with auditable lexical shortlisting.

Never mistake the closest character string for a legal goods/services similarity
assessment. Only extract genuine register terms, preserve language metadata,
and clearly indicate when the German register version is absent.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any
from euipo import validate_application_number


def validate_reference_terms(values: list[str] | None) -> list[str]:
    if values is None:
        return []
    if (
        not isinstance(values, list)
        or len(values) > 15
        or any(not isinstance(x, str) or not 1 <= len(x.strip()) <= 180 for x in values)
    ):
        raise ValueError("Maximal 15 Vergleichswaren/-dienstleistungen mit je 1–180 Zeichen")
    # Preserve source wording; no silent punctuation or terminology changes.
    return list(dict.fromkeys(x.strip() for x in values))


def _norm(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _similarity(left: str, right: str) -> float:
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    tokens_a, tokens_b = set(a.split()), set(b.split())
    overlap = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
    ratio = SequenceMatcher(None, a, b).ratio()
    if a in b or b in a:
        return round(max(0.8, ratio), 3)
    return round(0.65 * ratio + 0.35 * overlap, 3)


def _language_entries(cls: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    descriptions = cls.get("description")
    if not isinstance(descriptions, list):
        return result
    for item in descriptions:
        if not isinstance(item, dict):
            continue
        lang = item.get("language")
        terms = item.get("terms")
        if not isinstance(lang, str) or not isinstance(terms, list):
            continue
        lang = lang.lower().split("-")[0]
        if not re.fullmatch(r"[a-z]{2}", lang):
            continue
        clean = [t for t in terms if isinstance(t, str) and t.strip()]
        if clean:
            result.setdefault(lang, []).extend(clean)
    return {lang: list(dict.fromkeys(terms)) for lang, terms in result.items()}


def parse_class_goods(
    detail: dict[str, Any],
    class_number: int,
    reference_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Keep the actual, complete class wording returned by the EUIPO API."""
    if type(class_number) is not int or not 1 <= class_number <= 45:
        raise ValueError("Nizza-Klasse muss zwischen 1 und 45 liegen")
    refs = validate_reference_terms(reference_terms)
    if not isinstance(detail, dict) or not isinstance(detail.get("goodsAndServices"), list):
        raise RuntimeError("EUIPO-Register enthält kein auswertbares Waren-/Dienstleistungsverzeichnis")
    number = validate_application_number(detail.get("applicationNumber"))
    groups = [
        x for x in detail["goodsAndServices"]
        if isinstance(x, dict) and x.get("classNumber") == class_number
    ]
    if not groups:
        return {
            "anmeldenummer": number, "nizza_klasse": class_number,
            "begriffe": [], "sprache": None, "deutsche_registerfassung": False,
            "hinweis": "Für diese Klasse wurde im abgerufenen Registerdatensatz kein Verzeichnis geliefert.",
            "vergleichsbegriffe": refs, "technisch_naechster_begriff": None,
            "passende_positionen": [],
            "rangfolge": "Keine juristische Waren-/Dienstleistungsähnlichkeitsbewertung.",
        }
    merged: dict[str, list[str]] = {}
    for cls in groups:
        for lang, terms in _language_entries(cls).items():
            merged.setdefault(lang, []).extend(terms)
    merged = {k: list(dict.fromkeys(v)) for k, v in merged.items()}
    first = str(detail.get("applicationLanguage") or "").lower().split("-")[0]
    chosen = "de" if merged.get("de") else first if merged.get(first) else next(iter(merged), None)
    terms = merged.get(chosen, []) if chosen else []
    german = chosen == "de"
    note = (
        "Deutsche Fassung aus dem EUIPO-Register."
        if german else
        "Keine deutsche Registerfassung in der EUIPO-Antwort vorhanden; "
        "unveränderte Registerbegriffe in Original-/verfügbarer Sprache. "
        "Keine automatische Übersetzung."
    )
    # Identify exact matches and high lexical candidates only. These are
    # text-comparison flags, not findings of legal goods/service similarity.
    candidates = []
    if refs and terms:
        for term in terms:
            if not isinstance(term, str):
                continue
            scored = [(_similarity(term, reference), reference) for reference in refs]
            score, reference = max(scored, key=lambda item: item[0])
            if score >= 0.72:
                candidates.append({
                    "wortlaut": term,
                    "verglichen_mit": reference,
                    "technische_textaehnlichkeit": score,
                    "art": "identisch" if _norm(term) == _norm(reference) else "textlich_aehnlich",
                })
    # No fake ranking if reference goods/services were not specified.
    best = None
    if refs and terms:
        matches = [
            (score, term, reference)
            for term in terms
            for reference in refs
            for score in [_similarity(term, reference)]
        ]
        score, term, reference = max(matches, key=lambda x: x[0])
        best = {
            "wortlaut": term, "verglichen_mit": reference,
            "technische_textaehnlichkeit": score,
            "bewertungsgrundlage": (
                "Rein technische Zeichenfolgen-/Wortüberlappung; keine semantische "
                "oder markenrechtliche Waren-/Dienstleistungsähnlichkeitsprüfung."
            ),
        }
    return {
        "anmeldenummer": number,
        "nizza_klasse": class_number,
        "begriffe": terms,
        "sprache": chosen,
        "deutsche_registerfassung": german,
        "hinweis": note,
        "vergleichsbegriffe": refs,
        "technisch_naechster_begriff": best,
        "passende_positionen": candidates,
        "rangfolge": "Technische Vorauswahl, nicht die rechtlich ähnlichste Ware oder Dienstleistung.",
        "quelle": "EUIPO Trademark Search API 1.1.0 – Registerdetail",
    }
