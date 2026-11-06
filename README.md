# EUIPO-MCP-Server – Trademark Search API 1.1.0

Geschützter Read-only-MCP-Server auf Hostinger. Auth0-OAuth, Benutzerrollen,
HTTPS via Traefik und EUIPO-Client-Credentials (nur in lokalen Secret-Dateien)
bleiben voneinander getrennt.

**Aktueller Produktivstand:** Die bisherige ChatGPT-/Auth0-Anmeldung und
EUIPO-Verbindung wurden erfolgreich eingerichtet. Der neue Funktionsumfang
liegt zunächst nur auf dem Entwicklungszweig
`feature/euipo-trademark-search-1-1-extensions` – **noch nicht auf Hostinger
bereitgestellt**.

## Schnittstellen und Werkzeuge

Die Implementierung basiert auf der hochgeladenen Original-OpenAPI-Datei
`trademark-search_1.1.0.json` (OpenAPI 3.0). Der API-Client ruft ausschließlich
den offiziellen EUIPO-Server unter
`https://api.euipo.europa.eu/trademark-search` auf.

| MCP-Werkzeug | Zweck |
| --- | --- |
| `markenvarianten_erstellen` | Zeichen-/Anmeldestrategie; keine Registerabfrage |
| `alter_vergleichsmarke` | Alter einer Vergleichsanmeldung |
| `euipo_wortmarkenrecherche` | Wortmarken; **alle Registerstatus als Standard**, ausdrücklich `REGISTERED` nur bei Wunsch |
| `euipo_markendetails` | **Vollständiger** Registerdatensatz inkl. Prioritäten, Parteien, Widersprüchen, Löschungen und Beschwerden (soweit vorhanden) |
| `euipo_aehnlichkeitsrecherche` | Begrenzte Kandidatensuche nach indexiertem verbalElement für Wortmarken **und** andere Markenformen, auch `FIGURATIVE` |
| `euipo_erweiterte_markenrecherche` | **Neu:** Wortbestandteile, Nizza-Klassen ANY/ALL, Statuslisten, Markenformen, Markenbasis, Anmelder, Vertreter, Anmeldedaten und Sortierung |
| `euipo_markenabbildung` | **Neu:** Geschütztes Thumbnail (max. 512 KB) oder Originalbild (max. 2 MB) als MCP-Bildinhalt |

**Nicht integriert:** Sound, Video und 3D-Modelle sind als nachrangige
Erweiterungsmöglichkeit vorgesehen; sie dürfen nicht stillschweigend als
verfügbar dargestellt werden.

Die erweiterte Recherche liefert nur eine Ergebnisseite pro Aufruf.
Die Ähnlichkeitssuche ist eine begrenzte **Kandidatenrecherche**, keine
vollständige Kollisionsrecherche. Klangliche, begriffliche oder rein bildliche
Ähnlichkeiten werden nicht vollautomatisch erkannt. Nizza-Klassen sind nur
Vorfilter; Waren-/Dienstleistungsverzeichnisse müssen einzeln geprüft werden.
Unbekannte oder streitige Registerstatus bleiben manuell zu klären.

Internationale Anmeldenummern: `W` + acht Ziffern + optionaler Großbuchstabe
(z. B. `W00843427A`), EU-Anmeldenummern: exakt neun Ziffern
(z. B. `019430321`).

## Sicherheit und Deployment

- Basis-`compose.yaml` veröffentlicht nur `127.0.0.1:8765`, die zusätzliche
  Datei `compose.https.yaml` legt die Traefik-HTTPS-Route an.
- Auth0-Token werden auf RS256-Signatur, Issuer, Audience, Ablauf und
  `read:trademarks` geprüft. Beide bestehenden Workspace-Verbindungen
  verwenden denselben MCP-Endpunkt
  `https://mcp.trademark-assistant.de/mcp`.
- EUIPO-Client-ID und Client-Secret ausschließlich über die bestehenden,
  schreibgeschützten Bind-Mounts in `/run/secrets/`. Keine Schlüssel in Git,
  Kommandozeilen oder Screenshots.
- Bildabruf erfolgt serverseitig über EUIPO-Authentifizierung. Es werden keine
  Token-URLs an ChatGPT zurückgegeben; Größen- und Medienformatgrenzen greifen.
- Unverändert bleibt die n8n-/Traefik-Installation. Nach einem GitHub-Commit
  erfolgt **kein automatisches Deployment**.

## Offline-Tests ohne EUIPO-Zugangsdaten

```bash
python -m unittest -v test_euipo test_similarity test_auth test_extensions
```

Tests für Auth0 benötigen die Abhängigkeiten aus `requirements.txt`;
die Tokenprüfungen verwenden einen lokalen Testschlüssel und kein Netzwerk.
Die Endpunkt-Mocks testen Filter-Sicherheit, Suchparameter, IR-Nummern,
Bildabruf und Größenbegrenzung.

## Kontrollierter Freigabe- und Aktualisierungsablauf

1. Branch auf GitHub reviewen und erst nach Tests nach `main` übernehmen.
2. Auf Hostinger im Verzeichnis `/opt/euipo-mcp` nach dem Merge
   `git pull --ff-only` ausführen. Bestehende Secret-Dateien nicht ändern.
3. Mit den beiden Compose-Dateien `config --quiet` und
   `build euipo-mcp` ausführen; den laufenden Container dabei noch nicht
   ersetzen.
4. Offline-Tests mit einem separaten Docker-Prozess starten, einschließlich
   `test_extensions.py` (bei Bedarf als schreibgeschütztes Volume einhängen).
5. Erst nach bestandenen Tests:
   `docker compose -f compose.yaml -f compose.https.yaml up -d --no-deps euipo-mcp`.
6. HTTPS/OAuth-Negativtests (`401` ohne/mit ungültigem Token;
   `200` für `/.well-known/oauth-protected-resource/mcp`),
   **einen autorisierten ChatGPT-Aufruf** und reale EUIPO-Abfragen
   einschließlich Bild- bzw. Detailabruf testen.
7. Nach erfolgreichem Test die neuen MCP-Werkzeuge im ChatGPT-Plugin
   aktualisieren/synchronisieren (falls nicht automatisch erkannt).

**Rollback:** Zur vorherigen geprüften Git-Version zurückkehren und
das frühere Docker-Image mit denselben Compose-Dateien erneut starten.
Niemals bestehende Secret-Dateien überschreiben.

Die EUIPO-Registerdaten sind keine rechtliche Bewertung oder verbindliche
Eintragungsentscheidung. Für Mandanten ist eine abschließende rechtliche
Zeichen- und Warenähnlichkeitsprüfung erforderlich.
