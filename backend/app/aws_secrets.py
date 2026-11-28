"""Secrets from AWS Secrets Manager, used when the app runs on Lambda.

Each `*_SECRET` env var holds a secret's ARN or name. Locally none are set, so
nothing here runs and the app uses .env as before.
"""

import json
import logging
import os
from functools import cache

logger = logging.getLogger(__name__)

# Secret-holding env var -> the plain env var the app (or LiteLLM) reads.
SECRET_ENV_VARS = {
    "CLAUDE_API_KEY_SECRET": "ANTHROPIC_API_KEY",
    "DATABASE_URL_SECRET": "DATABASE_URL",
}


# Optional secrets holding several values as JSON: secret-holding env var -> {JSON key: env var}.
# If the secret doesn't exist yet, the app starts without it (Langfuse: tracing stays off).
OPTIONAL_JSON_SECRETS = {
    "LANGFUSE_KEYS_SECRET": {
        "public_key": "LANGFUSE_PUBLIC_KEY",
        "secret_key": "LANGFUSE_SECRET_KEY",
        "host": "LANGFUSE_HOST",
    },
}


@cache
def read_secret(secret_id: str) -> str:
    """A secret's value, fetched once per Lambda start."""
    import boto3  # provided by the Lambda runtime; not needed locally

    return boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)["SecretString"]


def load_into_env() -> None:
    """Copy secrets into the env vars the app reads, unless those are already set."""
    for secret_var, target_var in SECRET_ENV_VARS.items():
        secret_id = os.environ.get(secret_var)
        if secret_id and not os.environ.get(target_var):
            os.environ[target_var] = read_secret(secret_id)
    for secret_var, fields in OPTIONAL_JSON_SECRETS.items():
        secret_id = os.environ.get(secret_var)
        if not secret_id:
            continue
        try:
            values = json.loads(read_secret(secret_id))
        except Exception:
            logger.warning("Optional secret %s isn't available; carrying on without it", secret_id)
            continue
        for key, target_var in fields.items():
            if values.get(key) and not os.environ.get(target_var):
                os.environ[target_var] = values[key]


def origin_secret() -> str | None:
    """The value CloudFront sends in the x-origin-verify header. None locally."""
    secret_id = os.environ.get("ORIGIN_SECRET_ARN")
    return read_secret(secret_id) if secret_id else None
