#!/usr/bin/env bash
# Stores the Postgres connection URL that cuddly-tales.ukdoshi.com uses (from Neon).
# Pasted here, never shown or stored in code: it goes straight into AWS Secrets Manager.
#
#   scripts/database-url.sh
#
# Use Neon's pooled connection string (its host contains "-pooler").
set -euo pipefail
source "$(dirname "$0")/_secret.sh"

check_login
read -r -s -p "Neon connection URL for cuddly-tales.ukdoshi.com: " url; echo
[[ "$url" == postgres://* || "$url" == postgresql://* ]] || {
  echo "That doesn't look like a Postgres URL (it should start with postgresql://)." >&2
  exit 1
}
[[ "$url" == *-pooler.* ]] || echo "Note: this isn't Neon's pooled URL (no '-pooler' in the host). It will work, but the pooled one suits Lambda better."
store_secret cuddly-tales/database-url "Postgres URL for cuddly-tales.ukdoshi.com" "$url"
