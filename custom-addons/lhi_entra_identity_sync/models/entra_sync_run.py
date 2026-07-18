import hashlib
import json
import logging
import uuid
from datetime import timedelta
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)

USER_SELECT = (
    "id,accountEnabled,businessPhones,department,displayName,givenName,"
    "jobTitle,mail,mobilePhone,officeLocation,surname,userPrincipalName,"
    "employeeId,userType,createdDateTime"
)


def _stable_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


class LhiEntraSyncRun(models.Model):
    _name = "lhi.entra.sync.run"
    _description = "Entra Identity Synchronization Run"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, readonly=True, copy=False)
    run_uuid = fields.Char(required=True, readonly=True, copy=False, index=True)
    idempotency_key = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, readonly=True
    )
    configuration_id = fields.Many2one(
        "lhi.entra.configuration",
        required=True,
        ondelete="restrict",
        readonly=True,
    )
    connection_id = fields.Many2one(
        related="configuration_id.connection_id",
        store=True,
        readonly=True,
    )
    source = fields.Selection(
        [
            ("manual", "Manual"),
            ("scheduled", "Scheduled"),
            ("login", "Post-login Queue"),
            ("retry", "Failure Retry"),
        ],
        required=True,
        readonly=True,
    )
    apply_requested = fields.Boolean(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("planned", "Dry Run Ready"),
            ("applied", "Applied"),
            ("partial", "Partially Applied"),
            ("failed", "Failed"),
            ("rolled_back", "Rolled Back"),
        ],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
    )
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    requested_by_id = fields.Many2one(
        "res.users",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    graph_user_count = fields.Integer(readonly=True)
    planned_user_count = fields.Integer(readonly=True)
    applied_user_count = fields.Integer(readonly=True)
    blocked_count = fields.Integer(readonly=True)
    conflict_count = fields.Integer(readonly=True)
    missing_mapping_count = fields.Integer(readonly=True)
    missing_manager_count = fields.Integer(readonly=True)
    retry_count = fields.Integer(default=0, readonly=True)
    max_retries = fields.Integer(default=5, readonly=True)
    next_retry_at = fields.Datetime(readonly=True)
    safe_error = fields.Text(readonly=True)
    plan_hash = fields.Char(readonly=True, copy=False)
    configuration_fingerprint = fields.Char(readonly=True, copy=False)
    rollback_at = fields.Datetime(readonly=True)
    rollback_by_id = fields.Many2one("res.users", readonly=True)
    plan_ids = fields.One2many("lhi.entra.sync.plan", "run_id", readonly=True)
    finding_ids = fields.One2many("lhi.entra.sync.finding", "run_id", readonly=True)
    snapshot_ids = fields.One2many(
        "lhi.entra.sync.snapshot", "run_id", readonly=True
    )

    _run_uuid_unique = models.Constraint(
        "unique(run_uuid)", "The Entra synchronization run UUID must be unique."
    )
    _idempotency_unique = models.Constraint(
        "unique(idempotency_key)",
        "The Entra synchronization idempotency key must be unique.",
    )

    @api.model
    def create_and_execute(
        self,
        *,
        configuration,
        apply=False,
        source="manual",
        entra_object_ids=None,
        idempotency_key=None,
    ):
        configuration.ensure_one()
        if apply and configuration.sync_mode != "write":
            raise UserError(_("Entra synchronization write mode is not enabled."))
        if source == "scheduled":
            slot = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
            idempotency_key = idempotency_key or (
                f"entra:{configuration.id}:{'write' if apply else 'dry'}:{slot.isoformat()}"
            )
        else:
            idempotency_key = idempotency_key or f"entra:{uuid.uuid4()}"
        existing = self.sudo().search(
            [("idempotency_key", "=", idempotency_key)], limit=1
        )
        if existing:
            return existing
        run_uuid = str(uuid.uuid4())
        run = self.sudo().create(
            {
                "name": _("Entra Sync %s") % run_uuid[:8],
                "run_uuid": run_uuid,
                "idempotency_key": idempotency_key,
                "company_id": configuration.company_id.id,
                "configuration_id": configuration.id,
                "source": source,
                "apply_requested": apply,
                "requested_by_id": self.env.user.id,
            }
        )
        run._execute(entra_object_ids=entra_object_ids)
        return run

    def get_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _status_write(self, vals):
        return super(LhiEntraSyncRun, self.sudo()).write(vals)

    def _execute(self, entra_object_ids=None):
        self.ensure_one()
        if self.state not in ("draft", "failed"):
            return self
        self._status_write(
            {
                "state": "running",
                "started_at": fields.Datetime.now(),
                "safe_error": False,
                "next_retry_at": False,
            }
        )
        try:
            remote_users = self._fetch_remote_users(entra_object_ids=entra_object_ids)
            self._status_write({"graph_user_count": len(remote_users)})
            for remote_user in remote_users:
                self._plan_remote_user(remote_user)
            self._finalize_plan()
            if self.apply_requested:
                self._apply_plans()
            return self
        except Exception as error:
            _logger.exception("Entra identity synchronization run %s failed", self.run_uuid)
            retry_count = self.retry_count + 1
            self._status_write(
                {
                    "state": "failed",
                    "finished_at": fields.Datetime.now(),
                    "retry_count": retry_count,
                    "next_retry_at": fields.Datetime.now()
                    + timedelta(minutes=min(15 * (2 ** (retry_count - 1)), 24 * 60)),
                    "safe_error": self.connection_id._redact_text(error),
                }
            )
            self.configuration_id.sudo().write(
                {
                    "last_sync_state": "failed",
                    "last_safe_error": self.connection_id._redact_text(error),
                }
            )
            return self

    def _fetch_remote_users(self, entra_object_ids=None):
        self.ensure_one()
        connection = self.connection_id
        if entra_object_ids:
            users = []
            for object_id in dict.fromkeys(entra_object_ids):
                payload = connection.graph_request(
                    "GET",
                    f"/users/{quote(object_id, safe='')}",
                    params={"$select": USER_SELECT},
                    auth_context="application",
                )
                users.append(payload)
            return users
        configuration = self.configuration_id
        if configuration.user_scope_mode == "existing_users":
            local_users = (
                self.env["res.users"]
                .sudo()
                .with_context(active_test=False)
                .search(
                    [
                        ("company_ids", "in", self.company_id.id),
                        "|",
                        ("entra_object_id", "!=", False),
                        ("lhi_entra_object_id", "!=", False),
                    ],
                    limit=configuration.maximum_users + 1,
                )
            )
            if len(local_users) > configuration.maximum_users:
                raise UserError(
                    _(
                        "The number of existing Entra-linked Odoo users exceeds the "
                        "configured maximum. Increase the reviewed bound or narrow the scope."
                    )
                )
            users = []
            for user in local_users:
                object_id = user.entra_object_id or user.lhi_entra_object_id
                users.append(
                    connection.graph_request(
                        "GET",
                        f"/users/{quote(object_id, safe='')}",
                        params={"$select": USER_SELECT},
                        auth_context="application",
                    )
                )
            return users
        if configuration.user_scope_mode == "entra_group":
            resource = (
                f"/groups/{quote(configuration.entra_scope_group_object_id, safe='')}"
                "/transitiveMembers/microsoft.graph.user"
            )
        else:
            resource = "/users"
        return connection.graph_get_all(
            resource,
            params={
                "$select": USER_SELECT,
                "$top": self.configuration_id.page_size,
            },
            auth_context="application",
            max_pages=self.configuration_id.maximum_pages,
            max_items=self.configuration_id.maximum_users,
        )

    def _find_local_user(self, remote):
        object_id = remote.get("id")
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        user = Users.search(
            [
                "|",
                ("entra_object_id", "=", object_id),
                ("lhi_entra_object_id", "=", object_id),
            ],
            limit=2,
        )
        if len(user) == 1:
            return user, "object_id"
        if len(user) > 1:
            return Users, "duplicate_object_id"
        config = self.configuration_id
        if not config.allow_controlled_first_match:
            return Users, "not_found"
        candidates = {
            value.strip().casefold()
            for value in (remote.get("userPrincipalName"), remote.get("mail"))
            if value and value.strip()
        }
        if not candidates:
            return Users, "not_found"
        possible = Users.browse()
        for candidate in candidates:
            possible |= Users.search(
                [
                    "|",
                    ("login", "=ilike", candidate),
                    ("email", "=ilike", candidate),
                ],
                limit=3,
            )
        possible = possible.filtered(
            lambda record: {
                (record.login or "").strip().casefold(),
                (record.email or "").strip().casefold(),
            }
            & candidates
        )
        if len(possible) == 1 and not possible._lhi_is_protected_entra_user():
            return possible, "controlled_email"
        return Users, "ambiguous_email" if possible else "not_found"

    def _mapped_membership_ids(self, object_id, mappings):
        result = set()
        group_ids = mappings.mapped("entra_group_object_id")
        for start in range(0, len(group_ids), 20):
            chunk = group_ids[start : start + 20]
            payload = self.connection_id.graph_request(
                "POST",
                f"/users/{quote(object_id, safe='')}/checkMemberGroups",
                auth_context="application",
                json_body={"groupIds": chunk},
            )
            values = payload.get("value", [])
            if not isinstance(values, list):
                raise UserError(_("Microsoft Graph returned malformed group membership data."))
            result.update(values)
        return result

    def _manager_object_id(self, object_id):
        payload = self.connection_id.graph_request(
            "GET",
            f"/users/{quote(object_id, safe='')}/manager",
            auth_context="application",
            params={"$select": "id,displayName,userPrincipalName"},
            expected_statuses={200, 404},
        )
        return payload.get("id")

    def _find_named_master_data(self, model_name, value):
        if not value:
            return self.env[model_name]
        records = (
            self.env[model_name]
            .sudo()
            .with_context(active_test=False)
            .search([("company_id", "=", self.company_id.id)])
            .filtered(lambda record: (record.name or "").strip().casefold() == value.strip().casefold())
        )
        return records if len(records) == 1 else self.env[model_name]

    def _plan_remote_user(self, remote):
        self.ensure_one()
        object_id = remote.get("id")
        if not object_id:
            self._finding(
                category="block",
                severity="error",
                message=_("Microsoft Graph returned a user without an immutable object ID."),
            )
            return
        user, match_method = self._find_local_user(remote)
        create_user = (
            not user
            and match_method == "not_found"
            and self.configuration_id.create_missing_users
        )
        if not user and not create_user:
            self._finding(
                category="block",
                severity="warning",
                entra_object_id=object_id,
                entra_upn=remote.get("userPrincipalName"),
                message=_("No unique existing Odoo user matches this Entra identity (%s).")
                % match_method,
            )
            return
        if user and user._lhi_is_protected_entra_user():
            self._finding(
                category="preserve",
                severity="info",
                user=user,
                entra_object_id=object_id,
                entra_upn=remote.get("userPrincipalName"),
                message=_("Protected administrator preserved without automatic changes."),
            )
            return

        mappings = self.env["lhi.entra.group.mapping"].sudo().search(
            [
                ("enabled", "=", True),
                ("company_id", "=", self.company_id.id),
                ("connection_id", "=", self.connection_id.id),
            ],
            order="priority, id",
        )
        membership_ids = self._mapped_membership_ids(object_id, mappings)
        manager_object_id = self._manager_object_id(object_id)
        current_group_ids = set(user.group_ids.ids) if user else set()
        add_ids = set()
        remove_ids = set()

        protected_groups = self.env["res.groups"]._lhi_entra_protected_groups()
        for mapping in mappings:
            remote_member = mapping.entra_group_object_id in membership_ids
            current_member = mapping.odoo_group_id.id in current_group_ids
            if mapping.management_mode == "protected" or mapping.odoo_group_id in protected_groups:
                category = "block" if remote_member and not current_member else "preserve"
                self._finding(
                    category=category,
                    severity="warning" if category == "block" else "info",
                    user=user,
                    mapping=mapping,
                    entra_object_id=object_id,
                    entra_upn=remote.get("userPrincipalName"),
                    message=_("Protected group membership cannot be granted or removed by Entra."),
                )
                continue
            if mapping.management_mode == "odoo":
                if current_member or remote_member:
                    self._finding(
                        category="preserve",
                        severity="info",
                        user=user,
                        mapping=mapping,
                        entra_object_id=object_id,
                        entra_upn=remote.get("userPrincipalName"),
                        message=_("Odoo-managed membership preserved."),
                    )
                continue
            if remote_member and not current_member:
                add_ids.add(mapping.odoo_group_id.id)
                self._finding(
                    category="add",
                    severity="info",
                    user=user,
                    mapping=mapping,
                    entra_object_id=object_id,
                    entra_upn=remote.get("userPrincipalName"),
                    message=_("Mapped existing Odoo group would be added."),
                )
            elif (
                not remote_member
                and current_member
                and mapping.management_mode == "entra"
            ):
                remove_ids.add(mapping.odoo_group_id.id)
                self._finding(
                    category="remove",
                    severity="info",
                    user=user,
                    mapping=mapping,
                    entra_object_id=object_id,
                    entra_upn=remote.get("userPrincipalName"),
                    message=_("Entra-managed existing Odoo group would be removed."),
                )

        add_ids, sod_blocked = self._filter_sod_conflicts(
            user, current_group_ids, add_ids, remove_ids
        )
        employee = user.employee_id if user else self.env["hr.employee"]
        employee_vals = {}
        if employee:
            employee_vals = {
                "name": remote.get("displayName") or user.name,
                "job_title": remote.get("jobTitle") or False,
                "work_email": remote.get("mail")
                or remote.get("userPrincipalName")
                or False,
                "work_phone": (remote.get("businessPhones") or [False])[0],
                "mobile_phone": remote.get("mobilePhone") or False,
            }
        elif user and self.configuration_id.create_missing_employee:
            employee_vals = {
                "_create": True,
                "name": remote.get("displayName") or user.name,
                "user_id": user.id,
                "company_id": self.company_id.id,
                "job_title": remote.get("jobTitle") or False,
                "work_email": remote.get("mail")
                or remote.get("userPrincipalName")
                or False,
                "work_phone": (remote.get("businessPhones") or [False])[0],
                "mobile_phone": remote.get("mobilePhone") or False,
            }
        elif user:
            self._finding(
                category="block",
                severity="warning",
                user=user,
                entra_object_id=object_id,
                entra_upn=remote.get("userPrincipalName"),
                message=_("No linked employee exists; employee profile fields were not planned."),
            )

        manager_user = self.env["res.users"]
        if manager_object_id:
            manager_user = (
                self.env["res.users"]
                .sudo()
                .with_context(active_test=False)
                .search(
                    [
                        "|",
                        ("entra_object_id", "=", manager_object_id),
                        ("lhi_entra_object_id", "=", manager_object_id),
                    ],
                    limit=1,
                )
            )
            if not manager_user or not manager_user.employee_id:
                self._finding(
                    category="missing_manager",
                    severity="warning",
                    user=user,
                    entra_object_id=object_id,
                    entra_upn=remote.get("userPrincipalName"),
                    message=_("The Entra manager is not mapped to an Odoo employee."),
                )
            elif employee_vals:
                employee_vals["parent_id"] = manager_user.employee_id.id
        else:
            self._finding(
                category="missing_manager",
                severity="info",
                user=user,
                entra_object_id=object_id,
                entra_upn=remote.get("userPrincipalName"),
                message=_("No manager is assigned to this Entra user."),
            )

        department = self._find_named_master_data(
            "lhi.department", remote.get("department")
        )
        office = self._find_named_master_data(
            "lhi.office", remote.get("officeLocation")
        )
        organizational_vals = {}
        if self.configuration_id.sync_organizational_scope:
            if remote.get("department"):
                if department:
                    organizational_vals["department_ids"] = department.ids
                else:
                    self._finding(
                        category="missing_mapping",
                        severity="warning",
                        user=user,
                        entra_object_id=object_id,
                        entra_upn=remote.get("userPrincipalName"),
                        message=_("Entra department does not uniquely match existing LHI master data: %s")
                        % remote.get("department"),
                    )
            if remote.get("officeLocation"):
                if office:
                    organizational_vals["office_ids"] = office.ids
                else:
                    self._finding(
                        category="missing_mapping",
                        severity="warning",
                        user=user,
                        entra_object_id=object_id,
                        entra_upn=remote.get("userPrincipalName"),
                        message=_("Entra office does not uniquely match existing LHI master data: %s")
                        % remote.get("officeLocation"),
                    )

        account_enabled = remote.get("accountEnabled") is not False
        user_vals = {
            "entra_object_id": object_id,
            "lhi_entra_object_id": object_id,
            "entra_tenant_id": self.connection_id._effective_tenant_id(),
            "entra_upn": remote.get("userPrincipalName") or False,
            "entra_account_enabled": account_enabled,
            "entra_manager_object_id": manager_object_id or False,
            "entra_last_sync_at": fields.Datetime.now(),
            "entra_sync_state": "synced" if account_enabled else "disabled",
            "identity_source": "entra",
            "entra_given_name": remote.get("givenName") or False,
            "entra_family_name": remote.get("surname") or False,
            "entra_login_blocked": not account_enabled,
            "name": remote.get("displayName")
            or (user.name if user else remote.get("userPrincipalName")),
            "email": remote.get("mail")
            or remote.get("userPrincipalName")
            or (user.email if user else False),
        }
        if create_user:
            login = remote.get("userPrincipalName") or remote.get("mail")
            if not login:
                self._finding(
                    category="block",
                    severity="error",
                    entra_object_id=object_id,
                    message=_("An Entra user without a UPN or mail value cannot be provisioned."),
                )
                return
            user_vals.update(
                {
                    "login": login.strip().casefold(),
                    "active": account_enabled,
                    "share": False,
                    "company_id": self.company_id.id,
                    "company_ids": [(6, 0, self.company_id.ids)],
                    "group_ids": [
                        (6, 0, self.env.ref("lhi_security.group_lhi_employee").ids)
                    ],
                }
            )
        if self.configuration_id.sync_login_from_upn and remote.get("userPrincipalName"):
            user_vals["login"] = remote["userPrincipalName"].strip().casefold()
        if not account_enabled and self.configuration_id.deactivation_policy == "archive":
            user_vals["active"] = False
            if employee_vals:
                employee_vals["active"] = False

        plan = {
            "match_method": "create" if create_user else match_method,
            "create_user": create_user,
            "user_vals": user_vals,
            "employee_vals": employee_vals,
            "organizational_vals": organizational_vals,
            "group_add_ids": sorted(add_ids),
            "group_remove_ids": sorted(remove_ids),
            "manager_user_id": manager_user.id if manager_user else False,
            "sod_blocked": sod_blocked,
        }
        self.env["lhi.entra.sync.plan"].sudo().create(
            {
                "run_id": self.id,
                "user_id": user.id if user else False,
                "entra_object_id": object_id,
                "entra_upn": remote.get("userPrincipalName"),
                "match_method": "create" if create_user else match_method,
                "state": "blocked" if sod_blocked else "planned",
                "plan_json": plan,
                "local_state_hash": _stable_hash(
                    self._snapshot_state(user) if user else {"missing": True}
                ),
            }
        )

    def _filter_sod_conflicts(self, user, current_ids, add_ids, remove_ids):
        candidate_ids = (current_ids - remove_ids) | add_ids
        candidate_groups = self.env["res.groups"].browse(candidate_ids)
        effective_ids = set(candidate_groups._lhi_entra_effective_groups().ids)
        rules = self.env["lhi.sod.rule"].sudo().search([("is_active", "=", True)])
        blocked_additions = set()
        for rule in rules:
            if (
                rule.group_1_id.id in effective_ids
                and rule.group_2_id.id in effective_ids
            ):
                implicated = add_ids.intersection(
                    {rule.group_1_id.id, rule.group_2_id.id}
                )
                blocked_additions.update(implicated)
                self._finding(
                    category="sod_conflict",
                    severity="error",
                    user=user,
                    entra_object_id=user.entra_object_id,
                    entra_upn=user.entra_upn,
                    message=_("Segregation-of-duties conflict blocked: %s") % rule.name,
                )
        return add_ids - blocked_additions, bool(blocked_additions)

    def _finding(
        self,
        *,
        category,
        severity,
        message,
        user=None,
        mapping=None,
        entra_object_id=None,
        entra_upn=None,
    ):
        return self.env["lhi.entra.sync.finding"].sudo().create(
            {
                "run_id": self.id,
                "category": category,
                "severity": severity,
                "user_id": user.id if user else False,
                "mapping_id": mapping.id if mapping else False,
                "entra_object_id": entra_object_id,
                "entra_upn": entra_upn,
                "message": message,
            }
        )

    def _finalize_plan(self):
        self.ensure_one()
        plans = self.plan_ids
        findings = self.finding_ids
        plan_hash = _stable_hash(
            [
                {
                    "user": plan.user_id.id,
                    "oid": plan.entra_object_id,
                    "plan": plan.plan_json,
                }
                for plan in plans.sorted("id")
            ]
        )
        vals = {
            "state": "planned",
            "finished_at": fields.Datetime.now(),
            "planned_user_count": len(plans),
            "blocked_count": len(
                findings.filtered(lambda finding: finding.category == "block")
            )
            + len(plans.filtered(lambda plan: plan.state == "blocked")),
            "conflict_count": len(
                findings.filtered(lambda finding: finding.category == "sod_conflict")
            ),
            "missing_mapping_count": len(
                findings.filtered(lambda finding: finding.category == "missing_mapping")
            ),
            "missing_manager_count": len(
                findings.filtered(lambda finding: finding.category == "missing_manager")
            ),
            "plan_hash": plan_hash,
            "configuration_fingerprint": self._configuration_fingerprint(),
        }
        self._status_write(vals)
        self.configuration_id.sudo().write(
            {
                "last_sync_state": "planned",
                "last_safe_error": False,
            }
        )

    def _configuration_fingerprint(self):
        self.ensure_one()
        configuration = self.configuration_id
        mappings = self.env["lhi.entra.group.mapping"].sudo().search(
            [
                ("company_id", "=", self.company_id.id),
                ("connection_id", "=", self.connection_id.id),
            ],
            order="id",
        )
        sod_rules = self.env["lhi.sod.rule"].sudo().search(
            [("is_active", "=", True)], order="id"
        )
        return _stable_hash(
            {
                "configuration": {
                    "connection_id": configuration.connection_id.id,
                    "allow_controlled_first_match": configuration.allow_controlled_first_match,
                    "create_missing_users": configuration.create_missing_users,
                    "sync_login_from_upn": configuration.sync_login_from_upn,
                    "sync_organizational_scope": configuration.sync_organizational_scope,
                    "create_missing_employee": configuration.create_missing_employee,
                    "deactivation_policy": configuration.deactivation_policy,
                    "user_scope_mode": configuration.user_scope_mode,
                    "entra_scope_group_object_id": configuration.entra_scope_group_object_id,
                },
                "mappings": [
                    {
                        "id": mapping.id,
                        "write_date": mapping.write_date,
                        "entra_group_object_id": mapping.entra_group_object_id,
                        "group": mapping.odoo_group_id.id,
                        "mode": mapping.management_mode,
                        "priority": mapping.priority,
                        "policy": mapping.conflict_policy,
                        "enabled": mapping.enabled,
                    }
                    for mapping in mappings
                ],
                "sod_rules": [
                    {
                        "id": rule.id,
                        "write_date": rule.write_date,
                        "group_1": rule.group_1_id.id,
                        "group_2": rule.group_2_id.id,
                    }
                    for rule in sod_rules
                ],
                "protected_groups": sorted(
                    self.env["res.groups"]._lhi_entra_protected_groups().ids
                ),
            }
        )

    def action_approve_dry_run(self):
        self.ensure_one()
        if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            raise AccessError(_("Only an LHI ERP administrator may approve a dry run."))
        if self.state != "planned" or self.blocked_count:
            raise UserError(_("Only a dry run with no blocked changes can be approved."))
        self.configuration_id.sudo().write({"approved_dry_run_id": self.id})
        return True

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            raise AccessError(_("Only an LHI ERP administrator may apply Entra changes."))
        if self.configuration_id.sync_mode != "write":
            raise UserError(_("Entra synchronization write mode is not enabled."))
        if self.state != "planned":
            raise UserError(_("Only a completed dry run can be applied."))
        if self.configuration_id.approved_dry_run_id != self:
            raise UserError(_("Approve this exact dry run before applying it."))
        if self.configuration_fingerprint != self._configuration_fingerprint():
            raise UserError(
                _(
                    "Entra configuration, group mappings, protected groups, or "
                    "segregation rules changed after planning. Run a fresh dry run."
                )
            )
        return self._apply_plans()

    def _apply_plans(self):
        self.ensure_one()
        applied = 0
        failed = 0
        for plan in self.plan_ids.filtered(lambda item: item.state == "planned"):
            try:
                with self.env.cr.savepoint():
                    current_hash = _stable_hash(
                        self._snapshot_state(plan.user_id)
                        if plan.user_id
                        else {"missing": True}
                    )
                    if current_hash != plan.local_state_hash:
                        raise ValidationError(
                            _("The local user changed after planning; run a fresh dry run.")
                        )
                    before = (
                        self._snapshot_state(plan.user_id)
                        if plan.user_id
                        else {"created_user": True}
                    )
                    user = self._apply_plan(plan)
                    if not plan.user_id:
                        plan.sudo().write({"user_id": user.id})
                    after = self._snapshot_state(user)
                    self.env["lhi.entra.sync.snapshot"].sudo().create(
                        {
                            "run_id": self.id,
                            "plan_id": plan.id,
                            "user_id": user.id,
                            "before_json": before,
                            "after_json": after,
                            "before_hash": _stable_hash(before),
                            "after_hash": _stable_hash(after),
                        }
                    )
                    plan.sudo().write({"state": "applied", "safe_error": False})
                    applied += 1
            except Exception as error:
                failed += 1
                plan.sudo().write(
                    {
                        "state": "failed",
                        "safe_error": self.connection_id._redact_text(error),
                    }
                )
                self._finding(
                    category="block",
                    severity="error",
                    user=plan.user_id,
                    entra_object_id=plan.entra_object_id,
                    entra_upn=plan.entra_upn,
                    message=_("Planned user change failed and was rolled back transactionally."),
                )
        state = "applied" if not failed else ("partial" if applied else "failed")
        self._status_write(
            {
                "state": state,
                "applied_user_count": applied,
                "finished_at": fields.Datetime.now(),
                "safe_error": False if applied else self.safe_error,
            }
        )
        self.configuration_id.sudo().write(
            {
                "last_successful_sync_at": fields.Datetime.now() if applied else False,
                "last_sync_state": "success" if state == "applied" else state,
                "last_safe_error": False if state == "applied" else _("Some user plans failed."),
            }
        )
        self.env["lhi.audit.log"].create_event(
            event_type="identity_sync",
            res_model=self._name,
            res_id=self.id,
            description=_(
                "Entra synchronization applied: %s users; %s failed. "
                "Existing approval assignments were not modified."
            )
            % (applied, failed),
        )
        return self.get_form_action()

    def _apply_plan(self, plan):
        payload = plan.plan_json or {}
        user_vals = dict(payload.get("user_vals") or {})
        organizational_vals = payload.get("organizational_vals") or {}
        if "department_ids" in organizational_vals:
            user_vals["lhi_department_ids"] = [
                (6, 0, organizational_vals["department_ids"])
            ]
        if "office_ids" in organizational_vals:
            user_vals["lhi_office_ids"] = [
                (6, 0, organizational_vals["office_ids"])
            ]
        add_ids = payload.get("group_add_ids") or []
        remove_ids = payload.get("group_remove_ids") or []
        protected_ids = set(
            self.env["res.groups"]._lhi_entra_protected_groups().ids
        )
        if protected_ids.intersection(add_ids + remove_ids):
            raise ValidationError(_("A planned change attempted to mutate a protected group."))
        group_commands = [(3, group_id) for group_id in remove_ids]
        group_commands += [(4, group_id) for group_id in add_ids]
        if group_commands:
            user_vals.setdefault("group_ids", []).extend(group_commands)
        if payload.get("create_user"):
            user = self.env["res.users"].sudo().with_context(
                lhi_entra_sync=True,
                no_reset_password=True,
                mail_create_nosubscribe=True,
                tracking_disable=True,
                mail_notrack=True,
            ).create(user_vals)
        else:
            user = plan.user_id.sudo().with_context(lhi_entra_sync=True)
            user.write(user_vals)

        employee_vals = dict(payload.get("employee_vals") or {})
        create_employee = employee_vals.pop("_create", False)
        employee = user.employee_id
        if create_employee and not employee:
            employee = self.env["hr.employee"].sudo().with_context(
                lhi_entra_sync=True
            ).create(employee_vals)
        elif employee and employee_vals:
            employee.sudo().with_context(lhi_entra_sync=True).write(employee_vals)
        self.env["lhi.sod.rule"].sudo().check_user_conflicts(user)
        return user

    def _snapshot_state(self, user):
        user = user.sudo().with_context(active_test=False)
        employee = user.employee_id.sudo() if user.employee_id else self.env["hr.employee"]
        return {
            "user": {
                "active": user.active,
                "name": user.name,
                "login": user.login,
                "email": user.email,
                "entra_object_id": user.entra_object_id,
                "lhi_entra_object_id": user.lhi_entra_object_id,
                "entra_tenant_id": user.entra_tenant_id,
                "entra_upn": user.entra_upn,
                "entra_account_enabled": user.entra_account_enabled,
                "entra_manager_object_id": user.entra_manager_object_id,
                "entra_last_sync_at": user.entra_last_sync_at,
                "entra_sync_state": user.entra_sync_state,
                "identity_source": user.identity_source,
                "entra_given_name": user.entra_given_name,
                "entra_family_name": user.entra_family_name,
                "entra_login_blocked": user.entra_login_blocked,
                "department_ids": sorted(user.lhi_department_ids.ids),
                "office_ids": sorted(user.lhi_office_ids.ids),
                "project_ids": sorted(user.lhi_project_ids.ids),
                "group_ids": sorted(user.group_ids.ids),
            },
            "employee": {
                "id": employee.id if employee else False,
                "active": employee.active if employee else False,
                "name": employee.name if employee else False,
                "job_title": employee.job_title if employee else False,
                "work_email": employee.work_email if employee else False,
                "work_phone": employee.work_phone if employee else False,
                "mobile_phone": employee.mobile_phone if employee else False,
                "parent_id": employee.parent_id.id if employee else False,
            },
        }

    def action_rollback(self):
        self.ensure_one()
        if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            raise AccessError(_("Only an LHI ERP administrator may roll back Entra changes."))
        if self.state not in ("applied", "partial"):
            raise UserError(_("Only an applied synchronization run can be rolled back."))
        failures = 0
        for snapshot in self.snapshot_ids:
            current = self._snapshot_state(snapshot.user_id)
            if _stable_hash(current) != snapshot.after_hash:
                failures += 1
                self._finding(
                    category="block",
                    severity="error",
                    user=snapshot.user_id,
                    entra_object_id=snapshot.user_id.entra_object_id,
                    entra_upn=snapshot.user_id.entra_upn,
                    message=_(
                        "Rollback skipped because the user changed after synchronization."
                    ),
                )
                continue
            with self.env.cr.savepoint():
                self._restore_snapshot(snapshot)
                snapshot.sudo().write(
                    {
                        "rolled_back": True,
                        "rolled_back_at": fields.Datetime.now(),
                    }
                )
        if failures:
            raise UserError(
                _(
                    "Rollback stopped safely for %s changed users. Review the run findings; "
                    "no newer local changes were overwritten."
                )
                % failures
            )
        self._status_write(
            {
                "state": "rolled_back",
                "rollback_at": fields.Datetime.now(),
                "rollback_by_id": self.env.user.id,
            }
        )
        self.env["lhi.audit.log"].create_event(
            event_type="identity_rollback",
            res_model=self._name,
            res_id=self.id,
            description=_("Entra synchronization run rolled back from immutable snapshots."),
        )
        return self.get_form_action()

    def _restore_snapshot(self, snapshot):
        before = snapshot.before_json or {}
        if before.get("created_user"):
            snapshot.user_id.with_context(lhi_entra_rollback=True).write(
                {"active": False, "entra_login_blocked": True}
            )
            return
        user_before = dict(before.get("user") or {})
        department_ids = user_before.pop("department_ids", [])
        office_ids = user_before.pop("office_ids", [])
        project_ids = user_before.pop("project_ids", [])
        group_ids = user_before.pop("group_ids", [])
        user_before.update(
            {
                "lhi_department_ids": [(6, 0, department_ids)],
                "lhi_office_ids": [(6, 0, office_ids)],
                "lhi_project_ids": [(6, 0, project_ids)],
                "group_ids": [(6, 0, group_ids)],
            }
        )
        user = snapshot.user_id.sudo().with_context(
            active_test=False,
            lhi_entra_sync=True,
            lhi_entra_rollback=True,
        )
        user.write(user_before)
        employee_before = dict(before.get("employee") or {})
        employee_id = employee_before.pop("id", False)
        if employee_id:
            employee = self.env["hr.employee"].sudo().with_context(
                active_test=False
            ).browse(employee_id).exists()
            if employee:
                employee.with_context(
                    lhi_entra_sync=True, lhi_entra_rollback=True
                ).write(employee_before)

    @api.model
    def cron_retry_failures(self):
        now = fields.Datetime.now()
        runs = self.sudo().search(
            [
                ("state", "=", "failed"),
                ("retry_count", "<", 5),
                ("next_retry_at", "<=", now),
            ],
            order="next_retry_at, id",
            limit=10,
        )
        for run in runs:
            retry_key = f"{run.idempotency_key}:retry:{run.retry_count + 1}"
            self.create_and_execute(
                configuration=run.configuration_id,
                apply=run.apply_requested,
                source="retry",
                idempotency_key=retry_key,
            )
        return True


class LhiEntraSyncPlan(models.Model):
    _name = "lhi.entra.sync.plan"
    _description = "Entra Synchronization User Plan"
    _order = "id"

    run_id = fields.Many2one(
        "lhi.entra.sync.run", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="run_id.company_id", store=True, readonly=True, index=True
    )
    user_id = fields.Many2one(
        "res.users", ondelete="restrict", index=True
    )
    entra_object_id = fields.Char(required=True, index=True)
    entra_upn = fields.Char(index=True)
    match_method = fields.Selection(
        [
            ("object_id", "Immutable Object ID"),
            ("controlled_email", "Controlled UPN/Email First Match"),
            ("create", "Create Odoo User"),
        ],
        required=True,
    )
    state = fields.Selection(
        [
            ("planned", "Planned"),
            ("blocked", "Blocked"),
            ("applied", "Applied"),
            ("failed", "Failed"),
        ],
        default="planned",
        required=True,
        index=True,
    )
    plan_json = fields.Json(required=True, groups="lhi_security.group_lhi_erp_admin")
    local_state_hash = fields.Char(required=True)
    safe_error = fields.Text(readonly=True)

    _run_user_unique = models.Constraint(
        "unique(run_id, user_id)", "A user can occur only once in a synchronization run."
    )


class LhiEntraSyncFinding(models.Model):
    _name = "lhi.entra.sync.finding"
    _description = "Entra Synchronization Finding"
    _order = "severity desc, id"

    run_id = fields.Many2one(
        "lhi.entra.sync.run", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="run_id.company_id", store=True, readonly=True, index=True
    )
    category = fields.Selection(
        [
            ("add", "Would Add"),
            ("remove", "Would Remove"),
            ("preserve", "Would Preserve"),
            ("block", "Would Block"),
            ("sod_conflict", "Segregation Conflict"),
            ("missing_mapping", "Missing Mapping"),
            ("missing_manager", "Missing Manager"),
        ],
        required=True,
        index=True,
    )
    severity = fields.Selection(
        [("info", "Information"), ("warning", "Warning"), ("error", "Error")],
        required=True,
        index=True,
    )
    user_id = fields.Many2one("res.users", ondelete="set null", index=True)
    mapping_id = fields.Many2one(
        "lhi.entra.group.mapping", ondelete="set null", index=True
    )
    entra_object_id = fields.Char(index=True)
    entra_upn = fields.Char(index=True)
    message = fields.Text(required=True)


class LhiEntraSyncSnapshot(models.Model):
    _name = "lhi.entra.sync.snapshot"
    _description = "Entra Synchronization Before and After Snapshot"
    _order = "id"

    run_id = fields.Many2one(
        "lhi.entra.sync.run", required=True, ondelete="restrict", index=True
    )
    plan_id = fields.Many2one(
        "lhi.entra.sync.plan", required=True, ondelete="restrict", index=True
    )
    company_id = fields.Many2one(
        related="run_id.company_id", store=True, readonly=True, index=True
    )
    user_id = fields.Many2one(
        "res.users", required=True, ondelete="restrict", index=True
    )
    before_json = fields.Json(
        required=True, readonly=True, groups="lhi_security.group_lhi_erp_admin"
    )
    after_json = fields.Json(
        required=True, readonly=True, groups="lhi_security.group_lhi_erp_admin"
    )
    before_hash = fields.Char(required=True, readonly=True)
    after_hash = fields.Char(required=True, readonly=True)
    rolled_back = fields.Boolean(readonly=True)
    rolled_back_at = fields.Datetime(readonly=True)

    _plan_unique = models.Constraint(
        "unique(plan_id)", "A synchronization plan can have only one snapshot."
    )

    def write(self, vals):
        allowed = {"rolled_back", "rolled_back_at"}
        if set(vals) - allowed:
            raise AccessError(_("Entra synchronization snapshots are immutable."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Entra synchronization snapshots cannot be deleted."))
