#!/usr/bin/env bash
# Run from /opt/euipo-gs-test. Builds a disposable image, never restarts
# production euipo-mcp, Traefik or n8n.
set -euo pipefail
cd /opt/euipo-gs-test
for file in euipo_gs_client_id euipo_gs_client_secret; do
  if [[ ! -s "/opt/euipo-mcp/private/$file" ]]; then
    echo "Gesicherte Zugangsdaten-Datei fehlt: $file" >&2
    exit 1
  fi
done
printf '%s\n' "Baue isoliertes Testimage (keine Produktivaenderung) ..."
docker build -t euipo-gs-live-test:preview .
printf '%s\n' "Starte isolierte EUIPO-W/D-Tests ..."
docker run --rm --network bridge --read-only --tmpfs /tmp \
  --user 10001:10001 --security-opt no-new-privileges:true --cap-drop ALL \
  -v /opt/euipo-mcp/private/euipo_gs_client_id:/run/secrets/euipo_gs_client_id:ro \
  -v /opt/euipo-mcp/private/euipo_gs_client_secret:/run/secrets/euipo_gs_client_secret:ro \
  -v /opt/euipo-gs-test/scripts/test_gs_live.py:/app/test_gs_live.py:ro \
  euipo-gs-live-test:preview python /app/test_gs_live.py
