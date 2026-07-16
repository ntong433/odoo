import json
import os
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase

from ..models.graph_connection import LhiGraphConnection


TENANT_ID = "11111111-1111-4111-8111-111111111111"
CLIENT_ID = "22222222-2222-4222-8222-222222222222"
SITE_ID = (
    "lhinigeria.sharepoint.com,"
    "33333333-3333-4333-8333-333333333333,"
    "44444444-4444-4444-8444-444444444444"
)
DRIVE_ID = "b!approved"
ROOT_ITEM_ID = "01ROOTITEM"
CLIENT_SECRET = "test-client-secret-value"


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.content = (
            json.dumps(payload).encode()
            if payload is not None
            else b""
        )

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class TestLhiMicrosoftGraphCore(TransactionCase):
    @classmethod
    def setUpClass(cls):
        cls.test_environment = {
            "ENTRA_TENANT_ID": TENANT_ID,
            "ENTRA_CLIENT_ID": CLIENT_ID,
            "ENTRA_CLIENT_SECRET": CLIENT_SECRET,
            "SHAREPOINT_HOSTNAME": "lhinigeria.sharepoint.com",
            "SHAREPOINT_SITE_PATH": "/sites/LHIERP",
            "SHAREPOINT_SITE_ID": SITE_ID,
            "SHAREPOINT_LIBRARY_NAME": "Documents",
            "SHAREPOINT_DRIVE_ID": DRIVE_ID,
            "SHAREPOINT_ROOT_FOLDER": "ERP",
            "SHAREPOINT_ROOT_ITEM_ID": ROOT_ITEM_ID,
        }
        cls.original_environment = {
            name: os.environ.get(name) for name in cls.test_environment
        }
        os.environ.update(cls.test_environment)
        super().setUpClass()
        cls.connection = cls.env["lhi.graph.connection"].create(
            {
                "name": "Graph Test",
                "tenant_id": TENANT_ID,
                "client_id": CLIENT_ID,
                "sharepoint_hostname": "lhinigeria.sharepoint.com",
                "sharepoint_site_path": "/sites/LHIERP",
                "max_retries": 2,
                "backoff_base_seconds": 0.1,
            }
        )
        cls.local_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Graph Local Login User",
                "login": "graph.local.test",
                "password": "local-test-password",
                "email": "graph.local.test@example.invalid",
                "company_id": cls.env.company.id,
                "company_ids": [Command.set(cls.env.company.ids)],
                "group_ids": [
                    Command.set([cls.env.ref("base.group_user").id])
                ],
            }
        )

    @classmethod
    def tearDownClass(cls):
        try:
            for name, value in cls.original_environment.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        finally:
            super().tearDownClass()

    def test_broad_delegated_permissions_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.connection.delegated_scopes = (
                "openid offline_access "
                "https://graph.microsoft.com/Sites.ReadWrite.All"
            )

    def test_validated_identifiers_cannot_be_written_directly(self):
        with self.assertRaises(ValidationError):
            self.connection.sharepoint_site_id = SITE_ID
        with self.assertRaises(ValidationError):
            self.connection.library_ids[0].drive_id = "b!unvalidated"

    def test_site_validation_commits_only_confirmed_identifier(self):
        payload = {
            "id": SITE_ID,
            "displayName": "LHI ERP",
            "webUrl": "https://lhinigeria.sharepoint.com/sites/LHIERP",
        }
        with patch.object(
            LhiGraphConnection,
            "graph_request",
            autospec=True,
            return_value=payload,
        ):
            self.connection.action_validate_site()
        self.assertEqual(self.connection.sharepoint_site_id, SITE_ID)
        self.assertEqual(
            self.connection.sharepoint_site_web_url,
            payload["webUrl"],
        )

    def test_candidate_library_must_belong_to_validated_site(self):
        self.connection.with_context(lhi_graph_validated_write=True).write(
            {
                "sharepoint_site_id": SITE_ID,
                "sharepoint_site_web_url": (
                    "https://lhinigeria.sharepoint.com/sites/LHIERP"
                ),
            }
        )
        library = self.connection.library_ids.filtered(
            lambda item: item.code == "projects"
        )
        library.configured_drive_id = "b!outside"
        with patch.object(
            LhiGraphConnection,
            "graph_get_all",
            autospec=True,
                return_value=[
                    {
                        "id": "b!different",
                        "name": "Projects",
                    "webUrl": "https://example.invalid/projects",
                    "driveType": "documentLibrary",
                }
            ],
        ):
            with self.assertRaises(UserError):
                self.connection._validate_library(library)
        self.assertEqual(library.validation_state, "pending")
        self.assertFalse(library.drive_id)

    def test_sharepoint_drive_and_erp_root_are_validated(self):
        self.connection.with_context(lhi_graph_validated_write=True).write(
            {
                "sharepoint_site_id": SITE_ID,
                "sharepoint_site_web_url": (
                    "https://lhinigeria.sharepoint.com/sites/LHIERP"
                ),
            }
        )
        library = self.connection.library_ids.filtered(
            lambda item: item.code == "projects"
        )
        with (
            patch.object(
                LhiGraphConnection,
                "graph_get_all",
                autospec=True,
                return_value=[
                    {
                        "id": DRIVE_ID,
                        "name": "Documents",
                        "webUrl": (
                            "https://lhinigeria.sharepoint.com/sites/LHIERP/"
                            "Shared%20Documents"
                        ),
                        "driveType": "documentLibrary",
                    }
                ],
            ),
            patch.object(
                LhiGraphConnection,
                "graph_request",
                autospec=True,
                return_value={
                    "id": ROOT_ITEM_ID,
                    "name": "ERP",
                    "webUrl": (
                        "https://lhinigeria.sharepoint.com/sites/LHIERP/"
                        "Shared%20Documents/ERP"
                    ),
                    "folder": {"childCount": 0},
                },
            ),
        ):
            self.connection._validate_library(library)
        self.assertEqual(library.drive_id, DRIVE_ID)
        self.assertEqual(library.root_item_id, ROOT_ITEM_ID)
        self.assertEqual(library.validation_state, "valid")

    def test_pagination_follows_opaque_next_link(self):
        next_link = (
            "https://graph.microsoft.com/v1.0/sites/site/drives?"
            "$skiptoken=opaque-value"
        )
        pages = [
            {"value": [{"id": "one"}], "@odata.nextLink": next_link},
            {"value": [{"id": "two"}]},
        ]
        with patch.object(
            LhiGraphConnection,
            "graph_request",
            autospec=True,
            side_effect=pages,
        ) as graph_request:
            items = self.connection.graph_get_all(
                "/sites/site/drives",
                params={"$select": "id"},
            )
        self.assertEqual([item["id"] for item in items], ["one", "two"])
        self.assertEqual(graph_request.call_count, 2)
        self.assertEqual(graph_request.call_args_list[1].args[2], next_link)
        self.assertIsNone(graph_request.call_args_list[1].kwargs["params"])

    def test_retry_after_is_honoured_and_logged(self):
        responses = [
            FakeResponse(
                429,
                {"error": {"code": "tooManyRequests", "message": "Slow down"}},
                {"Retry-After": "3", "request-id": "request-one"},
            ),
            FakeResponse(200, {"id": "ok"}, {"request-id": "request-two"}),
        ]
        with (
            patch.object(
                LhiGraphConnection,
                "get_application_access_token",
                autospec=True,
                return_value="test-token",
            ),
            patch(
                "odoo.addons.lhi_microsoft_graph_core.models.graph_connection.requests.request",
                side_effect=responses,
            ) as request_mock,
            patch(
                "odoo.addons.lhi_microsoft_graph_core.models.graph_connection.time.sleep"
            ) as sleep_mock,
        ):
            payload = self.connection.graph_request("GET", "/sites/test")
        self.assertEqual(payload["id"], "ok")
        self.assertEqual(request_mock.call_count, 2)
        sleep_mock.assert_called_once_with(3.0)
        outcomes = self.env["lhi.graph.request.log"].sudo().search(
            [("connection_id", "=", self.connection.id)],
            order="id desc",
            limit=2,
        ).mapped("outcome")
        self.assertEqual(outcomes, ["success", "retry"])

    def test_token_endpoint_retry_after_is_honoured(self):
        responses = [
            FakeResponse(
                429,
                {
                    "error": {
                        "code": "temporarily_unavailable",
                        "message": "Retry token acquisition",
                    }
                },
                {"Retry-After": "2", "request-id": "token-request-one"},
            ),
            FakeResponse(
                200,
                {
                    "access_token": "new-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
                {"request-id": "token-request-two"},
            ),
        ]
        with (
            patch(
                "odoo.addons.lhi_microsoft_graph_core.models.graph_connection.requests.post",
                side_effect=responses,
            ) as post_mock,
            patch(
                "odoo.addons.lhi_microsoft_graph_core.models.graph_connection.time.sleep"
            ) as sleep_mock,
        ):
            payload = self.connection._post_token_request(
                {"grant_type": "client_credentials"},
                auth_context="application",
            )
        self.assertEqual(payload["access_token"], "new-token")
        self.assertEqual(post_mock.call_count, 2)
        sleep_mock.assert_called_once_with(2.0)

    def test_token_cache_and_expiry_handling(self):
        token = self.connection._store_token(
            "application",
            {
                "access_token": "cached-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
        self.assertEqual(
            self.connection.get_application_access_token(),
            "cached-token",
        )
        token.expires_at = fields.Datetime.now() + timedelta(seconds=30)
        self.assertFalse(self.connection._cached_token("application"))

    def test_missing_client_secret_fails_closed(self):
        with patch.dict(os.environ, {"ENTRA_CLIENT_SECRET": ""}, clear=False):
            with self.assertRaises(UserError) as captured:
                self.connection.get_application_access_token(force=True)
        self.assertNotIn(CLIENT_SECRET, str(captured.exception))

    def test_successful_client_credentials_request_uses_protected_secret(self):
        response = FakeResponse(
            200,
            {
                "access_token": "application-access-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            {"request-id": "token-request-success"},
        )
        with patch(
            "odoo.addons.lhi_microsoft_graph_core.models.graph_connection.requests.post",
            return_value=response,
        ) as post_mock:
            token = self.connection.get_application_access_token(force=True)
        self.assertEqual(token, "application-access-token")
        posted = post_mock.call_args.kwargs["data"]
        self.assertEqual(posted["client_id"], CLIENT_ID)
        self.assertEqual(posted["client_secret"], CLIENT_SECRET)
        self.assertEqual(posted["scope"], "https://graph.microsoft.com/.default")
        self.assertEqual(posted["grant_type"], "client_credentials")
        self.assertNotIn("client_assertion", posted)

    def test_invalid_client_secret_is_safe(self):
        response = FakeResponse(
            401,
            {
                "error": "invalid_client",
                "error_description": "The supplied client secret is invalid.",
            },
            {"request-id": "invalid-secret-request"},
        )
        with (
            patch(
                "odoo.addons.lhi_microsoft_graph_core.models.graph_connection.requests.post",
                return_value=response,
            ),
            patch.object(
                LhiGraphConnection,
                "_create_request_log",
                autospec=True,
            ) as create_log,
        ):
            with self.assertRaises(UserError) as captured:
                self.connection.get_application_access_token(force=True)
        self.assertNotIn(CLIENT_SECRET, str(captured.exception))
        log_values = create_log.call_args.kwargs
        self.assertEqual(log_values["error_code"], "invalid_client")
        self.assertEqual(log_values["outcome"], "failure")
        self.assertNotIn(CLIENT_SECRET, log_values["safe_message"] or "")

    def test_expired_client_secret_is_safe(self):
        response = FakeResponse(
            401,
            {
                "error": "invalid_client",
                "error_description": (
                    "AADSTS7000222: The provided client secret keys are expired."
                ),
            },
            {"request-id": "expired-secret-request"},
        )
        with (
            patch(
                "odoo.addons.lhi_microsoft_graph_core.models.graph_connection.requests.post",
                return_value=response,
            ),
            patch.object(
                LhiGraphConnection,
                "_create_request_log",
                autospec=True,
            ) as create_log,
        ):
            with self.assertRaises(UserError):
                self.connection.get_application_access_token(force=True)
        log_values = create_log.call_args.kwargs
        self.assertEqual(log_values["outcome"], "failure")
        self.assertEqual(log_values["error_code"], "invalid_client")
        self.assertNotIn(CLIENT_SECRET, log_values["safe_message"] or "")

    def test_secret_redaction_handles_json_and_unlabelled_runtime_values(self):
        webhook_state = "webhook-state-that-must-not-be-logged"
        with patch.dict(
            os.environ,
            {"GRAPH_WEBHOOK_CLIENT_STATE": webhook_state},
            clear=False,
        ):
            redacted = self.connection._redact_text(
                '{"client_secret": "visible-placeholder", '
                f'"detail": "{CLIENT_SECRET}", '
                f'"clientState": "{webhook_state}", '
                '"access_token": "access-value"}'
            )
        self.assertNotIn("visible-placeholder", redacted)
        self.assertNotIn(CLIENT_SECRET, redacted)
        self.assertNotIn(webhook_state, redacted)
        self.assertNotIn("access-value", redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED]"), 4)

    def test_application_token_renews_before_expiration(self):
        token = self.connection._store_token(
            "application",
            {
                "access_token": "nearly-expired-token",
                "expires_in": 3600,
            },
        )
        token.expires_at = fields.Datetime.now() + timedelta(
            seconds=self.connection.token_expiry_skew_seconds - 1
        )
        with patch.object(
            LhiGraphConnection,
            "_post_token_request",
            autospec=True,
            return_value={
                "access_token": "renewed-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        ) as token_request:
            result = self.connection.get_application_access_token()
        self.assertEqual(result, "renewed-token")
        token_request.assert_called_once()

    def test_token_vault_has_no_ordinary_user_access(self):
        self.connection._store_token(
            "delegated",
            {
                "access_token": "delegated-access",
                "refresh_token": "delegated-refresh",
                "expires_in": 3600,
            },
            user=self.local_user,
        )
        with self.assertRaises(AccessError):
            self.env["lhi.graph.token"].with_user(self.local_user).search([])

    def test_certificate_environment_is_not_used_for_token_authentication(self):
        with patch.dict(
            os.environ,
            {
                "ENTRA_CERTIFICATE_PATH": "/must/not/be/read.pem",
                "ENTRA_PRIVATE_KEY": "must-not-be-used",
            },
            clear=False,
        ):
            payload = self.connection._application_client_authentication_payload()
        self.assertEqual(payload, {"client_secret": CLIENT_SECRET})

    def test_delegated_authorization_url_uses_code_pkce_without_secret(self):
        action = self.connection.delegated_authorization_action(self.local_user)
        self.assertIn("response_type=code", action["url"])
        self.assertIn("code_challenge_method=S256", action["url"])
        self.assertNotIn("client_secret", action["url"])
        self.assertNotIn(CLIENT_SECRET, action["url"])

    def test_production_redirect_is_fixed_to_lhi_url(self):
        parameters = self.env["ir.config_parameter"].sudo()
        previous = parameters.get_param("web.base.url")
        try:
            parameters.set_param("web.base.url", "https://wrong.example")
            with patch.dict(
                os.environ,
                {"LHI_ENVIRONMENT": "production"},
                clear=False,
            ):
                with self.assertRaises(UserError):
                    self.connection._delegated_redirect_uri()
            parameters.set_param(
                "web.base.url",
                "https://work.lhinigeria.org",
            )
            with patch.dict(
                os.environ,
                {"LHI_ENVIRONMENT": "production"},
                clear=False,
            ):
                self.assertEqual(
                    self.connection._delegated_redirect_uri(),
                    (
                        "https://work.lhinigeria.org/"
                        "lhi/microsoft_graph/oauth/callback"
                    ),
                )
        finally:
            parameters.set_param("web.base.url", previous)

    def test_failed_graph_diagnostic_does_not_disable_local_login(self):
        with patch.object(
            LhiGraphConnection,
            "get_application_access_token",
            autospec=True,
            side_effect=UserError("client_secret=do-not-log"),
        ):
            action = self.connection.action_test_connection()
        self.assertEqual(action["params"]["type"], "warning")
        self.assertEqual(self.connection.connection_status, "failed")
        self.assertNotIn("do-not-log", self.connection.last_safe_error)
        auth_info = self.local_user.with_user(self.local_user)._check_credentials(
            {
                "type": "password",
                "login": self.local_user.login,
                "password": "local-test-password",
            },
            {"interactive": True},
        )
        self.assertEqual(auth_info["uid"], self.local_user.id)

    def test_graph_configuration_is_company_isolated(self):
        other_company = self.env["res.company"].create({"name": "Graph Other Company"})
        self.env["lhi.graph.connection"].create(
            {
                "name": "Other Company Graph",
                "company_id": other_company.id,
                "tenant_id": TENANT_ID,
                "client_id": CLIENT_ID,
            }
        )
        admin_user = self.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Graph Company Administrator",
                "login": "graph.company.admin",
                "email": "graph.company.admin@example.invalid",
                "company_id": self.env.company.id,
                "company_ids": [Command.set(self.env.company.ids)],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "lhi_security.group_lhi_erp_admin"
                            ).id,
                        ]
                    )
                ],
            }
        )
        visible = self.env["lhi.graph.connection"].with_user(admin_user).search([])
        self.assertEqual(visible, self.connection)
