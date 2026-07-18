import base64
import hashlib
import json
import logging
import os
import random
import re
import time
import uuid
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

import requests

from odoo import api, fields, models, tools, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_SCOPE = "https://graph.microsoft.com/.default"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
SITE_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9.-]+,"
    r"[0-9a-fA-F-]{36},"
    r"[0-9a-fA-F-]{36}$"
)
REDACTION_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(
        r"""(?ix)
        (client_secret["']?\s*[:=]\s*["']?)
        [^"'\s,;&}]+
        """
    ),
    re.compile(
        r"""(?ix)
        ((?:access|refresh|id)_token["']?\s*[:=]\s*["']?)
        [^"'\s,;&}]+
        """
    ),
    re.compile(
        r"""(?ix)
        (client[_-]?state["']?\s*[:=]\s*["']?)
        [^"'\s,;&}]+
        """
    ),
)


class LhiGraphConnection(models.Model):
    _name = "lhi.graph.connection"
    _description = "Microsoft Graph Connection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, name, id"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )

    tenant_id = fields.Char(
        string="Entra Tenant ID",
        help="Non-secret reference value. Runtime authentication requires ENTRA_TENANT_ID.",
        tracking=True,
    )
    client_id = fields.Char(
        string="Application (Client) ID",
        help="Non-secret reference value. Runtime authentication requires ENTRA_CLIENT_ID.",
        tracking=True,
    )
    client_secret_status = fields.Char(
        string="Client Secret",
        compute="_compute_client_secret_status",
        help="Indicates whether ENTRA_CLIENT_SECRET is provided in the environment.",
    )
    application_permission_mode = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("sites_selected", "Sites.Selected"),
        ],
        default="sites_selected",
        required=True,
        tracking=True,
    )
    delegated_permission_mode = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("sites_selected", "Sites.Selected"),
        ],
        default="sites_selected",
        required=True,
        tracking=True,
    )
    delegated_scopes = fields.Char(
        default=(
            "openid profile offline_access "
            "https://graph.microsoft.com/Sites.Selected"
        ),
        required=True,
        help="Delegated scopes. Broad tenant-wide *.All file/site scopes are rejected.",
    )

    sharepoint_hostname = fields.Char(
        help="Example: lhinigeria.sharepoint.com",
        tracking=True,
    )
    sharepoint_site_path = fields.Char(
        string="SharePoint Site Path",
        default="/sites/LHIERP",
        help="Server-relative site path used for discovery.",
        tracking=True,
    )
    configured_site_id = fields.Char(
        string="Candidate SharePoint Site ID",
        help="Optional candidate from provisioning. It is not authoritative until Graph validation succeeds.",
    )
    sharepoint_site_id = fields.Char(
        string="Validated SharePoint Site ID",
        readonly=True,
        copy=False,
        index=True,
    )
    sharepoint_site_web_url = fields.Char(readonly=True, copy=False)
    site_validation_context = fields.Selection(
        [("application", "Application"), ("delegated", "Delegated User")],
        default="application",
        required=True,
    )
    library_ids = fields.One2many(
        "lhi.graph.library",
        "connection_id",
        string="Document Libraries",
        copy=True,
    )

    timeout_seconds = fields.Integer(default=30, required=True)
    max_retries = fields.Integer(default=4, required=True)
    backoff_base_seconds = fields.Float(default=1.0, required=True)
    maximum_retry_after_seconds = fields.Integer(default=120, required=True)
    token_expiry_skew_seconds = fields.Integer(default=300, required=True)

    connection_status = fields.Selection(
        [
            ("not_tested", "Not Tested"),
            ("connected", "Connected"),
            ("degraded", "Degraded"),
            ("failed", "Failed"),
        ],
        default="not_tested",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
    )
    last_successful_test = fields.Datetime(readonly=True, copy=False)
    last_test_at = fields.Datetime(readonly=True, copy=False)
    last_safe_error = fields.Text(readonly=True, copy=False)

    _company_name_unique = models.Constraint(
        "unique(company_id, name)",
        "Microsoft Graph connection names must be unique per company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        defaults = [
            ("projects", "Projects"),
            ("procurement", "Procurement"),
            ("operations", "Operations"),
            ("controlled_documents", "Controlled Documents"),
            ("signed_documents", "Signed Documents"),
        ]
        for vals in vals_list:
            if not vals.get("library_ids"):
                vals["library_ids"] = [
                    (0, 0, {"sequence": index * 10, "code": code, "expected_name": name})
                    for index, (code, name) in enumerate(defaults, start=1)
                ]
        records = super().create(vals_list)
        for record in records:
            record._audit_sensitive_configuration("Microsoft Graph connection created.")
        return records

    def write(self, vals):
        protected = {
            "sharepoint_site_id",
            "sharepoint_site_web_url",
            "connection_status",
            "last_successful_test",
            "last_test_at",
            "last_safe_error",
        }
        if protected.intersection(vals) and not self.env.context.get("lhi_graph_validated_write"):
            raise ValidationError(
                _("Validated Graph status and identifiers can only be written by Graph validation actions.")
            )
        reset_fields = {
            "tenant_id",
            "client_id",
            "application_permission_mode",
            "sharepoint_hostname",
            "sharepoint_site_path",
            "configured_site_id",
        }
        if reset_fields.intersection(vals):
            vals = dict(vals)
            vals.update(
                {
                    "sharepoint_site_id": False,
                    "sharepoint_site_web_url": False,
                    "connection_status": "not_tested",
                    "last_successful_test": False,
                    "last_safe_error": False,
                }
            )
            result = super(
                LhiGraphConnection,
                self.with_context(lhi_graph_validated_write=True),
            ).write(vals)
        else:
            result = super().write(vals)
        if vals and not self.env.context.get("lhi_graph_validated_write"):
            changed = ", ".join(sorted(set(vals).intersection(reset_fields)))
            if changed:
                for record in self:
                    record._audit_sensitive_configuration(
                        _("Microsoft Graph configuration changed: %s") % changed
                    )
        return result

    @api.constrains(
        "tenant_id",
        "client_id",
        "sharepoint_hostname",
        "sharepoint_site_path",
        "configured_site_id",
    )
    def _check_identifiers(self):
        for record in self:
            tenant_id = record.tenant_id
            client_id = record.client_id
            if tenant_id and not UUID_PATTERN.fullmatch(tenant_id):
                raise ValidationError(_("The Entra tenant ID must be a UUID."))
            if client_id and not UUID_PATTERN.fullmatch(client_id):
                raise ValidationError(_("The Microsoft application client ID must be a UUID."))
            hostname = record.sharepoint_hostname
            if hostname and (
                not re.fullmatch(r"[A-Za-z0-9.-]+\.sharepoint\.com", hostname)
                or "://" in hostname
                or "/" in hostname
            ):
                raise ValidationError(_("Enter a SharePoint hostname without a scheme or path."))
            site_path = record.sharepoint_site_path
            if site_path and (
                not site_path.startswith("/")
                or ".." in site_path.split("/")
                or "?" in site_path
                or "#" in site_path
            ):
                raise ValidationError(_("The SharePoint site path is invalid."))
            candidate = record.configured_site_id
            if candidate and not SITE_ID_PATTERN.fullmatch(candidate):
                raise ValidationError(_("The candidate SharePoint site ID has an invalid format."))

    @api.constrains(
        "delegated_scopes",
        "delegated_permission_mode",
        "application_permission_mode",
    )
    def _check_permission_modes(self):
        broad_scopes = {
            "Files.Read.All",
            "Files.ReadWrite.All",
            "Sites.Read.All",
            "Sites.ReadWrite.All",
        }
        for record in self:
            scopes = set((record.delegated_scopes or "").split())
            normalized = {scope.rsplit("/", 1)[-1] for scope in scopes}
            prohibited = sorted(normalized.intersection(broad_scopes))
            if prohibited:
                raise ValidationError(
                    _(
                        "Tenant-wide delegated scopes are prohibited for this connection: %s"
                    )
                    % ", ".join(prohibited)
                )
            if (
                record.delegated_permission_mode == "sites_selected"
                and "Sites.Selected" not in normalized
            ):
                raise ValidationError(_("Delegated Sites.Selected mode requires the Sites.Selected scope."))
            if "offline_access" not in normalized and record.delegated_permission_mode != "disabled":
                raise ValidationError(_("Delegated mode requires offline_access for token renewal."))
            if record.application_permission_mode not in ("disabled", "sites_selected"):
                raise ValidationError(_("Only Sites.Selected application access is supported."))

    @api.constrains(
        "timeout_seconds",
        "max_retries",
        "backoff_base_seconds",
        "maximum_retry_after_seconds",
        "token_expiry_skew_seconds",
    )
    def _check_operational_bounds(self):
        for record in self:
            if not 1 <= record.timeout_seconds <= 120:
                raise ValidationError(_("Graph timeout must be between 1 and 120 seconds."))
            if not 0 <= record.max_retries <= 8:
                raise ValidationError(_("Graph retries must be between 0 and 8."))
            if not 0.1 <= record.backoff_base_seconds <= 30:
                raise ValidationError(_("Graph backoff base must be between 0.1 and 30 seconds."))
            if not 1 <= record.maximum_retry_after_seconds <= 900:
                raise ValidationError(_("Maximum Retry-After must be between 1 and 900 seconds."))
            if not 30 <= record.token_expiry_skew_seconds <= 900:
                raise ValidationError(_("Token expiry skew must be between 30 and 900 seconds."))

    @api.model
    def _get_active_connection(self, company=None):
        company = company or self.env.company
        connection = self.sudo().search(
            [("active", "=", True), ("company_id", "=", company.id)],
            order="id",
            limit=1,
        )
        if not connection:
            raise UserError(_("No active Microsoft Graph connection is configured for this company."))
        return connection

    def _audit_sensitive_configuration(self, description):
        self.ensure_one()
        self.env["lhi.audit.log"].create_event(
            event_type="write_sensitive_field",
            res_model=self._name,
            res_id=self.id,
            description=description,
        )

    @staticmethod
    def _base64url(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    @staticmethod
    def _redact_text(value):
        text = str(value or "")
        for environment_name in (
            "ENTRA_CLIENT_SECRET",
            "GRAPH_WEBHOOK_CLIENT_STATE",
        ):
            protected_value = os.environ.get(environment_name)
            if protected_value:
                text = text.replace(protected_value, "[REDACTED]")
        for pattern in REDACTION_PATTERNS:
            text = pattern.sub(r"\1[REDACTED]", text)
        return text[:2000]

    @staticmethod
    def _safe_error_payload(response):
        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = {}
        error = payload.get("error") if isinstance(payload, dict) else {}
        if isinstance(error, dict):
            code = str(error.get("code") or "")
            message = str(error.get("message") or "")
        else:
            code = str(error or "")
            message = ""
        return code[:120], LhiGraphConnection._redact_text(message)[:500]

    def _required_environment_value(self, environment_name, label):
        self.ensure_one()
        value = os.environ.get(environment_name)
        if not value:
            raise UserError(
                self.env._(
                    "%s is not configured in the protected runtime environment."
                )
                % label
            )
        return value

    def _effective_tenant_id(self):
        value = self._required_environment_value(
            "ENTRA_TENANT_ID",
            _("Microsoft Entra tenant ID"),
        )
        if not value or not UUID_PATTERN.fullmatch(value):
            raise UserError(_("A valid Entra tenant ID is required."))
        return value

    def _effective_client_id(self):
        value = self._required_environment_value(
            "ENTRA_CLIENT_ID",
            _("Microsoft application client ID"),
        )
        if not value or not UUID_PATTERN.fullmatch(value):
            raise UserError(_("A valid Microsoft application client ID is required."))
        return value

    def _effective_client_secret(self):
        self.ensure_one()
        return self._required_environment_value(
            "ENTRA_CLIENT_SECRET",
            _("Microsoft application client secret"),
        )

    def _token_endpoint(self):
        return (
            "https://login.microsoftonline.com/"
            f"{self._effective_tenant_id()}/oauth2/v2.0/token"
        )

    def _application_client_authentication_payload(self):
        self.ensure_one()
        return {"client_secret": self._effective_client_secret()}

    def _delegated_client_authentication_payload(self):
        """Authenticate the confidential web client without changing token context."""
        self.ensure_one()
        return {"client_secret": self._effective_client_secret()}

    def _environment_configuration_status(self):
        self.ensure_one()
        return {
            "tenant_configured": bool(os.environ.get("ENTRA_TENANT_ID")),
            "client_id_configured": bool(os.environ.get("ENTRA_CLIENT_ID")),
            "client_secret_configured": bool(os.environ.get("ENTRA_CLIENT_SECRET")),
        }

    def _compute_client_secret_status(self):
        for record in self:
            if os.environ.get("ENTRA_CLIENT_SECRET"):
                record.client_secret_status = "******** (Environment-Managed)"
            else:
                record.client_secret_status = "Missing"

    def _token_cache_key(self, token_context, user=None):
        self.ensure_one()
        return (
            f"{token_context}:{self.id}:{user.id}"
            if user
            else f"{token_context}:{self.id}"
        )

    def _cached_token(self, token_context, user=None):
        self.ensure_one()
        cache_key = self._token_cache_key(token_context, user=user)
        token = self.env["lhi.graph.token"].sudo().search(
            [("cache_key", "=", cache_key)],
            limit=1,
        )
        if not token or not token.access_token:
            return self.env["lhi.graph.token"]
        usable_until = fields.Datetime.now() + timedelta(
            seconds=self.token_expiry_skew_seconds
        )
        return token if token.expires_at > usable_until else self.env["lhi.graph.token"]

    def _store_token(self, token_context, payload, user=None):
        self.ensure_one()
        expires_in = max(int(payload.get("expires_in") or 0), 60)
        expires_at = fields.Datetime.now() + timedelta(seconds=expires_in)
        cache_key = self._token_cache_key(token_context, user=user)
        token = self.env["lhi.graph.token"].sudo().search(
            [("cache_key", "=", cache_key)],
            limit=1,
        )
        vals = {
            "cache_key": cache_key,
            "connection_id": self.id,
            "user_id": user.id if user else False,
            "token_context": token_context,
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token")
            or (token.refresh_token if token else False),
            "token_type": payload.get("token_type") or "Bearer",
            "scope": payload.get("scope") or TOKEN_SCOPE,
            "expires_at": expires_at,
        }
        if not vals["access_token"]:
            raise UserError(_("Microsoft did not return an access token."))
        if token:
            token.write(vals)
        else:
            token = self.env["lhi.graph.token"].sudo().create(vals)
        return token

    def _post_token_request(self, data, *, auth_context="application", user=None):
        self.ensure_one()
        if auth_context not in ("application", "delegated"):
            raise ValidationError(_("Invalid Microsoft Graph token context."))
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            client_request_id = str(uuid.uuid4())
            try:
                response = requests.post(
                    self._token_endpoint(),
                    data=data,
                    headers={"client-request-id": client_request_id},
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as error:
                should_retry = attempt < self.max_retries
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" and user else False,
                    method="POST",
                    resource_path="/oauth2/v2.0/token",
                    outcome="retry" if should_retry else "failure",
                    status_code=0,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=False,
                    error_code=error.__class__.__name__,
                    safe_message=_("Token endpoint request failed."),
                )
                if not should_retry:
                    raise UserError(
                        self.env._(
                            "Microsoft token acquisition failed. Check Graph diagnostics."
                        )
                    ) from error
                delay = min(
                    self.backoff_base_seconds * (2**attempt)
                    + random.uniform(0, 0.5),
                    self.maximum_retry_after_seconds,
                )
                time.sleep(delay)
                continue

            code, safe_message = self._safe_error_payload(response)
            if response.ok:
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" and user else False,
                    method="POST",
                    resource_path="/oauth2/v2.0/token",
                    outcome="success",
                    status_code=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=response.headers.get("request-id"),
                    error_code=False,
                    safe_message=False,
                )
                try:
                    return response.json()
                except ValueError as error:
                    raise UserError(
                        self.env._(
                            "Microsoft token endpoint returned malformed JSON."
                        )
                    ) from error

            should_retry = (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.max_retries
            )
            self._create_request_log(
                auth_context=auth_context,
                user_id=user.id if auth_context == "delegated" and user else False,
                method="POST",
                resource_path="/oauth2/v2.0/token",
                outcome="retry" if should_retry else "failure",
                status_code=response.status_code,
                duration_ms=int((time.monotonic() - started) * 1000),
                retry_count=attempt,
                client_request_id=client_request_id,
                graph_request_id=response.headers.get("request-id"),
                error_code=code,
                safe_message=safe_message,
            )
            if not should_retry:
                raise UserError(
                    self.env._(
                        "Microsoft token acquisition failed. Check Graph diagnostics."
                    )
                )
            delay = self._retry_after_seconds(
                response,
                self.maximum_retry_after_seconds,
            )
            if delay is False:
                delay = min(
                    self.backoff_base_seconds * (2**attempt)
                    + random.uniform(0, 0.5),
                    self.maximum_retry_after_seconds,
                )
            if delay:
                time.sleep(delay)
        raise UserError(
            self.env._("Microsoft token acquisition failed. Check Graph diagnostics.")
        )

    def get_application_access_token(self, force=False):
        self.ensure_one()
        if self.application_permission_mode != "sites_selected":
            raise UserError(_("Application Microsoft Graph access is disabled."))
        cached = self._cached_token("application")
        if cached and not force:
            return cached.access_token
        data = {
            "client_id": self._effective_client_id(),
            "scope": TOKEN_SCOPE,
            "grant_type": "client_credentials",
            **self._application_client_authentication_payload(),
        }
        return self._store_token(
            "application",
            self._post_token_request(data, auth_context="application"),
        ).access_token

    def get_delegated_access_token(self, user=None, force=False):
        self.ensure_one()
        user = user or self.env.user
        if self.delegated_permission_mode != "sites_selected":
            raise UserError(_("Delegated Microsoft Graph access is disabled."))
        cached = self._cached_token("delegated", user=user)
        if cached and not force:
            return cached.access_token
        token = self.env["lhi.graph.token"].sudo().search(
            [("cache_key", "=", self._token_cache_key("delegated", user=user))],
            limit=1,
        )
        if not token or not token.refresh_token:
            raise UserError(_("The user must authorize Microsoft Graph access."))
        data = {
            "client_id": self._effective_client_id(),
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "scope": self.delegated_scopes,
            **self._delegated_client_authentication_payload(),
        }
        return self._store_token(
            "delegated",
            self._post_token_request(
                data,
                auth_context="delegated",
                user=user,
            ),
            user=user,
        ).access_token

    def exchange_delegated_code(self, code, redirect_uri, code_verifier, user):
        self.ensure_one()
        data = {
            "client_id": self._effective_client_id(),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": self.delegated_scopes,
            "code_verifier": code_verifier,
            **self._delegated_client_authentication_payload(),
        }
        token = self._store_token(
            "delegated",
            self._post_token_request(
                data,
                auth_context="delegated",
                user=user,
            ),
            user=user,
        )
        self._audit_sensitive_configuration(
            _("Delegated Microsoft Graph authorization recorded for user ID %s.") % user.id
        )
        return token

    def delegated_authorization_action(self, user):
        self.ensure_one()
        if self.delegated_permission_mode != "sites_selected":
            raise UserError(_("Delegated Microsoft Graph access is disabled."))
        verifier = self._base64url(os.urandom(48))
        challenge = self._base64url(hashlib.sha256(verifier.encode()).digest())
        nonce = str(uuid.uuid4())
        state_record = self.env["lhi.graph.oauth.state"].sudo().create(
            {
                "nonce": nonce,
                "connection_id": self.id,
                "user_id": user.id,
                "code_verifier": verifier,
                "expires_at": fields.Datetime.now() + timedelta(minutes=10),
            }
        )
        state = tools.hash_sign(
            self.env(su=True),
            "lhi-microsoft-graph-delegated",
            {
                "state_id": state_record.id,
                "nonce": nonce,
                "user_id": user.id,
                "db": self.env.cr.dbname,
            },
            expiration=timedelta(minutes=10),
        )
        redirect_uri = self._delegated_redirect_uri()
        params = {
            "client_id": self._effective_client_id(),
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": self.delegated_scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        query = requests.compat.urlencode(params)
        return {
            "type": "ir.actions.act_url",
            "url": (
                "https://login.microsoftonline.com/"
                f"{self._effective_tenant_id()}/oauth2/v2.0/authorize?{query}"
            ),
            "target": "self",
        }

    def _delegated_redirect_uri(self):
        self.ensure_one()
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).rstrip("/")
        parsed = urlparse(base_url)
        environment = os.environ.get("LHI_ENVIRONMENT", "development").lower()
        if environment == "production":
            if base_url != "https://work.lhinigeria.org":
                raise UserError(
                    _(
                        "Production Microsoft Graph redirects require "
                        "https://work.lhinigeria.org as Odoo's base URL."
                    )
                )
        elif parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise UserError(_("Configure a valid Odoo base URL before delegated authorization."))
        expected_redirect_uri = (
            f"{base_url}/lhi/microsoft_graph/oauth/callback"
        )
        configured_redirect_uri = os.environ.get(
            "ENTRA_GRAPH_DELEGATED_REDIRECT_URI"
        )
        if configured_redirect_uri and configured_redirect_uri != expected_redirect_uri:
            raise UserError(
                _(
                    "ENTRA_GRAPH_DELEGATED_REDIRECT_URI does not match the "
                    "implemented delegated Microsoft Graph callback."
                )
            )
        return configured_redirect_uri or expected_redirect_uri

    @staticmethod
    def _retry_after_seconds(response, maximum):
        value = response.headers.get("Retry-After")
        if not value:
            return False
        try:
            seconds = float(value)
        except ValueError:
            try:
                seconds = parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                return False
        return max(0.0, min(seconds, maximum))

    @staticmethod
    def _resource_path(url):
        parsed = urlparse(url)
        return parsed.path[:1000]

    def _prepare_graph_url(self, resource):
        if resource.startswith(("http://", "https://")):
            parsed = urlparse(resource)
            if parsed.scheme != "https" or parsed.hostname != "graph.microsoft.com":
                raise ValidationError(_("Only HTTPS Microsoft Graph nextLink URLs are allowed."))
            return resource
        return f"{GRAPH_BASE_URL}/{resource.lstrip('/')}"

    def _create_request_log(self, **vals):
        self.ensure_one()
        vals["connection_id"] = self.id
        vals["safe_message"] = self._redact_text(vals.get("safe_message"))
        try:
            return self.env["lhi.graph.request.log"].sudo().create(vals)
        except Exception:
            _logger.exception("Could not persist Microsoft Graph request metadata")
            return self.env["lhi.graph.request.log"]

    def graph_request(
        self,
        method,
        resource,
        *,
        auth_context="application",
        user=None,
        params=None,
        json_body=None,
        headers=None,
        expected_statuses=None,
    ):
        self.ensure_one()
        if auth_context not in ("application", "delegated"):
            raise ValidationError(_("Invalid Microsoft Graph authorization context."))
        user = user or self.env.user
        url = self._prepare_graph_url(resource)
        method = method.upper()
        expected_statuses = set(expected_statuses or range(200, 300))
        force_token = False
        last_response = None
        for attempt in range(self.max_retries + 1):
            token = (
                self.get_application_access_token(force=force_token)
                if auth_context == "application"
                else self.get_delegated_access_token(user=user, force=force_token)
            )
            client_request_id = str(uuid.uuid4())
            request_headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "client-request-id": client_request_id,
                "return-client-request-id": "true",
                **(headers or {}),
            }
            started = time.monotonic()
            try:
                response = requests.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=request_headers,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as error:
                duration = int((time.monotonic() - started) * 1000)
                should_retry = attempt < self.max_retries
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method=method,
                    resource_path=self._resource_path(url),
                    outcome="retry" if should_retry else "failure",
                    status_code=0,
                    duration_ms=duration,
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=False,
                    error_code=error.__class__.__name__,
                    safe_message=_("Microsoft Graph network request failed."),
                )
                if not should_retry:
                    raise UserError(_("Microsoft Graph request failed. Check Graph diagnostics.")) from error
                delay = min(
                    self.backoff_base_seconds * (2**attempt) + random.uniform(0, 0.5),
                    self.maximum_retry_after_seconds,
                )
                time.sleep(delay)
                continue

            last_response = response
            duration = int((time.monotonic() - started) * 1000)
            code, safe_message = self._safe_error_payload(response)
            if response.status_code in expected_statuses:
                self._create_request_log(
                    auth_context=auth_context,
                    user_id=user.id if auth_context == "delegated" else False,
                    method=method,
                    resource_path=self._resource_path(url),
                    outcome="success",
                    status_code=response.status_code,
                    duration_ms=duration,
                    retry_count=attempt,
                    client_request_id=client_request_id,
                    graph_request_id=response.headers.get("request-id"),
                    error_code=False,
                    safe_message=False,
                )
                if response.status_code == 204 or not response.content:
                    return {}
                try:
                    return response.json()
                except ValueError as error:
                    raise UserError(_("Microsoft Graph returned malformed JSON.")) from error

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
                    response,
                    self.maximum_retry_after_seconds,
                )
                if delay is False:
                    delay = min(
                        self.backoff_base_seconds * (2**attempt)
                        + random.uniform(0, 0.5),
                        self.maximum_retry_after_seconds,
                    )
            self._create_request_log(
                auth_context=auth_context,
                user_id=user.id if auth_context == "delegated" else False,
                method=method,
                resource_path=self._resource_path(url),
                outcome="retry" if should_retry else "failure",
                status_code=response.status_code,
                duration_ms=duration,
                retry_count=attempt,
                client_request_id=client_request_id,
                graph_request_id=response.headers.get("request-id"),
                error_code=code,
                safe_message=safe_message,
            )
            if not should_retry:
                raise UserError(
                    _("Microsoft Graph request failed with status %s. Check diagnostics.")
                    % response.status_code
                )
            if delay:
                time.sleep(delay)

        status = last_response.status_code if last_response else 0
        raise UserError(_("Microsoft Graph request failed with status %s.") % status)

    def graph_get_all(
        self,
        resource,
        *,
        auth_context="application",
        user=None,
        params=None,
        headers=None,
        max_pages=100,
        max_items=10000,
    ):
        self.ensure_one()
        if not 1 <= max_pages <= 1000 or not 1 <= max_items <= 100000:
            raise ValidationError(_("Microsoft Graph pagination bounds are invalid."))
        items = []
        next_link = resource
        page = 0
        first_params = params
        while next_link:
            if page >= max_pages:
                raise UserError(_("Microsoft Graph pagination exceeded the configured page limit."))
            payload = self.graph_request(
                "GET",
                next_link,
                auth_context=auth_context,
                user=user,
                params=first_params,
                headers=headers,
            )
            first_params = None
            page_items = payload.get("value")
            if not isinstance(page_items, list):
                raise UserError(_("Microsoft Graph collection response did not contain a value list."))
            items.extend(page_items)
            if len(items) > max_items:
                raise UserError(_("Microsoft Graph pagination exceeded the configured item limit."))
            next_link = payload.get("@odata.nextLink")
            if next_link:
                self._prepare_graph_url(next_link)
            page += 1
        return items

    def _site_resource(self):
        self.ensure_one()
        candidate = self._required_environment_value(
            "SHAREPOINT_SITE_ID",
            _("SharePoint site ID"),
        )
        if not SITE_ID_PATTERN.fullmatch(candidate):
            raise UserError(_("The protected SharePoint site ID has an invalid format."))
        return f"/sites/{quote(candidate, safe=',.-')}"

    def action_validate_site(self):
        self.ensure_one()
        user = self.env.user
        payload = self.graph_request(
            "GET",
            self._site_resource(),
            auth_context=self.site_validation_context,
            user=user,
            params={"$select": "id,displayName,webUrl"},
        )
        site_id = payload.get("id")
        web_url = payload.get("webUrl")
        if not site_id or not SITE_ID_PATTERN.fullmatch(site_id):
            raise UserError(_("Microsoft Graph did not return a valid SharePoint site ID."))
        parsed = urlparse(web_url or "")
        expected_hostname = os.environ.get("SHAREPOINT_HOSTNAME")
        if parsed.scheme != "https" or (
            expected_hostname and parsed.hostname != expected_hostname
        ):
            raise UserError(_("The SharePoint site response did not match the configured hostname."))
        self.with_context(lhi_graph_validated_write=True).write(
            {
                "sharepoint_site_id": site_id,
                "sharepoint_site_web_url": web_url,
            }
        )
        self.message_post(body=_("SharePoint site identity validated through Microsoft Graph."))
        return True

    def _validate_library(self, library):
        self.ensure_one()
        if library.connection_id != self:
            raise ValidationError(_("The SharePoint library belongs to another connection."))
        if not self.sharepoint_site_id:
            self.action_validate_site()
        configured_drive_id = self._required_environment_value(
            "SHAREPOINT_DRIVE_ID",
            _("SharePoint document drive ID"),
        )
        configured_root_item_id = self._required_environment_value(
            "SHAREPOINT_ROOT_ITEM_ID",
            _("SharePoint ERP root DriveItem ID"),
        )
        drives = self.graph_get_all(
            f"/sites/{quote(self.sharepoint_site_id, safe=',.-')}/drives",
            auth_context=self.site_validation_context,
            user=self.env.user,
            params={"$select": "id,name,webUrl,driveType"},
            max_pages=20,
            max_items=200,
        )
        matches = [
            drive for drive in drives if drive.get("id") == configured_drive_id
        ]
        if len(matches) != 1:
            raise UserError(
                _("The configured SharePoint document drive is outside the validated site.")
            )
        payload = matches[0]
        if payload.get("driveType") != "documentLibrary" or not payload.get("id"):
            raise UserError(_("The validated SharePoint resource is not a document library."))
        root = self.graph_request(
            "GET",
            (
                f"/drives/{quote(payload['id'], safe='!._~-')}/items/"
                f"{quote(configured_root_item_id, safe='!._~-')}"
            ),
            auth_context=self.site_validation_context,
            user=self.env.user,
            params={"$select": "id,name,webUrl,folder,parentReference"},
        )
        if root.get("id") != configured_root_item_id or root.get("folder") is None:
            raise UserError(
                _("Microsoft Graph did not confirm the configured ERP root folder.")
            )
        expected_root_name = os.environ.get("SHAREPOINT_ROOT_FOLDER")
        if expected_root_name and root.get("name") != expected_root_name:
            raise UserError(
                _("The configured ERP root DriveItem does not match its expected folder name.")
            )
        library.with_context(lhi_graph_validated_write=True).write(
            {
                "drive_id": payload["id"],
                "drive_web_url": payload.get("webUrl"),
                "root_item_id": root["id"],
                "validation_state": "valid",
                "last_validated_at": fields.Datetime.now(),
                "validation_message": _("Validated through Microsoft Graph."),
            }
        )
        return True

    def action_clear_application_token_cache(self):
        self.ensure_one()
        if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            raise AccessError(
                _("Only an LHI ERP administrator may clear application token cache.")
            )
        self.env["lhi.graph.token"].sudo().search(
            [
                ("connection_id", "=", self.id),
                ("token_context", "=", "application"),
            ]
        ).unlink()
        self._audit_sensitive_configuration(
            _("Microsoft Graph application token cache cleared.")
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Microsoft Graph"),
                "message": _("Application token cache cleared."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_validate_libraries(self):
        self.ensure_one()
        for library in self.library_ids:
            self._validate_library(library)
        self.message_post(body=_("All configured SharePoint document libraries were validated."))
        return True

    def _run_diagnostics(self):
        self.ensure_one()
        environment_status = self._environment_configuration_status()
        environment_ready = all(environment_status.values())
        checks = [
            {
                "code": "environment_configuration",
                "status": "success" if environment_ready else "failure",
                "message": (
                    False
                    if environment_ready
                    else _("Required Microsoft application environment is incomplete.")
                ),
                **environment_status,
            }
        ]
        overall = "success"
        if checks[0]["status"] == "failure":
            overall = "failure"
        for code, callback in [
            ("application_token", lambda: self.get_application_access_token(force=True)),
            ("sharepoint_site", self.action_validate_site),
            ("sharepoint_drive_and_root", self.action_validate_libraries),
        ]:
            if overall == "failure":
                break
            started = time.monotonic()
            try:
                callback()
                check = {
                    "code": code,
                    "status": "success",
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
                if code == "application_token":
                    token = self.env["lhi.graph.token"].sudo().search(
                        [
                            ("connection_id", "=", self.id),
                            ("token_context", "=", "application"),
                        ],
                        order="expires_at desc, id desc",
                        limit=1,
                    )
                    check["token_expires_at"] = (
                        fields.Datetime.to_string(token.expires_at) if token else False
                    )
                latest_request = self.env["lhi.graph.request.log"].sudo().search(
                    [("connection_id", "=", self.id)],
                    order="id desc",
                    limit=1,
                )
                check["graph_request_id"] = (
                    latest_request.graph_request_id if latest_request else False
                )
                checks.append(check)
            except Exception as error:
                overall = "failure"
                latest_request = self.env["lhi.graph.request.log"].sudo().search(
                    [("connection_id", "=", self.id)],
                    order="id desc",
                    limit=1,
                )
                checks.append(
                    {
                        "code": code,
                        "status": "failure",
                        "duration_ms": int((time.monotonic() - started) * 1000),
                        "graph_request_id": (
                            latest_request.graph_request_id
                            if latest_request
                            else False
                        ),
                        "message": self._redact_text(error),
                    }
                )
                break
        now = fields.Datetime.now()
        diagnostic = self.env["lhi.graph.diagnostic"].sudo().create(
            {
                "connection_id": self.id,
                "run_by_id": self.env.user.id,
                "state": overall,
                "details": json.dumps(checks, indent=2, sort_keys=True),
                "completed_at": now,
            }
        )
        status_vals = {
            "last_test_at": now,
            "connection_status": "connected" if overall == "success" else "failed",
            "last_safe_error": False
            if overall == "success"
            else checks[-1].get("message"),
        }
        if overall == "success":
            status_vals["last_successful_test"] = now
        self.with_context(lhi_graph_validated_write=True).write(status_vals)
        return diagnostic

    def action_run_diagnostics(self):
        self.ensure_one()
        diagnostic = self._run_diagnostics()
        return {
            "type": "ir.actions.act_window",
            "name": _("Microsoft Graph Diagnostic"),
            "res_model": "lhi.graph.diagnostic",
            "res_id": diagnostic.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_test_connection(self):
        self.ensure_one()
        diagnostic = self._run_diagnostics()
        message = (
            _("Microsoft Graph and SharePoint validation succeeded.")
            if diagnostic.state == "success"
            else _("Microsoft Graph validation failed. Open diagnostics for safe details.")
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Microsoft Graph"),
                "message": message,
                "type": "success" if diagnostic.state == "success" else "warning",
                "sticky": diagnostic.state != "success",
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "lhi.graph.diagnostic",
                    "res_id": diagnostic.id,
                    "view_mode": "form",
                },
            },
        }
