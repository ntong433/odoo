import os
import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


DEFAULT_ENTRA_TENANT_ID = "552a1d00-ce70-4fdb-940f-0ad131e4b9cb"
DEFAULT_ENTRA_CLIENT_ID = "02b3748f-e84b-4bec-935a-21fab1498517"


class LhiEntraConfiguration(models.Model):
    _name = "lhi.entra.configuration"
    _description = "LHI Entra Identity Synchronization Configuration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, id"

    name = fields.Char(required=True, default="LHI Entra Identity Sync")
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    connection_id = fields.Many2one(
        "lhi.graph.connection",
        required=True,
        check_company=True,
        ondelete="restrict",
        tracking=True,
    )
    oauth_provider_id = fields.Many2one(
        "auth.oauth.provider",
        required=True,
        default=lambda self: self.env.ref(
            "lhi_entra_identity_sync.oauth_provider_microsoft_entra",
            raise_if_not_found=False,
        ),
        ondelete="restrict",
        tracking=True,
    )
    sync_mode = fields.Selection(
        [("dry_run", "Dry Run Only"), ("write", "Write Enabled")],
        default="dry_run",
        required=True,
        tracking=True,
    )
    approved_dry_run_id = fields.Many2one(
        "lhi.entra.sync.run",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    primary_sso_enabled = fields.Boolean(
        string="Primary Entra Login Enabled",
        default=False,
        tracking=True,
    )
    allow_controlled_first_match = fields.Boolean(
        string="Allow Controlled First Match by UPN/Email",
        default=False,
        tracking=True,
    )
    create_missing_users = fields.Boolean(
        string="Provision Missing Odoo Users",
        default=True,
        tracking=True,
        help=(
            "Create real internal Odoo users for unambiguous in-scope Entra identities. "
            "Creation remains subject to dry-run approval and never sends an invitation."
        ),
    )
    send_invitation_emails_after_sync = fields.Boolean(
        string="Send Invitation Emails After Sync",
        default=False,
        tracking=True,
        help=(
            "Reserved for a separately approved manual invitation process. Automatic "
            "and scheduled Entra synchronization never sends invitations."
        ),
    )
    sync_login_from_upn = fields.Boolean(default=True, tracking=True)
    user_scope_mode = fields.Selection(
        [
            ("existing_users", "Existing Odoo Entra Identities"),
            ("entra_group", "Approved Entra Scope Group"),
            ("tenant_directory", "Entire Tenant Directory"),
        ],
        default="existing_users",
        required=True,
        tracking=True,
        help=(
            "Existing users is the safest routine mode. An approved Entra scope "
            "group supports nested membership and controlled first-time matching. "
            "Entire tenant directory should be used only for bounded diagnostics."
        ),
    )
    entra_scope_group_object_id = fields.Char(
        string="Approved Entra Scope Group Object ID",
        tracking=True,
    )
    sync_organizational_scope = fields.Boolean(
        string="Synchronize Department and Office Scope",
        default=True,
        tracking=True,
        help=(
            "Matches Entra department and office names to existing LHI master data. "
            "Missing or ambiguous values are blocked; master data is never auto-created."
        ),
    )
    create_missing_employee = fields.Boolean(
        default=False,
        tracking=True,
        help="Create an HR employee only for an already matched Odoo user.",
    )
    deactivation_policy = fields.Selection(
        [
            ("block_login", "Block Entra Login and Require Review"),
            ("archive", "Block Login and Archive User/Employee"),
        ],
        default="block_login",
        required=True,
        tracking=True,
    )
    page_size = fields.Integer(default=100, required=True)
    maximum_users = fields.Integer(default=5000, required=True)
    maximum_pages = fields.Integer(default=100, required=True)
    scheduled_sync_enabled = fields.Boolean(default=False, tracking=True)
    last_successful_sync_at = fields.Datetime(readonly=True, copy=False)
    last_sync_state = fields.Selection(
        [
            ("never", "Never Run"),
            ("planned", "Dry Run Ready"),
            ("success", "Successful"),
            ("partial", "Partially Applied"),
            ("failed", "Failed"),
        ],
        default="never",
        readonly=True,
        copy=False,
    )
    last_safe_error = fields.Text(readonly=True, copy=False)

    _company_unique = models.Constraint(
        "unique(company_id)",
        "Only one active Entra identity synchronization configuration is allowed per company.",
    )

    def init(self):
        # Use raw SQL to map the old provider to the new XML ID before data files load.
        # Using ORM here causes UndefinedColumn crashes if res_users schema isn't ready.
        self.env.cr.execute("""
            SELECT res_id FROM ir_model_data 
            WHERE module = 'lhi_integration' AND name = 'provider_microsoft_entra'
            ORDER BY id DESC LIMIT 1
        """)
        row = self.env.cr.fetchone()
        if row:
            provider_id = row[0]
            self.env.cr.execute("""
                SELECT 1 FROM ir_model_data 
                WHERE module = 'lhi_entra_identity_sync' AND name = 'oauth_provider_microsoft_entra'
            """)
            if not self.env.cr.fetchone():
                self.env.cr.execute("""
                    INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                    VALUES ('lhi_entra_identity_sync', 'oauth_provider_microsoft_entra', 'auth.oauth.provider', %s, true)
                """, (provider_id,))

    @api.model
    def _ensure_oauth_provider_xmlid(self):
        return self.env.ref("lhi_entra_identity_sync.oauth_provider_microsoft_entra", raise_if_not_found=False)

    @api.model
    def _configure_interactive_oauth_provider(self, provider=None):
        provider = provider or self._ensure_oauth_provider_xmlid()
        if not provider:
            raise UserError(_("The Microsoft Entra OAuth provider record is missing."))
        obsolete_provider = self.env.ref("lhi_integration.provider_microsoft_entra", raise_if_not_found=False)
        if obsolete_provider and obsolete_provider != provider:
            obsolete_provider.sudo().write({"enabled": False})
        tenant_id = (os.environ.get("ENTRA_TENANT_ID") or DEFAULT_ENTRA_TENANT_ID).strip()
        client_id = (os.environ.get("ENTRA_CLIENT_ID") or DEFAULT_ENTRA_CLIENT_ID).strip()
        try:
            uuid.UUID(tenant_id)
            uuid.UUID(client_id)
        except (ValueError, AttributeError, TypeError) as error:
            raise UserError(
                _("Microsoft Entra Tenant ID and Client ID must be valid UUIDs.")
            ) from error
        if "PLACEHOLDER" in client_id.upper():
            raise UserError(_("Microsoft Entra Client ID still contains a placeholder value."))
        values = {
            "name": "Microsoft Entra ID",
            "client_id": client_id,
            "auth_endpoint": (
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
            ),
            "validation_endpoint": "https://graph.microsoft.com/oidc/userinfo",
            "data_endpoint": False,
            "scope": "openid profile email User.Read",
            "body": "Sign in with Microsoft",
            "enabled": True,
        }
        if "css_class" in provider._fields:
            values["css_class"] = "fa fa-windows"
        provider.sudo().write(values)
        self.env["ir.config_parameter"].sudo().set_param(
            "auth_oauth.authorization_header", "1"
        )
        return provider

    def action_test_microsoft_login_configuration(self):
        self.ensure_one()
        results = []
        provider = self.env.ref("lhi_entra_identity_sync.oauth_provider_microsoft_entra", raise_if_not_found=False)
        if provider:
            results.append("Canonical provider found: Yes")
        else:
            results.append("Canonical provider found: No")
            raise UserError("\n".join(results) + "\n\nTest failed. Canonical provider is missing.")

        results.append(f"Provider enabled: {'Yes' if provider.enabled else 'No'}")
        
        expected_client = (os.environ.get("ENTRA_CLIENT_ID") or DEFAULT_ENTRA_CLIENT_ID).strip()
        actual_client = (provider.client_id or "").strip()
        client_valid = actual_client and actual_client == expected_client and "PLACEHOLDER" not in actual_client.upper()
        results.append(f"Client ID valid: {'Yes' if client_valid else 'No'}")

        tenant_id = (os.environ.get("ENTRA_TENANT_ID") or DEFAULT_ENTRA_TENANT_ID).strip()
        expected_auth_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
        actual_auth_endpoint = (provider.auth_endpoint or "").strip().rstrip("/")
        tenant_valid = actual_auth_endpoint == expected_auth_endpoint
        results.append(f"Tenant endpoint valid: {'Yes' if tenant_valid else 'No'}")

        expected_validation = "https://graph.microsoft.com/oidc/userinfo"
        actual_validation = (provider.validation_endpoint or "").strip().rstrip("/")
        validation_valid = actual_validation == expected_validation
        results.append(f"Validation endpoint valid: {'Yes' if validation_valid else 'No'}")

        actual_scope = (provider.scope or "").strip()
        expected_scopes = {"openid", "profile", "email", "User.Read"}
        # Ensure at least openid, profile, email are there
        scope_valid = all(s in actual_scope for s in ["openid", "profile", "email"])
        results.append(f"Scope valid: {'Yes' if scope_valid else 'No'}")

        try:
            auth_link = request.env["auth.oauth.provider"].sudo()._get_auth_link(provider.id)
            results.append("Generated auth_link: Yes")
        except Exception:
            auth_link = False
            results.append("Generated auth_link: No")

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        redirect_uri = f"{base_url}/auth_oauth/signin"
        results.append(f"Redirect URI generated: {redirect_uri}")

        message = "\n".join(results)
        if not (provider.enabled and client_valid and tenant_valid and validation_valid and scope_valid and auth_link):
            raise UserError(f"{message}\n\nConfiguration validation failed. Check exact failed condition.")
        else:
            raise UserError(f"{message}\n\nConfiguration is valid and auth_link is successfully generated.")

    @api.constrains("page_size", "maximum_users", "maximum_pages")
    def _check_operational_bounds(self):
        for record in self:
            if not 1 <= record.page_size <= 999:
                raise ValidationError(_("The Graph user page size must be between 1 and 999."))
            if not 1 <= record.maximum_users <= 100000:
                raise ValidationError(_("The maximum user count must be between 1 and 100,000."))
            if not 1 <= record.maximum_pages <= 1000:
                raise ValidationError(_("The maximum page count must be between 1 and 1,000."))

    @api.constrains("user_scope_mode", "entra_scope_group_object_id")
    def _check_user_scope(self):
        for record in self:
            if record.user_scope_mode == "entra_group":
                try:
                    uuid.UUID(record.entra_scope_group_object_id or "")
                except (ValueError, AttributeError, TypeError) as error:
                    raise ValidationError(
                        _("Approved Entra scope group mode requires a valid group UUID.")
                    ) from error

    @api.model
    def _get_for_company(self, company=None, required=False):
        company = company or self.env.company
        config = self.sudo().search(
            [("active", "=", True), ("company_id", "=", company.id)],
            limit=1,
        )
        if required and not config:
            raise UserError(_("No active Entra identity synchronization configuration exists."))
        return config

    def _check_admin(self):
        if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            raise AccessError(_("Only LHI ERP administrators may change Entra synchronization."))

    def _maintenance_administrators(self):
        self.ensure_one()
        return self.env["res.users"].sudo().with_context(active_test=False).search(
            [
                ("active", "=", True),
                ("lhi_local_maintenance_admin", "=", True),
                ("company_ids", "in", self.company_id.id),
            ]
        )

    def _check_maintenance_readiness(self):
        self.ensure_one()
        environment = os.environ.get("LHI_ENVIRONMENT", "development").lower()
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).rstrip("/")
        if environment == "production" and base_url != "https://work.lhinigeria.org":
            raise UserError(
                _(
                    "Production Entra activation requires web.base.url to be "
                    "https://work.lhinigeria.org."
                )
            )
        administrators = self._maintenance_administrators()
        if len(administrators) < 2:
            raise UserError(
                _(
                    "Designate and verify at least two active protected local maintenance "
                    "administrator accounts before enabling write sync or primary Entra login."
                )
            )
        for user in administrators:
            if not (
                user.has_group("lhi_security.group_lhi_erp_admin")
                and user.has_group("base.group_system")
            ):
                raise UserError(
                    _("Every maintenance administrator must retain ERP and Settings administration.")
                )
        if not os.environ.get("LHI_ENTRA_MAINTENANCE_ALLOWED_CIDRS"):
            raise UserError(
                _(
                    "LHI_ENTRA_MAINTENANCE_ALLOWED_CIDRS must be configured before "
                    "maintenance login can be used."
                )
            )
        return administrators

    def action_configure_oauth_provider(self):
        self.ensure_one()
        self._check_admin()
        tenant_id = self.connection_id._effective_tenant_id()
        client_id = self.connection_id._effective_client_id()
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).rstrip("/")
        expected_redirect_uri = f"{base_url}/auth_oauth/signin"
        configured_redirect_uri = os.environ.get("ENTRA_REDIRECT_URI")
        if configured_redirect_uri and configured_redirect_uri != expected_redirect_uri:
            raise UserError(
                _(
                    "ENTRA_REDIRECT_URI does not match Odoo's implemented "
                    "/auth_oauth/signin callback."
                )
            )
        provider = self.oauth_provider_id
        provider_values = {
                "name": "Microsoft Entra ID",
                "client_id": client_id,
                "auth_endpoint": (
                    f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
                ),
                "scope": "openid profile email User.Read",
                "validation_endpoint": "https://graph.microsoft.com/oidc/userinfo",
                "data_endpoint": False,
                "enabled": True,
                "body": "Sign in with Microsoft",
            }
        if "css_class" in provider._fields:
            provider_values["css_class"] = "fa fa-fw fa-windows"
        provider.write(provider_values)
        self.env["ir.config_parameter"].sudo().set_param("auth_oauth.authorization_header", "1")
        self.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://work.lhinigeria.org"
        )
        self.env["ir.config_parameter"].sudo().set_param("web.base.url.freeze", "True")
        self.env["lhi.audit.log"].create_event(
            event_type="write_sensitive_field",
            res_model=self._name,
            res_id=self.id,
            description=_("Tenant-scoped Microsoft Entra OAuth provider configured."),
        )
        return True

    def action_run_dry_sync(self):
        self.ensure_one()
        self._check_admin()
        return self.env["lhi.entra.sync.run"].create_and_execute(
            configuration=self,
            apply=False,
            source="manual",
        ).get_form_action()

    def action_test_graph_connection(self):
        self.ensure_one()
        self._check_admin()
        return self.connection_id.action_test_connection()

    def action_sync_first_two_pilot_users(self):
        self.ensure_one()
        self._check_admin()
        users = self.connection_id.graph_get_all(
            "/users",
            params={"$select": "id", "$top": 2},
            auth_context="application",
            max_pages=1,
            max_items=2,
        )
        object_ids = [u.get("id") for u in users if u.get("id")]
        return self.env["lhi.entra.sync.run"].create_and_execute(
            configuration=self,
            apply=True,
            source="manual",
            entra_object_ids=object_ids,
        ).get_form_action()

    def action_run_full_sync(self):
        self.ensure_one()
        self._check_admin()
        return self.env["lhi.entra.sync.run"].create_and_execute(
            configuration=self,
            apply=True,
            source="manual",
        ).get_form_action()

    def action_enable_write_mode(self):
        self.ensure_one()
        self._check_admin()
        self._check_maintenance_readiness()
        run = self.approved_dry_run_id
        if not run or run.state != "planned" or run.blocked_count:
            raise UserError(
                _("Approve a current dry run with no blocked changes before enabling write mode.")
            )
        if run.configuration_fingerprint != run._configuration_fingerprint():
            raise UserError(
                _(
                    "Entra configuration, group mappings, protected groups, or "
                    "segregation rules changed after the approved dry run."
                )
            )
        if (
            not run.finished_at
            or run.finished_at < fields.Datetime.now() - timedelta(hours=24)
        ):
            raise UserError(_("The approved dry run is older than 24 hours. Run it again."))
        self.with_context(lhi_entra_activation=True).write({"sync_mode": "write"})
        return True

    def action_disable_write_mode(self):
        self.ensure_one()
        self._check_admin()
        self.with_context(lhi_entra_activation=True).write({"sync_mode": "dry_run"})
        return True

    def action_enable_primary_sso(self):
        self.ensure_one()
        self._check_admin()
        self._check_maintenance_readiness()
        if not self.oauth_provider_id.enabled:
            raise UserError(_("Configure and enable the tenant-scoped Entra OAuth provider first."))
        self.with_context(lhi_entra_activation=True).write(
            {"primary_sso_enabled": True}
        )
        return True

    def action_disable_primary_sso(self):
        self.ensure_one()
        self._check_admin()
        self.with_context(lhi_entra_activation=True).write(
            {"primary_sso_enabled": False}
        )
        return True

    def write(self, vals):
        if vals.get("send_invitation_emails_after_sync"):
            raise ValidationError(
                _(
                    "Automatic Entra invitation email delivery is not implemented. "
                    "Use a separately approved manual invitation process."
                )
            )
        if (
            vals.get("sync_mode") == "write"
            or vals.get("primary_sso_enabled") is True
        ) and not self.env.context.get("lhi_entra_activation"):
            raise ValidationError(
                _(
                    "Enable write synchronization and primary Entra login only through "
                    "their guarded activation actions."
                )
            )
        return super().write(vals)

    @api.model
    def cron_run_synchronization(self):
        configurations = self.sudo().search(
            [("active", "=", True), ("scheduled_sync_enabled", "=", True)]
        )
        for configuration in configurations:
            try:
                configuration = configuration.with_context(
                    no_reset_password=True,
                    mail_create_nosubscribe=True,
                    tracking_disable=True,
                    mail_notrack=True,
                    lhi_entra_automatic_sync=True,
                )
                self.env["lhi.entra.sync.run"].sudo().create_and_execute(
                    configuration=configuration,
                    apply=configuration.sync_mode == "write",
                    source="scheduled",
                )
            except Exception as error:
                safe_error = configuration.connection_id._redact_text(error)
                configuration.with_context(lhi_entra_status_write=True).write(
                    {"last_sync_state": "failed", "last_safe_error": safe_error}
                )
        return True
