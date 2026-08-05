import os
import random
import time
from urllib.parse import urljoin, urlparse

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class LhiOpenSignConfiguration(models.Model):
    _name = "lhi.opensign.configuration"
    _description = "LHI Sign Provider Configuration"
    _order = "company_id, id"

    name = fields.Char(required=True, default="LHI Sign / OpenSign")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    api_base_url = fields.Char(
        required=True,
        help="OpenSign API base URL, including its supported version path.",
    )
    api_token_parameter = fields.Char(
        required=True,
        default="lhi_signature_bridge.api_token",
        help="System-parameter name containing the API token. The token is never shown here.",
    )
    webhook_secret_parameter = fields.Char(
        required=True,
        default="lhi_signature_bridge.webhook_secret",
        help="System-parameter name containing the OpenSign webhook HMAC secret.",
    )
    allowed_preparation_hosts = fields.Char(
        help="Comma-separated HTTPS hostnames allowed for preparation and signing redirects.",
    )
    allowed_download_hosts = fields.Char(
        help="Comma-separated HTTPS hostnames allowed for signed artefact downloads.",
    )
    timeout_seconds = fields.Integer(default=30, required=True)
    maximum_download_mb = fields.Integer(default=100, required=True)
    maximum_retries = fields.Integer(default=3, required=True)
    backoff_base_seconds = fields.Float(default=1.0, required=True)
    last_success_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    _company_unique = models.Constraint(
        "unique(company_id)", "Only one LHI Sign configuration is allowed per company."
    )

    @api.constrains(
        "api_base_url",
        "timeout_seconds",
        "maximum_download_mb",
        "maximum_retries",
        "backoff_base_seconds",
    )
    def _check_configuration(self):
        for config in self:
            parsed = urlparse(config.api_base_url or "")
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValidationError(_("The LHI Sign API base URL must use HTTPS."))
            if not 1 <= config.timeout_seconds <= 300:
                raise ValidationError(
                    _("The provider timeout must be between 1 and 300 seconds.")
                )
            if not 1 <= config.maximum_download_mb <= 500:
                raise ValidationError(
                    _("The provider download limit must be between 1 and 500 MB.")
                )
            if not 0 <= config.maximum_retries <= 10:
                raise ValidationError(
                    _("The provider retry count must be between 0 and 10.")
                )
            if not 0.1 <= config.backoff_base_seconds <= 30:
                raise ValidationError(
                    _("The provider backoff must be between 0.1 and 30 seconds.")
                )

    @api.model
    def active_for_company(self, company=None):
        company = company or self.env.company
        config = self.sudo().search(
            [("company_id", "=", company.id), ("active", "=", True)], limit=1
        )
        if not config:
            raise UserError(_("LHI Sign is not configured for this company."))
        return config

    def _secret(self, parameter_field, environment_name):
        self.ensure_one()
        value = os.environ.get(environment_name)
        if not value:
            parameter = self[parameter_field]
            value = self.env["ir.config_parameter"].sudo().get_param(parameter)
        if not value:
            raise UserError(_("A required LHI Sign secret is not configured."))
        return value

    def api_token(self):
        return self._secret("api_token_parameter", "LHI_OPENSIGN_API_TOKEN")

    def webhook_secret(self):
        return self._secret("webhook_secret_parameter", "LHI_OPENSIGN_WEBHOOK_SECRET")

    @staticmethod
    def _host_set(value):
        return {
            item.strip().lower().rstrip(".")
            for item in (value or "").split(",")
            if item.strip()
        }

    def _validated_url(self, url, *, purpose):
        self.ensure_one()
        parsed = urlparse(url or "")
        if parsed.scheme != "https" or not parsed.hostname or parsed.username:
            raise ValidationError(_("The provider returned an unsafe HTTPS URL."))
        host = parsed.hostname.lower().rstrip(".")
        api_host = urlparse(self.api_base_url).hostname.lower().rstrip(".")
        configured = self._host_set(
            self.allowed_preparation_hosts
            if purpose == "redirect"
            else self.allowed_download_hosts
        )
        allowed = configured or {api_host}
        if not any(host == item or host.endswith(f".{item}") for item in allowed):
            raise ValidationError(
                _("The provider returned a URL outside the configured allowlist.")
            )
        return url

    @staticmethod
    def _retry_after(response):
        value = response.headers.get("Retry-After")
        if value and value.isdigit():
            return min(int(value), 60)
        return False

    def api_request(
        self,
        method,
        endpoint,
        *,
        json_body=None,
        expected_statuses=None,
        retry_safe=True,
    ):
        """Call a documented OpenSign API endpoint without exposing credentials."""
        self.ensure_one()
        method = method.upper()
        if not endpoint.startswith("/"):
            raise ValidationError(_("The provider API endpoint is invalid."))
        base = self.api_base_url.rstrip("/") + "/"
        url = urljoin(base, endpoint.lstrip("/"))
        expected_statuses = set(expected_statuses or range(200, 300))
        attempts = self.maximum_retries if retry_safe else 0
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-token": self.api_token(),
        }
        for attempt in range(attempts + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout_seconds,
                    allow_redirects=False,
                )
            except requests.RequestException as error:
                retry = retry_safe and attempt < attempts
                if retry:
                    time.sleep(
                        min(
                            self.backoff_base_seconds * (2**attempt)
                            + random.uniform(0, 0.5),
                            60,
                        )
                    )
                    continue
                self.sudo().write(
                    {
                        "last_error": _("The provider network request failed."),
                    }
                )
                raise UserError(
                    _("LHI Sign did not confirm the request. Its outcome is unknown.")
                ) from error
            if response.status_code in expected_statuses:
                try:
                    payload = response.json() if response.content else {}
                except ValueError as error:
                    message = _("LHI Sign returned malformed JSON.")
                    if not retry_safe:
                        message = _(
                            "LHI Sign returned malformed JSON; its outcome is unknown."
                        )
                    raise UserError(message) from error
                self.sudo().write(
                    {"last_success_at": fields.Datetime.now(), "last_error": False}
                )
                return payload
            retry = (
                retry_safe
                and response.status_code in RETRYABLE_STATUS_CODES
                and attempt < attempts
            )
            if retry:
                delay = self._retry_after(response)
                if delay is False:
                    delay = min(
                        self.backoff_base_seconds * (2**attempt)
                        + random.uniform(0, 0.5),
                        60,
                    )
                time.sleep(delay)
                continue
            if not retry_safe and response.status_code in RETRYABLE_STATUS_CODES:
                safe_error = (
                    _("LHI Sign returned HTTP status %s; its outcome is unknown.")
                    % response.status_code
                )
            else:
                safe_error = (
                    _("LHI Sign returned HTTP status %s.") % response.status_code
                )
            self.sudo().write({"last_error": safe_error})
            raise UserError(safe_error)
        raise UserError(_("LHI Sign request failed."))

    def download_artifact(self, url):
        """Download a signed artefact using an explicit SSRF allowlist and size cap."""
        self.ensure_one()
        if url and url.startswith("/"):
            base = self.api_base_url.rstrip("/")
            url = f"{base}{url}"
        self._validated_url(url, purpose="download")
        maximum = self.maximum_download_mb * 1024 * 1024
        headers = {
            "Accept": "application/pdf",
            "x-api-token": self.api_token(),
        }
        for attempt in range(self.maximum_retries + 1):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=self.timeout_seconds,
                    allow_redirects=False,
                    stream=True,
                )
            except requests.RequestException as error:
                if attempt >= self.maximum_retries:
                    raise UserError(
                        _("The signed artefact could not be downloaded.")
                    ) from error
                time.sleep(min(self.backoff_base_seconds * (2**attempt), 60))
                continue
            if response.status_code == 200:
                chunks = []
                size = 0
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > maximum:
                        raise UserError(
                            _("The signed artefact exceeds the configured limit.")
                        )
                    chunks.append(chunk)
                content = b"".join(chunks)
                if not content:
                    raise UserError(
                        _("The provider returned an empty signed artefact.")
                    )
                return content
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.maximum_retries
            ):
                time.sleep(self._retry_after(response) or min(2**attempt, 60))
                continue
            raise UserError(
                _("The signed artefact download returned HTTP status %s.")
                % response.status_code
            )
        raise UserError(_("The signed artefact could not be downloaded."))
