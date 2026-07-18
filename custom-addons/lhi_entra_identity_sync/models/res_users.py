import logging

import requests

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    entra_object_id = fields.Char(
        string="Canonical Entra Object ID",
        index=True,
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_tenant_id = fields.Char(
        string="Entra Tenant ID",
        index=True,
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_upn = fields.Char(
        string="Entra User Principal Name",
        index=True,
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_account_enabled = fields.Boolean(
        string="Entra Account Enabled",
        default=True,
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_manager_object_id = fields.Char(
        string="Entra Manager Object ID",
        index=True,
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_manager_user_id = fields.Many2one(
        "res.users",
        compute="_compute_entra_manager_user_id",
        string="Synchronized Manager",
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_last_sync_at = fields.Datetime(
        string="Entra Last Sync",
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_sync_state = fields.Selection(
        [
            ("never", "Never Synchronized"),
            ("synced", "Synchronized"),
            ("disabled", "Disabled in Entra"),
            ("error", "Synchronization Error"),
            ("protected", "Protected Local Administrator"),
        ],
        default="never",
        required=True,
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    identity_source = fields.Selection(
        [
            ("local", "Local Odoo"),
            ("entra", "Microsoft Entra"),
            ("maintenance", "Protected Local Maintenance"),
        ],
        default="local",
        required=True,
        index=True,
        groups="lhi_security.group_lhi_erp_admin",
    )
    entra_given_name = fields.Char(
        copy=False, groups="lhi_security.group_lhi_erp_admin"
    )
    entra_family_name = fields.Char(
        copy=False, groups="lhi_security.group_lhi_erp_admin"
    )
    entra_login_blocked = fields.Boolean(
        default=False,
        copy=False,
        groups="lhi_security.group_lhi_erp_admin",
    )
    lhi_local_maintenance_admin = fields.Boolean(
        string="Protected Local Maintenance Administrator",
        default=False,
        copy=False,
        groups="base.group_system,lhi_security.group_lhi_erp_admin",
        help=(
            "Protected break-glass account. It is excluded from Entra profile, "
            "group, deactivation, password, and archive changes."
        ),
    )

    _entra_object_id_unique = models.Constraint(
        "unique(entra_object_id)",
        "The immutable Entra object ID must be unique.",
    )
    _entra_tenant_upn_unique = models.Constraint(
        "unique(entra_tenant_id, entra_upn)",
        "The Entra user principal name must be unique within its tenant.",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "identity_source",
            "entra_upn",
            "entra_account_enabled",
            "entra_login_blocked",
        ]

    @api.depends("entra_manager_object_id")
    def _compute_entra_manager_user_id(self):
        object_ids = list(filter(None, self.mapped("entra_manager_object_id")))
        managers = self.sudo().with_context(active_test=False).search(
            [
                "|",
                ("entra_object_id", "in", object_ids),
                ("lhi_entra_object_id", "in", object_ids),
            ]
        )
        by_object_id = {}
        for manager in managers:
            by_object_id[manager.entra_object_id or manager.lhi_entra_object_id] = manager
        for user in self:
            user.entra_manager_user_id = by_object_id.get(
                user.entra_manager_object_id
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("entra_object_id") and not vals.get("lhi_entra_object_id"):
                vals["lhi_entra_object_id"] = vals["entra_object_id"]
            if vals.get("lhi_entra_object_id") and not vals.get("entra_object_id"):
                vals["entra_object_id"] = vals["lhi_entra_object_id"]
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("entra_object_id") and "lhi_entra_object_id" not in vals:
            vals["lhi_entra_object_id"] = vals["entra_object_id"]
        if vals.get("lhi_entra_object_id") and "entra_object_id" not in vals:
            vals["entra_object_id"] = vals["lhi_entra_object_id"]
        if "lhi_local_maintenance_admin" in vals:
            self._check_maintenance_admin_change(vals["lhi_local_maintenance_admin"])
        if self.env.context.get("lhi_entra_sync"):
            if not self.env.context.get("lhi_entra_rollback"):
                protected_users = self.filtered(
                    lambda user: user._lhi_is_protected_entra_user()
                )
                if protected_users:
                    raise AccessError(
                        _(
                            "Protected administrators cannot be modified by Entra synchronization."
                        )
                    )
            self._check_entra_group_commands(vals.get("group_ids"))
        result = super().write(vals)
        if "lhi_local_maintenance_admin" in vals:
            for user in self:
                self.env["lhi.audit.log"].create_event(
                    event_type="permission_change",
                    res_model=self._name,
                    res_id=user.id,
                    description=_(
                        "Protected local maintenance administrator status changed to %s."
                    )
                    % vals["lhi_local_maintenance_admin"],
                )
        return result

    def _check_maintenance_admin_change(self, target_value):
        if not (
            self.env.user.has_group("lhi_security.group_lhi_erp_admin")
            and self.env.user.has_group("base.group_system")
        ):
            raise AccessError(
                _("Only an ERP and Settings administrator may classify maintenance accounts.")
            )
        if target_value:
            for user in self:
                if not (
                    user.has_group("lhi_security.group_lhi_erp_admin")
                    and user.has_group("base.group_system")
                ):
                    raise ValidationError(
                        _("A maintenance account must already be an ERP and Settings administrator.")
                    )
        else:
            for user in self.filtered("lhi_local_maintenance_admin"):
                configurations = self.env["lhi.entra.configuration"].sudo().search(
                    [
                        ("company_id", "in", user.company_ids.ids),
                        "|",
                        ("primary_sso_enabled", "=", True),
                        ("sync_mode", "=", "write"),
                    ]
                )
                for configuration in configurations:
                    remaining = configuration._maintenance_administrators() - user
                    if len(remaining) < 2:
                        raise ValidationError(
                            _(
                                "Disable primary Entra login and write synchronization "
                                "before reducing protected maintenance accounts below two."
                            )
                        )

    def _check_entra_group_commands(self, commands):
        if not commands:
            return
        protected_ids = set(
            self.env["res.groups"]._lhi_entra_protected_groups().ids
        )
        for command in commands:
            operation = command[0]
            if operation in (3, 4) and command[1] in protected_ids:
                raise AccessError(_("Entra synchronization cannot mutate protected groups."))
            if operation == 6 and protected_ids.intersection(command[2]):
                raise AccessError(
                    _("Entra synchronization cannot replace protected group memberships.")
                )

    def _lhi_is_protected_entra_user(self):
        self.ensure_one()
        if self.id == SUPERUSER_ID or self.lhi_local_maintenance_admin:
            return True
        protected = self.env["res.groups"]._lhi_entra_protected_groups()
        return bool(self.all_group_ids & protected)

    @api.model
    def _auth_oauth_validate(self, provider, access_token):
        """Keep native validation, then obtain the immutable Graph object ID.

        The access token is used only for this bounded server-side request. It is
        never logged, returned to custom JavaScript, or written by this method.
        """
        validation = super()._auth_oauth_validate(provider, access_token)
        configuration = self.env["lhi.entra.configuration"]._get_for_company(
            required=False
        )
        if not configuration or configuration.oauth_provider_id.id != provider:
            return validation
        try:
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                params={
                    "$select": (
                        "id,userPrincipalName,mail,displayName,accountEnabled"
                    )
                },
                headers={"Authorization": "Bearer %s" % access_token},
                timeout=15,
            )
            response.raise_for_status()
            profile = response.json()
        except (requests.RequestException, ValueError):
            _logger.warning(
                "Entra OAuth Graph profile validation failed",
                extra={"lhi_stage": "oauth_graph_me", "lhi_result": "denied"},
            )
            raise AccessDenied(
                _(
                    "Your Microsoft account was authenticated, but you are not "
                    "currently authorized to access LHI ERP. Contact the LHI IT Helpdesk."
                )
            )
        object_id = profile.get("id")
        if not object_id or profile.get("accountEnabled") is False:
            raise AccessDenied()
        expected_tenant = configuration.connection_id._effective_tenant_id().casefold()
        token_tenant = (validation.get("tid") or "").casefold()
        if token_tenant and token_tenant != expected_tenant:
            raise AccessDenied()
        validation.update(profile)
        validation["user_id"] = object_id
        validation["lhi_tenant_id"] = expected_tenant
        return validation

    @api.model
    def _auth_oauth_signin(self, provider, validation, params):
        configuration = self.env["lhi.entra.configuration"]._get_for_company(
            required=False
        )
        if not configuration or configuration.oauth_provider_id.id != provider:
            return super()._auth_oauth_signin(provider, validation, params)
        # Existing provider/UID links stay entirely on Odoo's native path.
        try:
            login = super(
                ResUsers, self.with_context(no_user_creation=True)
            )._auth_oauth_signin(provider, validation, params)
            if login:
                return login
        except AccessDenied:
            pass
        object_id = validation.get("user_id")
        if not object_id:
            raise AccessDenied()
        users = self.sudo().with_context(active_test=False)
        user = users.search(
            [
                "|",
                ("entra_object_id", "=", object_id),
                ("lhi_entra_object_id", "=", object_id),
            ],
            limit=2,
        )
        match_method = "object_id"
        if not user and configuration.allow_controlled_first_match:
            identities = {
                value.strip().casefold()
                for value in (
                    validation.get("userPrincipalName"),
                    validation.get("mail"),
                    validation.get("email"),
                )
                if value and value.strip()
            }
            candidates = users.browse()
            for identity in identities:
                candidates |= users.search(
                    [
                        "|",
                        ("login", "=ilike", identity),
                        ("email", "=ilike", identity),
                    ],
                    limit=3,
                )
            candidates = candidates.filtered(
                lambda record: {
                    (record.login or "").strip().casefold(),
                    (record.email or "").strip().casefold(),
                }
                & identities
            )
            if len(candidates) == 1 and not candidates._lhi_is_protected_entra_user():
                user = candidates
                match_method = "controlled_email"
        if len(user) != 1 or user._lhi_is_protected_entra_user():
            raise AccessDenied(
                _("This Entra identity is not uniquely provisioned for Odoo login.")
            )
        if (
            user.entra_login_blocked
            or user.entra_account_enabled is False
            or validation.get("accountEnabled") is False
            or not user.active
        ):
            raise AccessDenied(_("This Entra account is disabled for Odoo login."))
        expected_tenant = configuration.connection_id._effective_tenant_id()
        if (
            validation.get("lhi_tenant_id")
            and validation["lhi_tenant_id"].casefold() != expected_tenant.casefold()
        ):
            raise AccessDenied()
        if user.entra_tenant_id and user.entra_tenant_id.casefold() != expected_tenant.casefold():
            raise AccessDenied()
        if not user.has_group("lhi_security.group_lhi_user"):
            raise AccessDenied()
        user.with_context(lhi_entra_login_binding=True).write(
            {
                "oauth_provider_id": provider,
                "oauth_uid": object_id,
                "oauth_access_token": params["access_token"],
                "entra_object_id": object_id,
                "lhi_entra_object_id": object_id,
                "entra_tenant_id": configuration.connection_id._effective_tenant_id(),
                "entra_upn": validation.get("userPrincipalName")
                or validation.get("mail")
                or user.entra_upn,
                "identity_source": "entra",
                "entra_account_enabled": validation.get("accountEnabled", True),
                "entra_login_blocked": False,
            }
        )
        _logger.info(
            "Entra OAuth identity bound to Odoo user ID %s using %s",
            user.id,
            match_method,
        )
        self.env["lhi.audit.log"].sudo().create_event(
            event_type="identity_link",
            res_model="res.users",
            res_id=user.id,
            description=_("Microsoft Entra identity linked after native OAuth validation."),
        )
        return user.login

    def _check_credentials(self, credential, env):
        if self.entra_login_blocked or (
            self.identity_source == "entra" and self.entra_account_enabled is False
        ):
            raise AccessDenied(_("This Entra identity is disabled."))
        configuration = self.env["lhi.entra.configuration"]._get_for_company(
            company=self.company_id,
            required=False,
        )
        if (
            credential.get("type") == "password"
            and self._is_internal()
            and not self.lhi_local_maintenance_admin
            and (
                self.identity_source == "entra"
                or (configuration and configuration.primary_sso_enabled)
            )
        ):
            raise AccessDenied(_("Use Microsoft Entra ID to sign in."))
        return super()._check_credentials(credential, env)

    def _lhi_queue_entra_profile_sync(self):
        configuration = self.env["lhi.entra.configuration"]._get_for_company(
            required=False
        )
        if not configuration:
            return False
        for user in self.filtered("entra_object_id"):
            key = "entra-login:%s:%s" % (
                user.entra_object_id,
                fields.Datetime.now().strftime("%Y%m%d%H"),
            )
            job_model = self.env["lhi.integration.job"].sudo()
            existing = job_model.search(
                [
                    ("model_name", "=", self._name),
                    ("record_id", "=", user.id),
                    ("action", "=", "sync_entra_profile"),
                    ("state", "in", ("pending", "running", "failed")),
                ],
                limit=1,
            )
            if not existing:
                job_model.create_job(
                    model_name=self._name,
                    record_id=user.id,
                    action="sync_entra_profile",
                    description=_("Post-login Entra profile reconciliation (%s).") % key,
                )
        return True

    def action_sync_entra_profile(self):
        for company, users in self.filtered("entra_object_id").grouped(
            lambda user: user.company_id
        ).items():
            configuration = self.env[
                "lhi.entra.configuration"
            ]._get_for_company(company=company, required=True)
            object_ids = users.mapped("entra_object_id")
            self.env["lhi.entra.sync.run"].sudo().create_and_execute(
                configuration=configuration,
                apply=configuration.sync_mode == "write",
                source="login",
                entra_object_ids=object_ids,
                idempotency_key="entra-login-run:%s:%s"
                % (
                    ",".join(sorted(object_ids)),
                    fields.Datetime.now().strftime("%Y%m%d%H"),
                ),
            )
        return True
