# EUIPO-MCP-Server – lokaler Test (v0.4)

**Wichtig:** Dieses Repository enthält ausschließlich Quellcode. Keine echten API-Schlüssel, Mandantendaten oder Zugangstoken ablegen.

## Sicherheitsstatus

Diese Version dient nur zum **lokalen Funktionstest auf dem Hostinger-VPS**. Die Verbindung von ChatGPT zu diesem MCP-Dienst ist noch **nicht** durch OAuth abgesichert. Deshalb darf der Dienst keinesfalls öffentlich über Traefik, einen offenen Port oder eine öffentliche URL erreichbar gemacht werden.

Die Docker-Konfiguration bindet den MCP-Port ausschließlich an `127.0.0.1:8765`. Sie enthält keine Traefik-Labels und verändert die bestehende n8n-Installation nicht.

## Installation (erst nach gemeinsamer Überprüfung)

```bash
cd /opt/euipo-mcp
git clone https://github.com/UlrichBergmeier/euipo-mcp-server.git .
docker compose config
docker compose up -d --build
docker compose ps
```

**Noch keine echten EUIPO-Zugangsdaten eingeben.** Für die ersten Tests bleiben `EUIPO_CLIENT_ID` und `EUIPO_CLIENT_SECRET` leer. Erst nach Einrichtung geeigneter Dateirechte oder eines Secret-Stores werden sie serverseitig hinterlegt.

## Funktionen

- `markenvarianten_erstellen`: Wort-, Bild- und Wort-/Bildmarkenkandidaten als reine fachliche Hilfestellung.
- `alter_vergleichsmarke`: Alter einer Registeranmeldung.
- `euipo_wortmarkenrecherche`: Read-only EUIPO-API-Abfrage für Wortmarken.
- `euipo_markendetails`: Read-only Detailabfrage für eine Anmeldenummer.
- `euipo_aehnlichkeitsrecherche`: Begrenzte Kandidatensuche nach vollständigem Wortlaut und bis zu fünf zusätzlichen Suchvarianten. Berücksichtigt potenziell lebende Registerstatus und markiert unklare Statusfälle. **Keine vollständige Ähnlichkeits- oder Kollisionsrecherche.**

Die beiden EUIPO-Abfragen sind **noch nicht mit echten Produktionszugangsdaten getestet**. Registerergebnisse sind nicht mit einer abschließenden Kollisionsprüfung oder einer Eintragungsentscheidung gleichzusetzen.

## Vor dem Produktivbetrieb erforderlich

1. Separate Benutzerauthentifizierung für ChatGPT–MCP (OAuth inklusive Berechtigungsprüfung, Auth-Code + PKCE).
2. Rate-Limiting, Secret-Management, Logging-Konzept und Abwehr unberechtigter Zugriffe.
3. HTTPS/TLS über Traefik, anschließend gesonderte Konnektivitäts- und Berechtigungstests.
4. Kontrollierte Live-Abfrage der EUIPO-API, Prüfung der Antwortfelder und der tatsächlich freigegebenen Nutzung.

**Nicht** die bestehende Compose-Anwendung `root` oder deren n8n-Container verändern.

## Erweiterung v0.4 – Status- und Ähnlichkeitskandidaten
Die neue Funktion recherchiert Wordmarks über die bisherigen EUIPO-Teilstringabfragen. Sie fragt ausdrücklich **ohne Statusfilter** ab, um auch laufende Anmeldungen zu erfassen. Treffer werden nach Anmeldenummer zusammengeführt und in „potenziell lebend“, „laut Status nicht lebend“ und „Status manuell prüfen“ gruppiert.

- Maximal 3 Seiten je Suchbegriff, maximal 6 Suchbegriffe einschließlich Ausgangszeichen, 10–100 Einträge je Seite.
- Die Suche kann bei großen Treffermengen unvollständig sein; sie dokumentiert deshalb den Suchumfang und eventuelle Abfragefehler.
- Schriftbildliche technische Ähnlichkeit wird über eine einfache Zeichenfolgenmetrik sortiert, **nicht** als juristische Verwechslungsgefahr eingestuft.
- Für klangliche und begriffliche Ähnlichkeiten müssen zusätzliche Suchbegriffe fachlich gebildet und übergeben werden.
- Treffer für nationale Marken in Europa sind nicht vollständig erfasst. Rechtsstand und tatsächliches Waren-/Dienstleistungsverzeichnis gehören in eine gesonderte juristische Prüfung.

### Offlinetests

```bash
python3 -m unittest -v test_similarity.py
```

### Sicheres späteres Update auf Hostinger

Keine direkte automatische Live-Veröffentlichung: Die Änderungen liegen zunächst ausschließlich in GitHub. Nach Prüfung und Sicherung erfolgt das Update kontrolliert im lokalen Verzeichnis `/opt/euipo-mcp` (mit `git pull --ff-only`, Docker-Neubau und Statusprüfung). Der bereits laufende Container wird **nicht** durch den GitHub-Commit verändert.
