#!/usr/bin/env bash
# Run on Hostinger VPS, never in GitHub Actions or on another machine.
set -euo pipefail
if [[ "${EUID}" != "0" ]]; then
  echo "Dieses Skript muss auf dem eigenen VPS mit Root-Rechten laufen." >&2
  exit 1
fi
if [[ ! -t 0 ]]; then
  echo "Interaktives Terminal erforderlich. Keine Secrets per Kommandozeile übergeben." >&2
  exit 1
fi
cd "$(dirname "$0")/.."
install -d -m 0700 -o root -g root private
read -r -s -p "EUIPO API Key (Eingabe bleibt unsichtbar): " euipo_key
printf '\n'
read -r -s -p "EUIPO API Secret (Eingabe bleibt unsichtbar): " euipo_secret
printf '\n'
if [[ -z "${euipo_key}" || -z "${euipo_secret}" ]]; then
  unset euipo_key euipo_secret
  echo "Abbruch: Beide Werte muessen gefuellt sein." >&2
  exit 1
fi
umask 077
printf '%s' "${euipo_key}" > private/euipo_client_id
printf '%s' "${euipo_secret}" > private/euipo_client_secret
unset euipo_key euipo_secret
chown root:10001 private/euipo_client_id private/euipo_client_secret
chmod 0640 private/euipo_client_id private/euipo_client_secret
echo "Gespeichert. Geheimwerte werden nicht angezeigt."
echo "Pruefung ohne Offenlegung: ls -l private/ (zeigt nur Dateirechte)."
