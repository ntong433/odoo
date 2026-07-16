import os

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    connections = env["lhi.graph.connection"].with_context(active_test=False).search([])

    # These removed columns held certificate or credential references. They
    # are no longer part of the model and are dropped explicitly so obsolete
    # authentication configuration cannot remain in the database.
    for column_name in (
        "application_credential_type",
        "certificate_identifier",
        "certificate_reference",
        "private_key_reference",
        "private_key_password_reference",
        "client_secret_reference",
    ):
        cr.execute(
            f'ALTER TABLE lhi_graph_connection DROP COLUMN IF EXISTS "{column_name}"'
        )

    values = {
        field_name: value
        for field_name, value in (
            ("tenant_id", os.environ.get("ENTRA_TENANT_ID")),
            ("client_id", os.environ.get("ENTRA_CLIENT_ID")),
            ("sharepoint_hostname", os.environ.get("SHAREPOINT_HOSTNAME")),
            ("sharepoint_site_path", os.environ.get("SHAREPOINT_SITE_PATH")),
            ("configured_site_id", os.environ.get("SHAREPOINT_SITE_ID")),
        )
        if value
    }
    if values:
        connections.write(values)

    drive_id = os.environ.get("SHAREPOINT_DRIVE_ID")
    if drive_id:
        connections.mapped("library_ids").write({"configured_drive_id": drive_id})

    # Force the first post-upgrade background request to authenticate with the
    # protected ENTRA_CLIENT_SECRET environment value.
    env["lhi.graph.token"].sudo().search(
        [("token_context", "=", "application")]
    ).unlink()
