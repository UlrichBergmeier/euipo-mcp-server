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

def build_query(term: str, nice_class: int | None, status: str | None = "REGISTERED", mark_basis: str = "ALL") -> str:
    if not isinstance(term,str):
        raise ValueError("Suchbegriff muss Text sein")
    term=term.strip()
    if not 1 <= len(term) <= 100 or not re.fullmatch(r"[\wÄÖÜäöüß\- .]+",term, flags=re.UNICODE):
        raise ValueError("Ungültiger Suchbegriff")
    if nice_class is not None and (type(nice_class) is not int or not 1 <= nice_class <= 45):
        raise ValueError("Nizza-Klasse muss zwischen 1 und 45 liegen")
    if status is not None and status not in STATUSES:
        raise ValueError("Ungültiger Registerstatus")
    if mark_basis not in BASES:
        raise ValueError("Ungültige Registerbasis")
    value = f'"*{term}*"' if " " in term else f"*{term}*"
    clauses=["markFeature==WORD", f"wordMarkSpecification.verbalElement=={value}"]
    if mark_basis!="ALL": clauses.append(f"markBasis=={mark_basis}")
    if nice_class is not None: clauses.append(f"niceClasses=={nice_class}")
    if status: clauses.append(f"status=={status}")
    return ";".join(clauses)

class EUIPOClient:
    def __init__(self):
        try:
            self.client_id=Path("/run/secrets/euipo_client_id").read_text(encoding="utf-8").strip()
            self.client_secret=Path("/run/secrets/euipo_client_secret").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise RuntimeError("EUIPO-Zugang ist serverseitig noch nicht konfiguriert.") from None
        if not self.client_id or not self.client_secret:
            raise RuntimeError("EUIPO-Zugang ist serverseitig noch nicht konfiguriert.")

    async def _token(self, client: httpx.AsyncClient) -> str:
        response=await client.post(TOKEN_URL,data={"grant_type":"client_credentials","scope":"uid"},auth=(self.client_id,self.client_secret))
        response.raise_for_status()
        token=response.json().get("access_token")
        if not token: raise RuntimeError("Kein EUIPO-Zugriffstoken")
        return token

    def _headers(self,token):
        return {"X-IBM-Client-Id":self.client_id,"Authorization":f"Bearer {token}","Accept":"application/json","Accept-Language":"de"}

    async def search_wordmarks(self,term,nice_class,status="REGISTERED",page=0,size=20,mark_basis="ALL"):
        if type(page) is not int or page<0: raise ValueError("Ungültige Seite")
        if type(size) is not int or not 10<=size<=100: raise ValueError("Seitengröße 10 bis 100")
        query=build_query(term,nice_class,status,mark_basis)
        async with httpx.AsyncClient(timeout=25.0) as client:
            token=await self._token(client)
            response=await client.get(f"{API_BASE_URL}/trademarks",params={"query":query,"page":page,"size":size,"sort":"registrationDate:desc"},headers=self._headers(token))
            response.raise_for_status()
            data=response.json()
        return {"recherchestand":"live durchgefuehrt","quelle":"EUIPO Trademark Search API 1.1.0","abgerufen_utc":datetime.now(timezone.utc).isoformat(),"query":query,"seite":data.get("page",page),"seitenumfang":data.get("size",size),"treffer_gesamt":data.get("totalElements"),"seiten_gesamt":data.get("totalPages"),"marken":data.get("trademarks",[]),"hinweis":"Klassen sind nur Vorfilter. Waren/DL und zeitliche Aussagekraft gesondert prüfen."}

    async def trademark_detail(self,application_number):
        if not isinstance(application_number,str) or not re.fullmatch(r"[0-9]{1,16}",application_number):
            raise ValueError("Ungültige Anmeldenummer")
        async with httpx.AsyncClient(timeout=25.0) as client:
            token=await self._token(client)
            response=await client.get(f"{API_BASE_URL}/trademarks/{application_number}",headers=self._headers(token))
            response.raise_for_status()
            data=response.json()
        fields=("applicationNumber","markFeature","markBasis","wordMarkSpecification","applicationDate","registrationDate","status","goodsAndServices","tradeDistinctivenessIndicator","decisions")
        return {"recherchestand":"live durchgefuehrt","quelle":"EUIPO Trademark Search API 1.1.0","abgerufen_utc":datetime.now(timezone.utc).isoformat(),**{k:data.get(k) for k in fields},"hinweis":"Entscheidungsgründe und Waren/DL gesondert verifizieren."}
