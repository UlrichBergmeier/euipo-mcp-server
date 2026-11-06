# Vorbereitung EUIPO Goods and Services API 1.2.0

**Status 06.11.2026:** EUIPO-Produktabo der separaten App **W/D-Harmonisierung** steht auf **Pending approval**. Keine Live-Abfrage und keine Änderung der laufenden Hostinger-Installation bis zur Freigabe. Entwicklungszweig: `feature/euipo-goods-services`.

## Offizielle API (aus der beigefügten OpenAPI-Spezifikation)
- API-Basis: `https://api.euipo.europa.eu/goods-and-services`
- OAuth2 Client Credentials: `https://euipo.europa.eu/cas-server-webapp/oidc/accessToken`, Scope `uid`
- Header: `X-IBM-Client-Id` sowie `Authorization: Bearer <token>`
- `POST /classification-validation` -> pro Begriff `harmonized`, `conceptId`, `errors`, `warnings`
- `POST /terms-suggestion-list?maxSuggestions=20` -> vorgeschlagene HDB-Begriffe (optional `classNumber`)
- `POST /classification-translation` -> Übersetzung in unterstützte Amtssprachen (HDB-Begriffe)

Zusätzliche Endpunkte `/terms`, `/taxonomy` und `/classHeadings` sind in der Spezifikation vorhanden, in dieser Entwicklungsstufe aber **nicht implementiert**.

## Neue MCP-Funktionen
Die drei Funktionen sind ausschließlich im Entwicklungszweig hinzugefügt:
- `euipo_wd_harmonisierung(waren_dienstleistungen, sprache="de")`
- `euipo_wd_vorschlaege(begriffe, sprache="de", nizza_klasse=0, max_vorschlaege=20)`
- `euipo_wd_uebersetzung(waren_dienstleistungen, quell_sprache="de", ziel_sprachen=["en"])`

### Beispielformat
```json
[
  {"classNumber": 19, "terms": ["Beton.", "Baumaterialien aus Beton."]},
  {"classNumber": 37, "terms": ["Betonieren."]}
]
```

Ein einzelner abschließender Punkt und umgebende Leerzeichen werden **nur für die API-Abfrage** entfernt. Der Originalbegriff wird getrennt zurückgegeben. Punkte innerhalb des Begriffs bleiben erhalten; Klassenzuordnung und Duplikate werden nicht still verändert. Zeilen-/Textformatierung für eine spätere Arbeitsfassung erfolgt getrennt.

**Strikte Ergebnistreue:** Nur wenn die API-Antwort denselben bereinigten Begriff in derselben Nizza-Klasse enthält, wird ein Ergebnis als harmonisiert/nicht harmonisiert übernommen. Abweichungen erscheinen als `manuell_pruefen`. Harmonisierung ist weder eine rechtliche Eintragungsprüfung noch eine Garantie für semantische Gleichwertigkeit alternativer Begriffe.

## Getrennte Zugangsdaten
Die EUIPO-App „Markenrecherche“ und die EUIPO-App „W/D-Harmonisierung“ haben getrennte Credentials. Der schon laufende MCP-Dienst liest für Trademark Search weiter:
- `/run/secrets/euipo_client_id`
- `/run/secrets/euipo_client_secret`

Für Goods and Services kommen **nach EUIPO-Freigabe** zwei neue, ausschließlich lokal hinterlegte Dateien hinzu:
- `/run/secrets/euipo_gs_client_id`
- `/run/secrets/euipo_gs_client_secret`

Das optionale Overlay `compose.goods-services.yaml` mountet diese beiden Dateien read-only. Bis die Dateien sicher eingerichtet wurden, darf dieses Overlay **nicht** zum Start des Produktionscontainers verwendet werden. Die Daten dürfen nicht in GitHub, Screenshots, ChatGPT oder einer ungeschützten `.env` gespeichert werden.

## Offline-Prüfung vor Freigabe
```bash
python3 -m unittest -v test_goods_services.py
```
Testet mit simulierten API-Antworten, insbesondere abschließende Punkte, richtige Nizza-Klasse, fehlende Antwort-Zuordnung, Vorschläge, Übersetzungs-Schema und fehlerhafte Eingaben. Kein API-Schlüssel und keine Netzwerkverbindung erforderlich.

## Vor produktivem Rollout
1. EUIPO bestätigt die Freigabe der App „W/D-Harmonisierung“ für **Goods And Services 1.2.0**.
2. Die neuen EUIPO-Zugangsdaten separat und verdeckt auf Hostinger installieren; nur für non-root Docker-User lesbar machen.
3. Zunächst einen **isolierten** Testcontainer mit dem Entwicklungszweig verwenden und mit echten freigegebenen Zugangsdaten eine kontrollierte Abfrage durchführen.
4. API-Response-Formate anhand der Liveantwort validieren, insbesondere Zuordnung zu einzelnen Begriffen und Begriffsklassen.
5. Im persönlichen und Kanzlei-Workspace prüfen, ob die bestehenden Auth0-Berechtigungen für die W/D-Funktionen ausreichen; bei Bedarf getrennte Scope-/Rollenberechtigung entwerfen.
6. Code prüfen, Änderung kontrolliert in `main` übernehmen, Backup/Rollback vorsehen.
7. `Dockerfile` aktualisieren, Overlay-Dateien für Secrets berücksichtigen, mit bestehenden HTTPS- und Base-Compose-Dateien kombinieren. n8n und Traefik nicht ändern.
8. Bestehende EUIPO-Trademark-Suche gegen Regression testen; ChatGPT-Plugin ggf. Werkzeugliste aktualisieren oder erneut importieren. Erst danach neuen Endpunkt öffentlich über das geschützte MCP-Plugin bereitstellen.

**Nicht:** Jetzt `git pull` auf dem Hostinger-Produktivverzeichnis durchführen, Secrets offen eingeben oder Änderungen in `main` deployen.
