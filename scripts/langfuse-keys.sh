#!/usr/bin/env bash
# Stores the Langfuse keys that cuddly-tales.ukdoshi.com sends its traces with. Pasted here,
# never shown or stored in code: they go straight into AWS Secrets Manager as one secret.
#
#   scripts/langfuse-keys.sh
#
# Make the keys in your Langfuse project: Settings -> API Keys -> Create new API keys.
set -euo pipefail
source "$(dirname "$0")/_secret.sh"

check_login
read -r -p "Langfuse public key (pk-lf-...): " public_key
read -r -s -p "Langfuse secret key (sk-lf-...): " secret_key; echo
read -r -p "Langfuse host [https://us.cloud.langfuse.com]: " host
host="${host:-https://us.cloud.langfuse.com}"

[[ "$public_key" == pk-lf-* ]] || { echo "That doesn't look like a Langfuse public key (they start with pk-lf-)." >&2; exit 1; }
[[ "$secret_key" == sk-lf-* ]] || { echo "That doesn't look like a Langfuse secret key (they start with sk-lf-)." >&2; exit 1; }
[[ "$host" == https://* ]] || { echo "The host should start with https://" >&2; exit 1; }

# Built as JSON by Python, reading the values from the environment rather than the command line.
value=$(PUBLIC_KEY="$public_key" SECRET_KEY="$secret_key" HOST="$host" python3 -c \
  'import json, os; print(json.dumps({"public_key": os.environ["PUBLIC_KEY"], "secret_key": os.environ["SECRET_KEY"], "host": os.environ["HOST"]}))')
store_secret cuddly-tales/langfuse-keys "Langfuse keys for cuddly-tales.ukdoshi.com tracing" "$value"
