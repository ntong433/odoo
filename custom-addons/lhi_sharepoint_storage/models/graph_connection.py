import ipaddress
import json
import logging
import random
import time
import uuid
from urllib.parse import quote, urlparse

import requests

from odoo import models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
ALLOWED_UPLOAD_HOST_SUFFIXES = (
    ".sharepoint.com",
    ".sharepoint-df.com",
    ".1drv.com",
)
ALLOWED_DOWNLOAD_HOST_SUFFIXES = (
    ".sharepoint.com",
    ".sharepoint-df.com",
    ".1drv.com",
    ".onedrive.com",
    ".blob.core.windows.net",
    ".msocdn.com",
    ".office.net",
    ".microsoft.com",
    ".microsoftonline.com",
    ".office365.com",
)


class LhiGraphConnection(models.Model):
    _inherit = "lhi.graph.connection"

    def lhi_binary_request(
        self,
        method,
        resource,
        *,
        data=None,
        auth_context="application",
        user=None,
        headers=None,
        expected_statuses=None,
        allow_redirects=True,
        stream=False,
    ):
        self.ensure_one()
        user = user or self.env.user
        url = self._prepare_graph_url(resource)
        expected_statuses = set(expected_statuses or range(200, 300))
        force_token = False
        for attempt in range(self.max_retries + 1):
            token = (
                self.get_application_access_token(force=force_token)
                if auth_context == "application"
                else self.get_delegated_access_token(user=user, force=force_token)
            )
            client_request_id = str(uuid.uuid4())
            request_headers = {
                "Authorization": f"Bearer {token}",
                "client-request-id": client_request_id,
                "return-client-request-id": "true",
                **(headers or {}),
            }
            started = time.monotonic()
            try:
                response = requests.request(
                    method.upper(),
                    url,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout_seconds,
                    allow_redirects=allow_redirects,
                    stream=stream,
                )
            except requests.RequestException as error:
                should_retry = attempt < self.max_retries
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method=method.upper(),
                    resource_path=self._resource_path(url),
                    outcome="retry" if should_retry else "failure",
                    status_code=0,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=False,
                    error_code=error.__class__.__name__,
                    safe_message=_("Microsoft Graph binary request failed."),
                )
                if not should_retry:
                    raise UserError(
                        _("Microsoft Graph binary request failed. Check diagnostics.")
                    ) from error
                time.sleep(
                    min(
                        self.backoff_base_seconds * (2**attempt)
                        + random.uniform(0, 0.5),
                        self.maximum_retry_after_seconds,
                    )
                )
                continue
            if response.status_code in expected_statuses:
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method=method.upper(),
                    resource_path=self._resource_path(url),
                    outcome="success",
                    status_code=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=response.headers.get("request-id"),
                    error_code=False,
                    safe_message=False,
                )
                return response
            if response.status_code == 401 and attempt == 0:
                force_token = True
                should_retry = True
                delay = 0
            else:
                should_retry = (
                    response.status_code in RETRYABLE_STATUS_CODES
                    and attempt < self.max_retries
                )
                delay = self._retry_after_seconds(
                    response, self.maximum_retry_after_seconds
                )
                if delay is False:
                    delay = min(
                        self.backoff_base_seconds * (2**attempt)
                        + random.uniform(0, 0.5),
                        self.maximum_retry_after_seconds,
                    )
            code, message = self._safe_error_payload(response)
            self._create_request_log(
                auth_context=auth_context,
                user_id=user.id if auth_context == "delegated" else False,
                method=method.upper(),
                resource_path=self._resource_path(url),
                outcome="retry" if should_retry else "failure",
                status_code=response.status_code,
                duration_ms=int((time.monotonic() - started) * 1000),
                retry_count=attempt,
                client_request_id=client_request_id,
                graph_request_id=response.headers.get("request-id"),
                error_code=code,
                safe_message=message,
            )
            if not should_retry:
                raise UserError(
                    _("Microsoft Graph request failed with status %s.")
                    % response.status_code
                )
            if delay:
                time.sleep(delay)
        raise UserError(_("Microsoft Graph binary request failed."))

    def _lhi_validate_upload_url(self, upload_url):
        parsed = urlparse(upload_url or "")
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not hostname
            or not any(hostname.endswith(suffix) for suffix in ALLOWED_UPLOAD_HOST_SUFFIXES)
        ):
            raise ValidationError(_("Microsoft returned an unsafe upload-session URL."))
        return upload_url

    def _lhi_validate_download_url(self, download_url):
        if not download_url:
            raise ValidationError(_("No download URL provided."))
        parsed = urlparse(download_url)
        if parsed.scheme != "https":
            raise ValidationError(_("Pre-authenticated download URL must use HTTPS."))
        if parsed.username or parsed.password:
            raise ValidationError(_("Pre-authenticated download URL must not contain user credentials."))
        if parsed.fragment:
            raise ValidationError(_("Pre-authenticated download URL must not contain URL fragments."))
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            raise ValidationError(_("Pre-authenticated download URL is missing a hostname."))
        if hostname == "localhost":
            raise ValidationError(_("Pre-authenticated download URL cannot target localhost."))

        try:
            ipaddress.ip_address(hostname)
            raise ValidationError(_("Pre-authenticated download URL cannot use raw IP addresses."))
        except ValueError:
            pass

        valid_host = any(
            hostname == suffix.lstrip(".") or hostname.endswith(suffix)
            for suffix in ALLOWED_DOWNLOAD_HOST_SUFFIXES
        )
        if not valid_host:
            _logger.warning("Rejected download hostname: %s (scheme: %s)", hostname, parsed.scheme)
            raise ValidationError(_("Microsoft returned an untrusted download URL hostname."))

        _logger.info("Validated download URL scheme: %s, hostname: %s", parsed.scheme, hostname)
        return download_url

    def lhi_upload_session_request(
        self,
        method,
        upload_url,
        *,
        data=None,
        headers=None,
        expected_statuses=None,
        stream=False,
        auth_context="application",
        user=None,
    ):
        self.ensure_one()
        self._lhi_validate_upload_url(upload_url)
        expected_statuses = set(expected_statuses or (200, 201, 202))
        user = user or self.env.user
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            client_request_id = str(uuid.uuid4())
            try:
                response = requests.request(
                    method.upper(),
                    upload_url,
                    data=data,
                    headers=headers or {},
                    timeout=max(self.timeout_seconds, 60),
                    stream=stream,
                )
            except requests.RequestException as error:
                should_retry = attempt < self.max_retries
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method=method.upper(),
                    resource_path="/sharepoint/preauthenticated-content",
                    outcome="retry" if should_retry else "failure",
                    status_code=0,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=False,
                    error_code=error.__class__.__name__,
                    safe_message=_("SharePoint preauthenticated request failed."),
                )
                if not should_retry:
                    raise UserError(_("SharePoint upload-session request failed.")) from error
                time.sleep(
                    min(
                        self.backoff_base_seconds * (2**attempt)
                        + random.uniform(0, 0.5),
                        self.maximum_retry_after_seconds,
                    )
                )
                continue
            if response.status_code in expected_statuses:
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method=method.upper(),
                    resource_path="/sharepoint/preauthenticated-content",
                    outcome="success",
                    status_code=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=response.headers.get("request-id"),
                    error_code=False,
                    safe_message=False,
                )
                return response
            should_retry = (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.max_retries
            )
            if not should_retry:
                code, message = self._safe_error_payload(response)
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method=method.upper(),
                    resource_path="/sharepoint/preauthenticated-content",
                    outcome="failure",
                    status_code=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=response.headers.get("request-id"),
                    error_code=code,
                    safe_message=message,
                )
                raise UserError(
                    _("SharePoint upload-session request failed with status %s.")
                    % response.status_code
                )
            delay = self._retry_after_seconds(response, self.maximum_retry_after_seconds)
            code, message = self._safe_error_payload(response)
            self._create_request_log(
                auth_context=auth_context,
                user_id=user.id if auth_context == "delegated" else False,
                method=method.upper(),
                resource_path="/sharepoint/preauthenticated-content",
                outcome="retry",
                status_code=response.status_code,
                duration_ms=int((time.monotonic() - started) * 1000),
                retry_count=attempt,
                client_request_id=client_request_id,
                graph_request_id=response.headers.get("request-id"),
                error_code=code,
                safe_message=message,
            )
            time.sleep(
                delay
                if delay is not False
                else min(
                    self.backoff_base_seconds * (2**attempt),
                    self.maximum_retry_after_seconds,
                )
            )
        raise UserError(_("SharePoint upload-session request failed."))

    def lhi_preauthenticated_download_request(
        self,
        download_url,
        *,
        auth_context="application",
        user=None,
        maximum_bytes=None,
    ):
        self.ensure_one()
        self._lhi_validate_download_url(download_url)
        user = user or self.env.user
        max_bytes = maximum_bytes or (50 * 1024 * 1024)
        timeout = max(self.timeout_seconds, 60)

        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            client_request_id = str(uuid.uuid4())
            try:
                response = requests.get(
                    download_url,
                    headers={"Accept": "*/*"},
                    timeout=timeout,
                    stream=True,
                    allow_redirects=False,
                )
            except requests.RequestException as error:
                should_retry = attempt < self.max_retries
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method="GET",
                    resource_path="/sharepoint/preauthenticated-download",
                    outcome="retry" if should_retry else "failure",
                    status_code=0,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=False,
                    error_code=error.__class__.__name__,
                    safe_message=_("SharePoint preauthenticated download failed."),
                )
                if not should_retry:
                    raise UserError(_("SharePoint pre-authenticated download failed.")) from error
                time.sleep(
                    min(
                        self.backoff_base_seconds * (2**attempt) + random.uniform(0, 0.5),
                        self.maximum_retry_after_seconds,
                    )
                )
                continue

            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get("Location")
                if not redirect_url:
                    raise UserError(_("Download redirect omitted Location header."))
                self._lhi_validate_download_url(redirect_url)
                return self.lhi_preauthenticated_download_request(
                    redirect_url,
                    auth_context=auth_context,
                    user=user,
                    maximum_bytes=max_bytes,
                )

            if response.status_code != 200:
                should_retry = (
                    response.status_code in RETRYABLE_STATUS_CODES
                    and attempt < self.max_retries
                )
                code, message = self._safe_error_payload(response)
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method="GET",
                    resource_path="/sharepoint/preauthenticated-download",
                    outcome="retry" if should_retry else "failure",
                    status_code=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=response.headers.get("request-id"),
                    error_code=code,
                    safe_message=message,
                )
                if should_retry:
                    delay = self._retry_after_seconds(response, self.maximum_retry_after_seconds)
                    time.sleep(
                        delay
                        if delay is not False
                        else min(
                            self.backoff_base_seconds * (2**attempt),
                            self.maximum_retry_after_seconds,
                        )
                    )
                    continue
                raise UserError(
                    _("SharePoint download returned HTTP status %s.")
                    % response.status_code
                )

            content_length_str = response.headers.get("Content-Length")
            if content_length_str and content_length_str.isdigit():
                if int(content_length_str) > max_bytes:
                    raise UserError(
                        _("Downloaded file size exceeds maximum permitted limit.")
                    )

            chunks = []
            downloaded_size = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                downloaded_size += len(chunk)
                if downloaded_size > max_bytes:
                    raise UserError(
                        _("Downloaded file size exceeds maximum permitted limit.")
                    )
                chunks.append(chunk)

            content = b"".join(chunks)
            if not content:
                raise UserError(_("Downloaded file is empty."))

            self._create_request_log(
                auth_context=auth_context,
                user_id=user.id if auth_context == "delegated" else False,
                method="GET",
                resource_path="/sharepoint/preauthenticated-download",
                outcome="success",
                status_code=200,
                duration_ms=int((time.monotonic() - started) * 1000),
                retry_count=attempt,
                client_request_id=client_request_id,
                graph_request_id=response.headers.get("request-id"),
                error_code=False,
                safe_message=False,
            )
            return content

        raise UserError(_("SharePoint pre-authenticated download failed."))

    def lhi_download_url_request(self, download_url, **kwargs):
        """Alias for lhi_preauthenticated_download_request."""
        return self.lhi_preauthenticated_download_request(download_url, **kwargs)

    def lhi_get_library(self, code):
        self.ensure_one()
        library = self.library_ids.filtered(
            lambda value: value.code == code and value.validation_state == "valid"
        )[:1]
        if not library or not library.drive_id or not library.root_item_id:
            raise UserError(
                _("The SharePoint %s library must be validated before document upload.")
                % code
            )
        return library

    @staticmethod
    def _lhi_safe_segment(value):
        value = " ".join(str(value or "").strip().split())
        for character in '"*:<>?/\\|#%':
            value = value.replace(character, "-")
        value = value.rstrip(". ")
        if not value or value in (".", ".."):
            raise ValidationError(_("A SharePoint folder or file name is invalid."))
        return value[:120]

    def lhi_ensure_folder_path(
        self, library, path, *, auth_context="application", user=None
    ):
        self.ensure_one()
        parent_id = library.root_item_id
        for raw_segment in [part for part in (path or "").split("/") if part.strip()]:
            segment = self._lhi_safe_segment(raw_segment)
            children = self.graph_get_all(
                f"/drives/{quote(library.drive_id)}/items/{quote(parent_id)}/children",
                auth_context=auth_context,
                user=user,
                params={"$select": "id,name,folder,parentReference"},
                max_pages=20,
                max_items=5000,
            )
            match = next(
                (
                    child
                    for child in children
                    if child.get("name", "").casefold() == segment.casefold()
                    and child.get("folder") is not None
                ),
                None,
            )
            if not match:
                match = self.graph_request(
                    "POST",
                    f"/drives/{quote(library.drive_id)}/items/{quote(parent_id)}/children",
                    auth_context=auth_context,
                    user=user,
                    json_body={
                        "name": segment,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "fail",
                    },
                    expected_statuses={200, 201},
                )
            parent_id = match["id"]
        return parent_id

    def lhi_create_upload_session(
        self,
        library,
        parent_id,
        filename,
        *,
        conflict_behavior="fail",
        auth_context="application",
        user=None,
    ):
        self.ensure_one()
        filename = self._lhi_safe_segment(filename)
        payload = self.graph_request(
            "POST",
            (
                f"/drives/{quote(library.drive_id)}/items/{quote(parent_id)}:"
                f"/{quote(filename)}:/createUploadSession"
            ),
            auth_context=auth_context,
            user=user,
            json_body={
                "item": {
                    "@microsoft.graph.conflictBehavior": conflict_behavior,
                    "name": filename,
                }
            },
            expected_statuses={200, 201},
        )
        self._lhi_validate_upload_url(payload.get("uploadUrl"))
        return payload

    def lhi_upload_small(
        self,
        library,
        parent_id,
        filename,
        content,
        *,
        conflict_behavior="fail",
        auth_context="application",
        user=None,
        mimetype="application/octet-stream",
    ):
        self.ensure_one()
        filename = self._lhi_safe_segment(filename)
        resource = (
            f"/drives/{quote(library.drive_id)}/items/{quote(parent_id)}:"
            f"/{quote(filename)}:/content"
            f"?@microsoft.graph.conflictBehavior={quote(conflict_behavior)}"
        )
        response = self.lhi_binary_request(
            "PUT",
            resource,
            data=content,
            auth_context=auth_context,
            user=user,
            headers={"Content-Type": mimetype or "application/octet-stream"},
            expected_statuses={200, 201},
        )
        try:
            return response.json()
        except ValueError as error:
            raise UserError(_("SharePoint returned malformed upload metadata.")) from error
