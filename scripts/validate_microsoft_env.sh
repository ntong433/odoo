#!/bin/sh
set -eu

mode="${1:-full}"

python3 - "$mode" <<'PY'
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

import requests


MODE = sys.argv[1]
REQUIRED = (
    "ENTRA_TENANT_ID",
    "ENTRA_CLIENT_ID",
    "ENTRA_CLIENT_SECRET",
    "SHAREPOINT_SITE_ID",
    "SHAREPOINT_DRIVE_ID",
    "SHAREPOINT_ROOT_ITEM_ID",
)
DEPRECATED_CERTIFICATE_VARIABLES = (
    "ENTRA_CERTIFICATE_PATH",
    "ENTRA_CERTIFICATE_THUMBPRINT",
    "ENTRA_PRIVATE_KEY",
    "ENTRA_PFX_PATH",
    "ENTRA_PFX_PASSWORD",
    "LHI_GRAPH_CERTIFICATE_PEM",
    "LHI_GRAPH_PRIVATE_KEY_PEM",
    "LHI_GRAPH_PRIVATE_KEY_PASSWORD",
)


def configured(name):
    return bool(os.environ.get(name))


def fail(message):
    print(f"Microsoft environment validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


print(f"Tenant configured: {'yes' if configured('ENTRA_TENANT_ID') else 'no'}")
print(f"Client ID configured: {'yes' if configured('ENTRA_CLIENT_ID') else 'no'}")
print(
    "Client secret configured: "
    f"{'yes' if configured('ENTRA_CLIENT_SECRET') else 'no'}"
)

missing = [name for name in REQUIRED if not configured(name)]
if missing:
    fail("required protected variables are missing: " + ", ".join(missing))

deprecated = [
    name for name in DEPRECATED_CERTIFICATE_VARIABLES if configured(name)
]
if deprecated:
    fail(
        "certificate-based Microsoft authentication variables are not supported: "
        + ", ".join(deprecated)
    )

tenant_id = os.environ["ENTRA_TENANT_ID"]
client_id = os.environ["ENTRA_CLIENT_ID"]
client_secret = os.environ["ENTRA_CLIENT_SECRET"]
site_id = os.environ["SHAREPOINT_SITE_ID"]
drive_id = os.environ["SHAREPOINT_DRIVE_ID"]
root_item_id = os.environ["SHAREPOINT_ROOT_ITEM_ID"]

expected_token_endpoint = (
    f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
)
token_endpoint = os.environ.get("ENTRA_TOKEN_ENDPOINT") or expected_token_endpoint
if token_endpoint != expected_token_endpoint:
    fail("ENTRA_TOKEN_ENDPOINT does not match ENTRA_TENANT_ID")

graph_base_url = (
    os.environ.get("GRAPH_BASE_URL")
    or "https://graph.microsoft.com/v1.0"
).rstrip("/")
parsed_graph_url = urlparse(graph_base_url)
if (
    parsed_graph_url.scheme != "https"
    or parsed_graph_url.hostname != "graph.microsoft.com"
    or parsed_graph_url.path != "/v1.0"
):
    fail("GRAPH_BASE_URL must be https://graph.microsoft.com/v1.0")

redirect_uri = os.environ.get("ENTRA_REDIRECT_URI")
if redirect_uri and redirect_uri != (
    "https://work.lhinigeria.org/auth_oauth/signin"
):
    fail("ENTRA_REDIRECT_URI does not match the implemented primary SSO callback")

delegated_redirect_uri = os.environ.get("ENTRA_GRAPH_DELEGATED_REDIRECT_URI")
if delegated_redirect_uri and delegated_redirect_uri != (
    "https://work.lhinigeria.org/lhi/microsoft_graph/oauth/callback"
):
    fail(
        "ENTRA_GRAPH_DELEGATED_REDIRECT_URI does not match the implemented "
        "delegated Graph callback"
    )

if MODE == "--configuration-only":
    print("Runtime configuration validation: success")
    raise SystemExit(0)
if MODE not in ("full", "--full"):
    fail("supported modes are --configuration-only and --full")

timeout = int(os.environ.get("GRAPH_HTTP_TIMEOUT_SECONDS", "60"))
max_retries = int(os.environ.get("GRAPH_MAX_RETRIES", "5"))
retry_base = float(os.environ.get("GRAPH_RETRY_BASE_SECONDS", "2"))


def retry_after(response, attempt):
    value = response.headers.get("Retry-After")
    if value:
        try:
            return max(0.0, min(float(value), 120.0))
        except ValueError:
            try:
                seconds = parsedate_to_datetime(value).timestamp() - time.time()
                return max(0.0, min(seconds, 120.0))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(retry_base * (2**attempt), 120.0)


def request_with_retry(method, url, **kwargs):
    last_response = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException:
            if attempt >= max_retries:
                raise
            time.sleep(min(retry_base * (2**attempt), 120.0))
            continue
        last_response = response
        if response.status_code not in {429, 500, 502, 503, 504}:
            return response
        if attempt >= max_retries:
            return response
        time.sleep(retry_after(response, attempt))
    return last_response


token_response = request_with_retry(
    "POST",
    token_endpoint,
    data={
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    },
    headers={"Accept": "application/json"},
)
token_request_id = (
    token_response.headers.get("request-id")
    or token_response.headers.get("x-ms-request-id")
    or "not-returned"
)
if not token_response.ok:
    print("Token acquisition: failure")
    print(f"Graph request ID: {token_request_id}")
    fail(f"token endpoint returned HTTP {token_response.status_code}")
try:
    token_payload = token_response.json()
except ValueError:
    fail("token endpoint returned malformed JSON")
access_token = token_payload.get("access_token")
if not access_token:
    fail("token endpoint did not return an access token")
expires_in = max(int(token_payload.get("expires_in") or 0), 0)
expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
print("Token acquisition: success")
print(f"Token expiry time: {expires_at.isoformat()}")
print(f"Graph request ID: {token_request_id}")

headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
}


def graph_get(label, resource, expected_id):
    response = request_with_retry(
        "GET",
        f"{graph_base_url}/{resource.lstrip('/')}",
        headers=headers,
    )
    request_id = (
        response.headers.get("request-id")
        or response.headers.get("x-ms-request-id")
        or "not-returned"
    )
    if not response.ok:
        print(f"{label}: failure")
        print(f"Graph request ID: {request_id}")
        fail(f"{label.lower()} returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        fail(f"{label.lower()} returned malformed JSON")
    if payload.get("id") != expected_id:
        fail(f"{label.lower()} returned an unexpected immutable identifier")
    print(f"{label}: success")
    print(f"Graph request ID: {request_id}")


graph_get(
    "SharePoint connection",
    f"/sites/{quote(site_id, safe=',.-')}",
    site_id,
)
graph_get(
    "SharePoint drive access",
    f"/drives/{quote(drive_id, safe='!._~-')}",
    drive_id,
)
graph_get(
    "ERP root DriveItem access",
    (
        f"/drives/{quote(drive_id, safe='!._~-')}/items/"
        f"{quote(root_item_id, safe='!._~-')}"
    ),
    root_item_id,
)
PY
