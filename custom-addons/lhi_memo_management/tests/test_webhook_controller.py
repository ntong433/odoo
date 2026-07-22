import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestOpenSignWebhookAuthentication(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        configuration = cls.env["lhi.opensign.configuration"].search(
            [("company_id", "=", company.id)], limit=1
        )
        values = {
            "name": "Webhook Authentication Test",
            "api_base_url": "https://sign.example.test/api/v1.2/",
            "active": True,
        }
        if configuration:
            configuration.write(values)
        else:
            configuration = cls.env["lhi.opensign.configuration"].create(
                {"company_id": company.id, **values}
            )
        cls.env["ir.config_parameter"].sudo().set_param(
            configuration.webhook_secret_parameter, "test-webhook-secret"
        )
        project = cls.env["lhi.project"].create(
            {
                "name": "Webhook Test Project",
                "code": "WEBHOOK-TEST",
                "company_id": company.id,
            }
        )
        cls.signature_request = cls.env["lhi.opensign.request"].create(
            {
                "name": "Webhook Test Request",
                "res_model": project._name,
                "res_id": project.id,
                "configuration_id": configuration.id,
                "provider_request_id": "webhook-auth-test-provider",
                "signatories": "{}",
            }
        )

    def test_unsigned_webhook_is_rejected(self):
        response = self.url_open(
            "/api/opensign/callback",
            data=json.dumps(
                {
                    "event": "created",
                    "objectId": self.signature_request.provider_request_id,
                }
            ),
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": "invalid",
            },
        )
        self.assertEqual(response.status_code, 401)
