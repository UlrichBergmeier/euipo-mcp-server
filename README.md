# EUIPO-MCP-Server – OAuth-Testversion v0.5 (nur lokal)

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

**Geheimnisse ausschließlich lokal auf dem VPS speichern.** Die nächste Entwicklungsstufe liest die API-Zugangsdaten ausschließlich aus `/run/secrets/euipo_client_id` und `/run/secrets/euipo_client_secret`. Diese werden als schreibgeschützte Datei-Mounts aus `private/` übergeben und tauchen nicht als Klartext in `docker inspect` oder `docker compose config` auf.

**Wichtige Reihenfolge für ein Update von v0.4:**

```bash
cd /opt/euipo-mcp
git pull --ff-only
bash scripts/configure_secrets.sh
docker compose config
docker compose build euipo-mcp
docker compose up -d --no-deps euipo-mcp
```

Das Skript fragt API Key und API Secret verdeckt in der Hostinger-Webkonsole ab. **Niemals Zugangsdaten in ChatGPT, GitHub, Screenshots oder normale Shell-Befehle kopieren.** Die Dateien werden mit Besitzer root, Gruppe GID 10001, Dateirechten 0640 in einem Verzeichnis mit Modus 0700 gespeichert. Docker bindet die Dateien einzeln als read-only ein. Auf dem Host kann root sie weiterhin lesen; vollständiger Schutz gegen einen kompromittierten VPS ist damit nicht möglich. Keine Secrets in Git versionieren.

Die Implementierung der offiziellen EUIPO-Endpunkte muss vor einer echten Produktivabfrage gegen die Original-API-Spezifikation abgeglichen werden. Keine Freigabe von Traefik ohne OAuth-Schutz.

## Funktionen

- `markenvarianten_erstellen`: Wort-, Bild- und Wort-/Bildmarkenkandidaten als reine fachliche Hilfestellung.
- `alter_vergleichsmarke`: Alter einer Registeranmeldung.
- `euipo_wortmarkenrecherche`: Read-only EUIPO-API-Abfrage für Wortmarken.
- `euipo_markendetails`: Read-only Detailabfrage für eine Anmeldenummer.
- `euipo_aehnlichkeitsrecherche`: Begrenzte Kandidatensuche nach vollständigem Wortlaut und bis zu fünf zusätzlichen Suchvarianten. Berücksichtigt potenziell lebende Registerstatus und markiert unklare Statusfälle. **Keine vollständige Ähnlichkeits- oder Kollisionsrecherche.**

Die EUIPO-Suche und der Detailabruf wurden am 05.11.2026 über Hostinger mit SYSTEMBETON live getestet. Die Ähnlichkeitsrecherche ist eine begrenzte Teilrecherche, keine vollständige Kollisionsprüfung oder rechtliche Eintragungsentscheidung.

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

## Auth0-OAuth-Absicherung (v0.5 – noch nicht auf Hostinger freigegeben)

Die neue Serverversion verwendet `AuthSettings` und `Auth0TokenVerifier`. Sie akzeptiert ausschließlich RS256-signierte Auth0-Zugriffstokens mit `iss` unseres EU-Tenants, `aud` der EUIPO-MCP-API, nicht abgelaufenem `exp`, vorhandenem `sub`/`azp` und `permissions: ["read:trademarks"]`. Alle Fehler verweigern den Zugriff, einschließlich fehlender Netzwerkverbindung zum JWKS-Endpunkt. Der JWT-Inhalt, das EUIPO-Secret und der Bearer-Token dürfen niemals protokolliert werden.

**Keine neue OAuth-API-Key-Datei erforderlich.** Die Auth0-Issueradresse und die API-Audience sind öffentliche Konfigurationsangaben; die bereits lokal geschützten EUIPO-Keys bleiben unverändert.

Wichtig: Auth0-Tokenprüfung und das MCP-Server-OAuth-Discovery sind nur eine **Vorbereitung**. OpenAI/ChatGPT und Auth0 müssen noch end-to-end getestet werden; auch die von Auth0 ausgegebenen Metadaten (PKCE, CIMD, Authorization Response Issuer) sind zu prüfen. Die bisherige Hostinger-Installation bleibt lokal; keine Traefik-Labels aktivieren, ehe die Negativtests erfolgreich sind.

### Kontrolliertes Upgrade vom Hostinger-VPS

1. `cd /opt/euipo-mcp && git pull --ff-only`
2. `docker compose config --quiet && docker compose build euipo-mcp`
3. Vor dem Container-Update alle Offline-Tests in einem **separaten** Testcontainer starten:

```bash
docker run --rm --network none -e AUTH0_ISSUER=https://dev-yf816x77jyish1bb.eu.auth0.com/ -e MCP_RESOURCE_URL=https://mcp.trademark-assistant.de -v /opt/euipo-mcp/test_auth.py:/app/test_auth.py:ro euipo-mcp-local-euipo-mcp python -m unittest -v test_auth
```

4. Nur nach bestandenen Tests: `docker compose up -d --no-deps euipo-mcp`
5. Geschützte lokale Endpunkte überprüfen:

```bash
curl -i -m 10 http://127.0.0.1:8765/mcp
curl -i -m 10 -H 'Authorization: Bearer invalid' http://127.0.0.1:8765/mcp
curl -i -m 10 http://127.0.0.1:8765/.well-known/oauth-protected-resource
```

Erwartung: Beide Anfragen ohne gültiges Token werden mit **401 Unauthorized** zurückgewiesen, die Metadatenabfrage liefert eine maschinenlesbare URL des Auth0-Issuers und den Scope. Der konkrete Pfad der Metadaten kann je nach MCP-SDK-Stand abweichen. Keine rückwirkende Aussage über bestehende n8n/Traefik-Konfiguration.

**Für die erste Live-OAuth-Anmeldung** muss Auth0 eine berechtigte Anwendung registrieren und einen User-Delegated Access Token mit `permissions` ausgeben. Die Auth0-E-Mail-Bestätigung und die Rollenvergabe allein reichen nicht aus.
