# Shared by claude-key.sh and database-url.sh: store one secret, then restart the API.
# Usage (from those scripts): store_secret <secret-name> <description> <value>
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-ukdoshi}" AWS_REGION="${AWS_REGION:-us-east-1}"
FUNCTION=cuddly-tales-api

check_login() {
  aws sts get-caller-identity >/dev/null 2>&1 || {
    echo "Log in to AWS first: aws sso login --profile $AWS_PROFILE" >&2
    exit 1
  }
}

store_secret() {
  local name="$1" description="$2" value="$3"
  if aws secretsmanager describe-secret --secret-id "$name" >/dev/null 2>&1; then
    aws secretsmanager put-secret-value --secret-id "$name" --secret-string "$value" >/dev/null
    echo "Updated $name."
  else
    aws secretsmanager create-secret --name "$name" --description "$description" --secret-string "$value" >/dev/null
    echo "Created $name."
  fi

  # The API reads secrets when it starts. Any configuration change makes Lambda start
  # fresh copies, so the new value is used from the next request.
  if aws lambda get-function --function-name "$FUNCTION" >/dev/null 2>&1; then
    aws lambda update-function-configuration --function-name "$FUNCTION" \
      --description "Secrets last updated $(date -u +%Y-%m-%dT%H:%M:%SZ)" >/dev/null
    echo "Restarted $FUNCTION, so it uses the new value from the next request."
  else
    echo "$FUNCTION isn't deployed yet; it will use this value from its first start."
  fi
}
