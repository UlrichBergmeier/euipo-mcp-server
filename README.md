# EUIPO-MCP-Server – lokaler Test (v0.3)

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

Die beiden EUIPO-Abfragen sind **noch nicht mit echten Produktionszugangsdaten getestet**. Registerergebnisse sind nicht mit einer abschließenden Kollisionsprüfung oder einer Eintragungsentscheidung gleichzusetzen.

## Vor dem Produktivbetrieb erforderlich

1. Separate Benutzerauthentifizierung für ChatGPT–MCP (OAuth inklusive Berechtigungsprüfung, Auth-Code + PKCE).
2. Rate-Limiting, Secret-Management, Logging-Konzept und Abwehr unberechtigter Zugriffe.
3. HTTPS/TLS über Traefik, anschließend gesonderte Konnektivitäts- und Berechtigungstests.
4. Kontrollierte Live-Abfrage der EUIPO-API, Prüfung der Antwortfelder und der tatsächlich freigegebenen Nutzung.

**Nicht** die bestehende Compose-Anwendung `root` oder deren n8n-Container verändern.
