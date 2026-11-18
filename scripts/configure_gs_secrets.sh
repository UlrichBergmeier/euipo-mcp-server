#!/usr/bin/env bash
# Store credentials for the separately approved EUIPO Goods and Services app.
# This script is intended to run interactively as root on the Hostinger VPS.
# Nothing is sent to GitHub or printed to the terminal.
set -euo pipefail
if [[ "$EUID" -ne 0 || ! -t 0 ]]; then
  echo "Bitte interaktiv als root auf dem eigenen VPS ausfuehren." >&2
  exit 1
fi
cd /opt/euipo-mcp
install -d -m 0700 -o root -g root private

printf '%s\n' "EUIPO-App: W/D-Harmonisierung (Goods and Services 1.2.0)"
read -r -s -p "API Key (Eingabe unsichtbar): " gs_key
printf '\n'
read -r -s -p "API Secret (Eingabe unsichtbar): " gs_secret
printf '\n'
if [[ -z "$gs_key" || -z "$gs_secret" ]]; then
  unset gs_key gs_secret
  echo "Abbruch: Beide Werte muessen angegeben werden." >&2
  exit 1
fi
umask 077
# Temp files remain private until both values have been provided.
key_tmp="$(mktemp private/.gs_key.XXXXXXXX)"
secret_tmp="$(mktemp private/.gs_secret.XXXXXXXX)"
trap 'rm -f "$key_tmp" "$secret_tmp"; unset gs_key gs_secret' EXIT
printf '%s' "$gs_key" > "$key_tmp"
printf '%s' "$gs_secret" > "$secret_tmp"
unset gs_key gs_secret
chown root:10001 "$key_tmp" "$secret_tmp"
chmod 0640 "$key_tmp" "$secret_tmp"
mv -f "$key_tmp" private/euipo_gs_client_id
mv -f "$secret_tmp" private/euipo_gs_client_secret
trap - EXIT
echo "Beide Goods-and-Services-Zugangsdaten lokal gespeichert."
ls -l private/euipo_gs_client_id private/euipo_gs_client_secret
