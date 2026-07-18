from . import controllers
from . import models


def post_init_hook(env):
    configuration_model = env["lhi.entra.configuration"]
    provider = configuration_model._ensure_oauth_provider_xmlid()
    configuration_model._configure_interactive_oauth_provider(provider)
    users = env["res.users"].sudo().with_context(active_test=False).search(
        [
            ("lhi_entra_object_id", "!=", False),
            ("entra_object_id", "=", False),
        ]
    )
    for user in users:
        user.with_context(lhi_entra_sync=True).write(
            {"entra_object_id": user.lhi_entra_object_id}
        )
