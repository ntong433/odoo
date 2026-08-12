import os
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLhiEntraIdentitySync(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.group_employee = cls.env.ref("lhi_security.group_lhi_employee")
        cls.group_project = cls.env.ref("lhi_security.group_lhi_project_officer")
        cls.group_meal = cls.env.ref("lhi_security.group_lhi_meal_officer")
        cls.connection = cls.env["lhi.graph.connection"].create(
            {
                "name": "Entra Test Connection",
                "company_id": cls.company.id,
                "tenant_id": "11111111-1111-4111-8111-111111111111",
                "client_id": "22222222-2222-4222-8222-222222222222",
            }
        )
        cls.configuration = cls.env["lhi.entra.configuration"].create(
            {
                "name": "Entra Test",
                "company_id": cls.company.id,
                "connection_id": cls.connection.id,
                "oauth_provider_id": cls.env.ref(
                    "lhi_integration.provider_microsoft_entra"
                ).id,
                "sync_organizational_scope": False,
                "user_scope_mode": "tenant_directory",
            }
        )
        cls.mapping_project = cls.env["lhi.entra.group.mapping"].create(
            {
                "company_id": cls.company.id,
                "connection_id": cls.connection.id,
                "entra_group_object_id": "33333333-3333-4333-8333-333333333333",
                "entra_group_display_name": "Project Officers",
                "odoo_group_id": cls.group_project.id,
                "management_mode": "entra",
            }
        )
        cls.mapping_meal = cls.env["lhi.entra.group.mapping"].create(
            {
                "company_id": cls.company.id,
                "connection_id": cls.connection.id,
                "entra_group_object_id": "44444444-4444-4444-8444-444444444444",
                "entra_group_display_name": "MEAL Officers",
                "odoo_group_id": cls.group_meal.id,
                "management_mode": "odoo",
            }
        )
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Entra User",
                "login": "entra.user@example.org",
                "email": "entra.user@example.org",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [
                    Command.set((cls.group_employee | cls.group_meal).ids)
                ],
                "entra_object_id": "55555555-5555-4555-8555-555555555555",
                "identity_source": "entra",
            }
        )

    def _remote_user(self, enabled=True):
        return {
            "id": self.user.entra_object_id,
            "accountEnabled": enabled,
            "businessPhones": ["+2348000000000"],
            "department": "Programmes",
            "displayName": "Entra User Updated",
            "givenName": "Entra",
            "jobTitle": "Project Officer",
            "mail": "entra.user@example.org",
            "mobilePhone": "+2348111111111",
            "officeLocation": "Abuja",
            "surname": "User",
            "userPrincipalName": "entra.user@example.org",
        }

    def _graph_request(self, method, resource, **kwargs):
        if resource.endswith("/checkMemberGroups"):
            return {"value": [self.mapping_project.entra_group_object_id]}
        if resource.endswith("/manager"):
            return {"error": {"code": "Request_ResourceNotFound"}}
        raise AssertionError(resource)

    def test_dry_run_adds_only_existing_mapped_group(self):
        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[self._remote_user()],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=False,
                source="manual",
            )
        self.assertEqual(run.state, "planned")
        self.assertNotIn(self.group_project, self.user.group_ids)
        self.assertIn(
            self.group_project.id,
            run.plan_ids.plan_json["group_add_ids"],
        )
        self.assertIn(self.group_meal, self.user.group_ids)

    def test_approved_plan_applies_and_rolls_back(self):
        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[self._remote_user()],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=False,
                source="manual",
            )
        self.configuration.write({"approved_dry_run_id": run.id})
        self.configuration.with_context(lhi_entra_activation=True).write(
            {"sync_mode": "write"}
        )
        run.action_apply()
        self.assertEqual(run.state, "applied")
        self.assertIn(self.group_project, self.user.group_ids)
        self.assertIn(self.group_meal, self.user.group_ids)
        run.action_rollback()
        self.assertEqual(run.state, "rolled_back")
        self.assertNotIn(self.group_project, self.user.group_ids)
        self.assertIn(self.group_meal, self.user.group_ids)

    def test_idempotency_key_reuses_the_existing_run(self):
        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[self._remote_user()],
            ) as graph_get_all,
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            first = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                idempotency_key="entra-test-idempotency",
            )
            second = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                idempotency_key="entra-test-idempotency",
            )
        self.assertEqual(first, second)
        self.assertEqual(graph_get_all.call_count, 1)

    def test_missing_entra_user_is_created_silently_and_idempotently(self):
        remote = self._remote_user()
        remote.update(
            {
                "id": "88888888-8888-4888-8888-888888888888",
                "displayName": "New Silent User",
                "mail": False,
                "userPrincipalName": "NEW.USER@EXAMPLE.ORG",
            }
        )
        mail_count = self.env["mail.mail"].sudo().search_count([])
        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[remote],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=False,
                source="manual",
            )
        self.assertEqual(run.state, "planned")
        self.assertEqual(run.plan_ids.match_method, "create")
        self.assertFalse(run.plan_ids.user_id)
        self.assertFalse(
            self.env["res.users"].with_context(active_test=False).search(
                [("entra_object_id", "=", remote["id"])]
            )
        )

        self.configuration.write({"approved_dry_run_id": run.id})
        self.configuration.with_context(lhi_entra_activation=True).write(
            {"sync_mode": "write"}
        )
        run.action_apply()
        user = self.env["res.users"].with_context(active_test=False).search(
            [("entra_object_id", "=", remote["id"])]
        )
        self.assertEqual(len(user), 1)
        self.assertEqual(user.login, "new.user@example.org")
        self.assertTrue(user.active)
        self.assertTrue(user.has_group("lhi_security.group_lhi_employee"))
        self.assertFalse(user.share)
        self.assertTrue(user.has_group("base.group_user"))
        self.assertFalse(user.has_group("base.group_portal"))
        self.assertFalse(user.has_group("base.group_system"))
        self.assertFalse(user.has_group("base.group_erp_manager"))
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), mail_count)

        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[remote],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            second = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=True,
                source="manual",
            )
        self.assertEqual(second.state, "applied")
        self.assertEqual(
            self.env["res.users"].with_context(active_test=False).search_count(
                [("entra_object_id", "=", remote["id"])]
            ),
            1,
        )
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), mail_count)

    def test_graph_failure_queues_retry_without_changing_roles(self):
        with patch.object(
            type(self.connection),
            "graph_get_all",
            side_effect=TimeoutError("Graph unavailable"),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                source="scheduled",
                idempotency_key="entra-test-failure",
            )
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.retry_count, 1)
        self.assertTrue(run.next_retry_at)
        self.assertIn(self.group_meal, self.user.group_ids)
        self.assertNotIn(self.group_project, self.user.group_ids)

    def test_configuration_drift_requires_a_fresh_dry_run(self):
        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[self._remote_user()],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=False,
                source="manual",
            )
        self.configuration.write({"approved_dry_run_id": run.id})
        self.configuration.with_context(lhi_entra_activation=True).write(
            {"sync_mode": "write"}
        )
        self.mapping_project.priority += 1
        with self.assertRaises(UserError):
            run.action_apply()
        self.assertNotIn(self.group_project, self.user.group_ids)

    def test_sod_conflict_is_blocked_before_write(self):
        self.env["lhi.sod.rule"].create(
            {
                "name": "Employee and Project Officer Test Conflict",
                "group_1_id": self.group_employee.id,
                "group_2_id": self.group_project.id,
            }
        )
        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[self._remote_user()],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=False,
                source="manual",
            )
        self.assertEqual(run.conflict_count, 1)
        self.assertEqual(run.plan_ids.state, "blocked")
        self.assertNotIn(self.group_project, self.user.group_ids)

    def test_protected_administrator_is_preserved(self):
        administrator = self.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Protected Administrator",
                "login": "protected.admin@example.org",
                "company_id": self.company.id,
                "company_ids": [Command.set(self.company.ids)],
                "group_ids": [
                    Command.set(
                        (
                            self.env.ref("lhi_security.group_lhi_erp_admin")
                            | self.env.ref("base.group_system")
                        ).ids
                    )
                ],
                "entra_object_id": "77777777-7777-4777-8777-777777777777",
            }
        )
        remote = self._remote_user()
        remote["id"] = administrator.entra_object_id
        remote["userPrincipalName"] = administrator.login
        remote["mail"] = administrator.login
        remote["displayName"] = "Changed by Entra"
        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[remote],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=False,
                source="manual",
            )
        self.assertFalse(run.plan_ids.filtered(lambda plan: plan.user_id == administrator))
        self.assertEqual(administrator.name, "Protected Administrator")
        self.assertTrue(
            run.finding_ids.filtered(
                lambda finding: finding.user_id == administrator
                and finding.category == "preserve"
            )
        )

    def test_protected_group_cannot_be_entra_managed(self):
        with self.assertRaises(ValidationError):
            self.env["lhi.entra.group.mapping"].create(
                {
                    "company_id": self.company.id,
                    "connection_id": self.connection.id,
                    "entra_group_object_id": "66666666-6666-4666-8666-666666666666",
                    "odoo_group_id": self.env.ref("base.group_system").id,
                    "management_mode": "entra",
                }
            )

    def test_enabled_entra_identity_reactivates_archived_user(self):
        self.user.with_context(lhi_entra_rollback=True).write(
            {
                "active": False,
                "entra_login_blocked": True,
            }
        )

        self.assertFalse(self.user.active)

        with (
            patch.object(
                type(self.connection),
                "graph_get_all",
                return_value=[self._remote_user(enabled=True)],
            ),
            patch.object(
                type(self.connection),
                "graph_request",
                side_effect=self._graph_request,
            ),
        ):
            run = self.env["lhi.entra.sync.run"].create_and_execute(
                configuration=self.configuration,
                apply=False,
                source="manual",
            )

        plan = run.plan_ids.filtered(
            lambda record: record.user_id == self.user
        )
        self.assertEqual(len(plan), 1)
        self.assertTrue(plan.plan_json["user_vals"]["active"])
        self.assertFalse(
            plan.plan_json["user_vals"]["entra_login_blocked"]
        )
        self.assertTrue(
            plan.plan_json["user_vals"]["entra_account_enabled"]
        )

        self.configuration.write(
            {"approved_dry_run_id": run.id}
        )
        self.configuration.with_context(
            lhi_entra_activation=True
        ).write(
            {"sync_mode": "write"}
        )

        run.action_apply()

        self.user.invalidate_recordset()

        self.assertTrue(self.user.active)
        self.assertTrue(self.user.entra_account_enabled)
        self.assertFalse(self.user.entra_login_blocked)

    def test_disabled_entra_identity_fails_closed(self):
        self.user.write(
            {
                "entra_account_enabled": False,
                "entra_login_blocked": True,
            }
        )
        with self.assertRaises(AccessDenied):
            self.user.with_user(self.user)._check_credentials(
                {
                    "type": "oauth_token",
                    "login": self.user.login,
                    "token": "not-a-token",
                },
                {"interactive": True},
            )

    def test_ordinary_user_cannot_read_identity_configuration(self):
        with self.assertRaises(AccessError):
            self.env["lhi.entra.configuration"].with_user(self.user).search([])

    def test_primary_sso_keeps_the_existing_odoo_callback(self):
        parameters = self.env["ir.config_parameter"].sudo()
        previous = parameters.get_param("web.base.url")
        try:
            parameters.set_param("web.base.url", "https://work.lhinigeria.org")
            with patch.dict(
                os.environ,
                {
                    "ENTRA_TENANT_ID": self.connection.tenant_id,
                    "ENTRA_CLIENT_ID": self.connection.client_id,
                    "ENTRA_REDIRECT_URI": (
                        "https://work.lhinigeria.org/auth_oauth/signin"
                    ),
                },
                clear=False,
            ):
                self.configuration.action_configure_oauth_provider()
            provider = self.configuration.oauth_provider_id
            self.assertEqual(provider.name, "Microsoft Entra ID")
            self.assertEqual(provider.client_id, self.connection.client_id)
            self.assertTrue(provider.enabled)
            self.assertEqual(provider.scope, "openid profile email User.Read")
            self.assertEqual(provider.body, "Sign in with Microsoft")
            if "css_class" in provider._fields:
                self.assertEqual(provider.css_class, "fa fa-windows")
            self.assertNotIn("PLACEHOLDER", provider.client_id.upper())
            self.assertNotIn("/common/", provider.auth_endpoint)
            self.assertEqual(
                provider.auth_endpoint,
                (
                    "https://login.microsoftonline.com/"
                    f"{self.connection.tenant_id}/oauth2/v2.0/authorize"
                ),
            )
            self.assertEqual(
                self.env["res.config.settings"].get_uri(),
                "https://work.lhinigeria.org/auth_oauth/signin",
            )
            self.assertEqual(
                parameters.get_param("auth_oauth.authorization_header"), "1"
            )
        finally:
            parameters.set_param("web.base.url", previous)

    def test_placeholder_client_id_is_rejected(self):
        with (
            patch.dict(
                os.environ,
                {
                    "ENTRA_TENANT_ID": self.connection.tenant_id,
                    "ENTRA_CLIENT_ID": "PLACEHOLDER_CLIENT_ID",
                },
                clear=False,
            ),
            self.assertRaises(UserError),
        ):
            self.configuration._configure_interactive_oauth_provider(
                self.configuration.oauth_provider_id
            )

    def test_manager_approval_snapshots_approver(self):
        manager = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Manager",
                "login": "manager@example.org",
                "entra_object_id": "77777777-7777-4777-8777-777777777777",
                "company_id": self.company.id,
                "company_ids": [Command.set(self.company.ids)],
                "group_ids": [Command.set(self.group_project.ids)],
            }
        )
        self.user.entra_manager_object_id = manager.entra_object_id
        matrix = self.env["lhi.approval.matrix"].create(
            {
                "name": "Manager Approval Test",
                "document_type": "purchase",
                "company_id": self.company.id,
                "currency_id": self.company.currency_id.id,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Manager Review",
                            "approver_source": "requester_manager",
                            "approver_group_id": self.group_project.id,
                        }
                    )
                ],
            }
        )
        request = self.env["lhi.approval.request"].with_user(self.user).create(
            {
                "res_model": "res.users",
                "res_id": self.user.id,
                "document_type": "purchase",
                "currency_id": self.company.currency_id.id,
                "creator_id": self.user.id,
                "company_id": self.company.id,
            }
        )
        request.with_user(self.user).action_submit()
        self.assertEqual(request.current_line_id.approver_ids, manager)
        self.user.entra_manager_object_id = False
        self.assertEqual(request.current_line_id.approver_ids, manager)
