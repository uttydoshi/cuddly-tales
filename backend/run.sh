#!/bin/bash
# Lambda's entry point (the function's "handler"). The AWS Lambda Web Adapter
# layer runs this script, waits for /api/health to answer, then forwards each
# request to uvicorn and streams the response back.
set -euo pipefail
export PYTHONPATH="/var/task:${PYTHONPATH:-}"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" --no-access-log
