#!/usr/bin/env bash
# Stores the Claude API key that cuddly-tales.ukdoshi.com uses. Pasted here, never
# shown or stored in code: it goes straight into AWS Secrets Manager.
#
#   scripts/claude-key.sh
#
# Use a key made just for Cuddly Tales, with its own spend limit in the Claude Console.
set -euo pipefail
source "$(dirname "$0")/_secret.sh"

check_login
read -r -s -p "Claude API key for cuddly-tales.ukdoshi.com: " key; echo
[[ "$key" == sk-ant-* ]] || { echo "That doesn't look like a Claude API key (they start with sk-ant-)." >&2; exit 1; }
store_secret cuddly-tales/claude-api-key "Claude API key for cuddly-tales.ukdoshi.com" "$key"
