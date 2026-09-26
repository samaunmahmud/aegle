#!/usr/bin/env bash
# Local development TLS for every Aegle service.
#
# Creates, under infra/tls/certs/ (git-ignored):
#   ca.crt / ca.key          a private "Aegle Local Dev CA" (never trust it outside dev)
#   server.crt / server.key  one certificate for localhost and the compose service names
#   server-bundle.pem        certificate + key in one file (Orthanc)
#   minio/                   the layout MinIO's --certs-dir expects
#   truststore.p12           the JDK's public CAs plus the dev CA, for core-api (password: changeit)
#
# Usage: infra/tls/generate.sh [--force]   (--force replaces an existing CA and certificates)
set -euo pipefail

cd "$(dirname "$0")"
OUT=certs
if [[ -f $OUT/ca.crt && ${1:-} != "--force" ]]; then
    echo "Certificates already exist in infra/tls/$OUT (use --force to regenerate)."
    exit 0
fi
rm -rf "$OUT"
mkdir -p "$OUT/minio/CAs"

openssl req -x509 -new -nodes -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
    -keyout "$OUT/ca.key" -out "$OUT/ca.crt" -days 825 -subj "/CN=Aegle Local Dev CA" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null

openssl req -new -nodes -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
    -keyout "$OUT/server.key" -out "$OUT/server.csr" -subj "/CN=localhost" 2>/dev/null
cat > "$OUT/server.ext" <<'EXT'
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = DNS:localhost, DNS:postgres, DNS:minio, DNS:keycloak, DNS:orthanc, DNS:host.docker.internal, IP:127.0.0.1, IP:::1
EXT
# 397 days: the longest validity browsers accept for a server certificate.
openssl x509 -req -in "$OUT/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
    -days 397 -extfile "$OUT/server.ext" -out "$OUT/server.crt" 2>/dev/null
rm -f "$OUT/server.csr" "$OUT/server.ext" "$OUT/ca.srl"

cat "$OUT/server.crt" "$OUT/server.key" > "$OUT/server-bundle.pem"
cp "$OUT/server.crt" "$OUT/minio/public.crt"
cp "$OUT/server.key" "$OUT/minio/private.key"
cp "$OUT/ca.crt" "$OUT/minio/CAs/ca.crt"

# Containers run as their own users and must be able to read the key. Dev-only material;
# production keys come from a secret store, never from this script.
chmod 644 "$OUT/server.key" "$OUT/server-bundle.pem" "$OUT/minio/private.key"
chmod 600 "$OUT/ca.key"

JAVA_HOME=${JAVA_HOME:-$(/usr/libexec/java_home 2>/dev/null || dirname "$(dirname "$(readlink -f "$(command -v java)")")")}
keytool -importkeystore -noprompt -srckeystore "$JAVA_HOME/lib/security/cacerts" -srcstorepass changeit \
    -destkeystore "$OUT/truststore.p12" -deststoretype PKCS12 -deststorepass changeit >/dev/null 2>&1
keytool -importcert -noprompt -alias aegle-dev-ca -file "$OUT/ca.crt" \
    -keystore "$OUT/truststore.p12" -storepass changeit >/dev/null

echo "Wrote infra/tls/$OUT. To let your browser trust it (macOS):"
echo "  security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db infra/tls/$OUT/ca.crt"
