#!/usr/bin/env bash
# Generate a self-signed certificate for local HTTPS development.
#
# Browsers and `curl` will warn about the untrusted issuer — that is expected;
# use `curl -k` locally. Never use these certs outside development.
set -euo pipefail

cert_dir="$(cd "$(dirname "$0")/.." && pwd)/certs"
mkdir -p "$cert_dir"

if [ -f "$cert_dir/server.crt" ] && [ "${1:-}" != "--force" ]; then
    echo "Certificates already exist in $cert_dir (use --force to regenerate)."
    exit 0
fi

openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout "$cert_dir/server.key" \
    -out "$cert_dir/server.crt" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$cert_dir/server.key"
echo "Wrote $cert_dir/server.crt and $cert_dir/server.key"
