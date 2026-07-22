from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill company ownership without changing historical source links."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    requests = env["lhi.opensign.request"].with_context(active_test=False).search([])
    for signature_request in requests:
        source = signature_request._source_record()
        company = (
            source.company_id
            if source and "company_id" in source._fields and source.company_id
            else signature_request.configuration_id.company_id
            or signature_request.company_id
            or env.company
        )
        if signature_request.company_id != company:
            signature_request.with_context(
                lhi_signature_company_backfill=True
            ).sudo().write({"company_id": company.id})
