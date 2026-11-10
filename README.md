# EUIPO-MCP-Server – Trademark Search API 1.1.0

Geschützter Read-only-MCP-Server auf Hostinger. Auth0-OAuth, Benutzerrollen,
HTTPS via Traefik und EUIPO-Client-Credentials (nur in lokalen Secret-Dateien)
bleiben voneinander getrennt.

**Aktueller Produktivstand:** Der EUIPO-MCP-Server mit acht Werkzeugen
(einschließlich interaktiver Einzelbildanzeige) ist auf Hostinger produktiv
und mit ChatGPT-Plugin 1.0.2 nutzbar. Die Vergleichsgalerie wird im Branch
`feature/euipo-similarity-gallery` entwickelt und ist **noch nicht produktiv**.

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
| `euipo_markenabbildung` | Geschütztes Thumbnail (max. 512 KB) oder Originalbild (max. 2 MB) als MCP-Bildinhalt; ChatGPT zeigt den Inhalt ohne UI nicht zwangsläufig sichtbar an |
| `euipo_markenanzeige` | Interaktive Einzelbildanzeige als geschützte MCP App |
| `euipo_aehnlichkeitsgalerie` | **Neu, im Entwicklungszweig:** begrenzte Ähnlichkeitssuche mit sichtbaren Markenabbildungen mehrerer Vergleichsmarken, Registerstatus und Klassen |

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

## MCP-Apps-Bildansicht (in Entwicklung)

Die neue Funktion `euipo_markenanzeige(anmeldenummer)` verknüpft ihren
Werkzeugeintrag über `_meta.ui.resourceUri` mit
`ui://euipo/markenanzeige-v1.html`. Die statische UI-Ressource wird als
`text/html;profile=mcp-app` geliefert. Für ChatGPT ist zusätzlich die
kompatible Angabe `openai/outputTemplate` gesetzt.

Das UI ist in `trademark_viewer.html` implementiert und enthält alle CSS-
und JavaScript-Ressourcen selbst. Es benötigt keine offenen Netzfreigaben und
keinen Zugriff auf EUIPO-Client-Secrets im Browser. Stattdessen holt es
Vorschaubild bzw. Original über eine **vom ChatGPT-Host vermittelte,
autorisierte** `tools/call`-Anfrage an `euipo_markenabbildung`. Das Bild
wird unmittelbar als eingebettete Daten-URL im geschützten iframe gezeigt.
Die Benutzerin oder der Benutzer kann Vorschau/Original umschalten und zoomen.

**Wichtige Grenze:** Ein Host ohne MCP-Apps-Unterstützung erhält nur den
aussagekräftigen Text des Werkzeugaufrufs. Weder die Ausgabe dieses Textes
noch eine erfolgreiche Markenbild-API-Abfrage beweisen eine sichtbare
Bilddarstellung im Chat. Die finale UI-Darstellung muss nach der
Entwicklungsbereitstellung ausdrücklich in ChatGPT getestet werden.
Wird der Aufruf aus der App verweigert, zeigt das UI einen Fehler an,
statt einen Bilderfolg zu behaupten.

Die bestehenden sieben Werkzeuge, OAuth-Ressourcenkennung, Benutzerrollen,
Traefik-Routen und Secret-Mounts bleiben unverändert. Neu ist ausschließlich
ein achtes, read-only UI-Werkzeug mit passender HTML-Ressource.

## EUIPO-Ähnlichkeitsgalerie (in Entwicklung)

Das neunte MCP-Werkzeug `euipo_aehnlichkeitsgalerie(zeichen, nizza_klasse, ...)`
verwendet **unverändert** die vorhandene `euipo_similarity_search`-Logik.
Es führt pro Suchbegriff eine begrenzte Ergebnisseite ab und stellt höchstens
40 Kandidaten in der Galerie bereit. Die Darstellung erfolgt auf Seiten zu je
8 Kandidaten; maximal zwei Bilddownloads gleichzeitig und **nur** für
Markenformen ungleich `WORD`. Der zugehörige Browser lädt Abbildungen über
die bestehende geschützte MCP-Werkzeugverbindung
`euipo_markenabbildung`. Originalbilder werden erst nach einem Klick
abgerufen. Keine EUIPO-Secrets, keine externen Stylesheets, keine offenen
Bild-URLs und keine eigenen Browser-Netzwerkaufrufe.

UI-Ressource: `ui://euipo/aehnlichkeitsgalerie-v1.html`
(`text/html;profile=mcp-app`). Es werden nur übermittelte Registerdaten
angezeigt. Bei Wortmarken erscheint ein **neutraler textlicher Platzhalter**;
es wird keine grafische Gestaltung erfunden. Fehlende oder gesperrte
Abbildungen werden ausdrücklich als solche gekennzeichnet.

**Wichtige rechtliche Grenzen:** Die Galerie bildet nur die begrenzte
EUIPO-Teilrecherche ab; keine vollständige Kollisionsrecherche und keine
automatische Verwechslungsgefahrbeurteilung. Ein angezeigter Prozentwert
ist ausschließlich eine technische Zeichenfolgenähnlichkeit. Die
Nizza-Klasse ist nur ein Vorfilter; nationale Marken und rein
bildliche/klangliche/begriffliche Ähnlichkeiten werden nicht erschöpfend
ermittelt. In der Kopfzeile wird die Zahl der ermittelten und der
tatsächlich angezeigten Kandidaten offengelegt.

Die bestehenden **acht** MCP-Werkzeuge, die Auth0-Rollen und -Tokens, die
Traefik-Routen, die Docker-Compose-Konfiguration und die Secret-Dateien
bleiben unverändert. Änderungen erfolgen zunächst ausschließlich auf dem
Entwicklungszweig. Produktive Übernahme erst nach Offline-Tests,
Sicherheitstests und einer tatsächlich sichtbaren Galerie in ChatGPT.


## Klassenverzeichnisse und technische Waren-/Dienstleistungs-Vorauswahl (in Entwicklung)

Eine zusätzliche schreibfreie Funktion `euipo_klassendetails(anmeldenummer,
nizza_klasse, referenzwaren)` lädt die Klasse **erst nach dem Klick** in der
Vergleichsgalerie aus dem unveränderten EUIPO-Registerdetail-Endpunkt.
Die Klasse wird aus der EUIPO-Struktur `goodsAndServices[].description[]
{language,terms}` entnommen. Der bereits bestehende EUIPO-Client sendet
`Accept-Language: de`; vor dem Anzeigen wird geprüft, ob die Antwort
tatsächlich `language="de"` enthält.

- Deutsche Registerfassung vorhanden: tatsächliche Begriffe im Wortlaut,
  keine Ergänzung/Kürzung oder Formulierung anhand bloßer Klassenüberschriften.
- Keine deutsche Registerfassung: Original-/verfügbare Sprache mit deutlicher
  Kennzeichnung; **keine erfundene oder fälschlich amtlich genannte Übersetzung**.
  Für eine vollständige Übersetzung aus anderen Sprachen ist ein verifizierter
  EUIPO-Goods-And-Services-Übersetzungsaufruf separat zu prüfen.
- Jede Klasse hat eine eigene anklickbare Schaltfläche. Die Antwort zeigt
  vollständig die im EUIPO-Register gelieferten Positionen dieser Klasse.
- Nur wenn bei `euipo_aehnlichkeitsgalerie` zusätzlich das Feld
  `referenzwaren_dienstleistungen` angegeben wurde, erfolgt je Klasse
  die **technische** Vorauswahl einer Position anhand normalisierter
  Wort-/Zeichenfolgenähnlichkeit. Der gefundene Eintrag, der Referenzbegriff
  und der technische Prozentsatz erscheinen hervorgehoben.
- Die Vorauswahl ist **keine semantische Prüfung und keine markenrechtliche
  Waren-/Dienstleistungsähnlichkeitsbewertung**. Zweck, Verwendung,
  Vertriebswege, Wettbewerb, Komplementarität oder Herkunft werden damit
  nicht beurteilt. Die Position darf nicht ohne juristische Prüfung als
  „rechtlich ähnlichste Ware/Dienstleistung“ bezeichnet werden.
- Ohne Vergleichswaren wird ausdrücklich keine „ähnlichste“ Position
  ausgegeben. Die bloße Markenbezeichnung `BETON` wird nicht automatisch
  als beanspruchte Ware unterstellt.
- Auth0, Secrets, Markenbildwerkzeug und die bisherige Ähnlichkeitsrecherche
  bleiben unverändert; es kommt nur ein gezielter read-only Toolaufruf hinzu.
  Registertexte werden weder dauerhaft gespeichert noch an eine externe
  Übersetzungs-API gesendet.

**Beispiel zur Verwendung nach Freigabe**:
`euipo_aehnlichkeitsgalerie(zeichen="BETON", nizza_klasse=19,
referenzwaren_dienstleistungen=["Beton"])`.

Die Funktion bleibt bis zu den automatischen Tests sowie der sichtbaren
Klassenprüfung in ChatGPT ausschließlich im Entwicklungszweig.


## Risikoorientierte Vergleichsgalerie (experimentell, PR 6)

Die Galerie wurde um die folgenden Punkte ergänzt:
- Die Nizza-Klassen laden bei angezeigten Treffern automatisch eine **kompakte
  Übersicht** aller Klassen mit nur einem authentifizierten EUIPO-Detailabruf
  pro Marke. Neben der Klasse steht, soweit durch die tatsächlichen Waren-/DL-
  Begriffe belegt, z. B. `19 (identisch: Beton)` bzw.
  `19 (textlich ähnlich: Betonbau)`.
- Beim Klassenklick wird das **vollständige Registerverzeichnis** dieser Klasse
  abgerufen. Identische oder technisch textähnliche Positionen erscheinen
  **rot und fett**. Der genannte Vergleichsbegriff muss vom Benutzer stammen.
  Die algorithmische Textübereinstimmung ist **keine** juristische Feststellung
  der Waren-/Dienstleistungsähnlichkeit.
- Jeder Treffer erhält einen anklickbaren **vorläufigen Risikoindex** 0–100
  (rot ab 70, orange ab 40, sonst grün). Der Index dient ausschließlich der
  technischen **Triage** von Recherchetreffern; er ist **keine mathematisch
  oder empirisch ermittelte Verwechslungswahrscheinlichkeit**. Bei fehlenden
  Referenzwaren oder nicht auswertbarem Zeichen wird statt einer Zahl
  "nicht bewertbar" gezeigt. Solange die Registerdaten nicht geladen sind,
  bleibt der Wert besonders unsicher.
- Die Detailansicht unterscheidet schriftbildliche **technische**
  Zeichenfolgenähnlichkeit, technische W/D-Textübereinstimmung und die
  **nicht geprüfte** Kennzeichnungskraft. Klang-/Begriffsähnlichkeit,
  bildliche Bestandteile, tatsächliche W/D-Ähnlichkeit, Kennzeichnungskraft
  und Verkehrsbekanntheit werden ausdrücklich als nicht juristisch geprüft
  markiert. Ein KI-/Sachverständigen-Gutachten wird **nicht simuliert**.
- Die Treffer werden vor der Paginierung innerhalb der begrenzten EUIPO-
  Trefferliste nach dem **vorläufigen** Index absteigend sortiert.
  Nachträglich abgerufene Klassenübersichten aktualisieren den Risikoindex
  und die Reihenfolge automatisch; Treffer ohne geladenes Verzeichnis bleiben
  vorläufig bewertet. Eine vollständige Neubewertung aller Treffer verlangt
  zusätzliche, kosten-/ratelimitbewusste Registeranreicherung.
- Formel nur für die Priorisierung: Index = 100 × (0,65 × technische
  Wortähnlichkeit + 0,35 × technische W/D-Textnähe). Fehlende W/D-Daten
  werden neutral und vorläufig statt als Negativbefund behandelt. Diese
  Gewichte sind technische Heuristiken, **keine EUIPO-Formel**.
- OAuth, API-Secrets, die bestehende Suche und die 10 MCP-Werkzeuge bleiben
  unverändert. Alle Funktionen zunächst **nur auf dem Entwicklungszweig**;
  vor Deployment erst Python-/Node-Tests und Live-Darstellung prüfen.

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
python -m unittest -v test_euipo test_similarity test_auth test_extensions test_viewer test_gallery test_class_goods
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
   `test_extensions.py` und `test_viewer.py` (bei Bedarf als schreibgeschütztes Volume einhängen).
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

## Freigabekriterien für die neue UI

1. Offline-Tests plus HTML-JavaScript-Syntaxprüfung erfolgreich.
2. Testimage mit beiden `ui://`-Ressourcen und acht Werkzeugen starten.
3. Ohne/mit ungültigem Token weiterhin 401; OAuth-Metadaten 200.
4. Mit der bestehenden Auth0-Anmeldung ein neues ChatGPT-Plugin-Tool-Update
   durchführen; nötigenfalls das Plugin auf Version 1.0.2 anheben.
5. Im Chat `euipo_markenanzeige('019440746')` ausführen und **sichtbare**
   Bilddarstellung mit Vorschau, Original und Zoom bestätigen. Erst dann
   als vollständig funktionierend melden.

## Freigabekriterien der Vergleichsgalerie

1. Python-Offline-Tests und JavaScript-Bridge-Simulation grün.
2. Separate Testversion mit neun Werkzeugen und beiden `ui://`-Ressourcen.
3. Bestehende TLS/OAuth-Prüfungen unverändert erfolgreich.
4. In einem neuen Chat: mehrere tatsächliche EUIPO-Bildmarken nebeneinander sichtbar,
   Wortmarken korrekt textlich dargestellt, Original per Klick verfügbar.
5. Bei EUIPO-Fehlern / unvollständigen Trefferlisten explizite Hinweise.


## Wortlaut und Wortbildungsfamilien recherchieren
`euipo_wortmarkenrecherche` unterstützt zusätzlich `suchmodus`: `EXAKT` sucht den alleinigen Wortlaut, `WORTANFANG` die Wortbildungsfamilie, `ENTHAELT` erhält die bisherige Suche. Keine Wildcards oder RSQL-Syntax übergeben. `sortierfeld="registrationDate"` ordnet jüngere Eintragungen zuerst. Die Antwort weist Modus, Sortierung, Seite und Gesamtzahl aus. Weitere Seiten sind getrennt abzurufen. Wortgleichheit bzw. Wortanfang zusätzlich anhand des tatsächlich gelieferten Wortlauts prüfen; keine Vollständigkeit bei begrenztem Abruf behaupten. Anmelde- und Eintragungsdatum sowie tatsächliche Waren/Dienstleistungen und unbekannte Eintragungsgrundlagen getrennt würdigen.
