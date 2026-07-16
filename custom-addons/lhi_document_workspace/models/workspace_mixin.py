from odoo import fields, models, _
from odoo.exceptions import ValidationError


class LhiDocumentWorkspaceMixin(models.AbstractModel):
    _name = "lhi.document.workspace.mixin"
    _description = "LHI Document Workspace Mixin"

    lhi_document_workspace = fields.Boolean(
        string="Documents",
        compute="_compute_lhi_document_workspace",
    )

    def _compute_lhi_document_workspace(self):
        for record in self:
            record.lhi_document_workspace = bool(record.id)

    def _lhi_workspace_record(self):
        self.ensure_one()
        if not self.id:
            raise ValidationError(_("Save the business record before opening Documents."))
        self.check_access("read")
        return self

    def lhi_workspace_get(
        self,
        query="",
        category="",
        workflow_state="",
        scope="record",
        limit=100,
    ):
        record = self._lhi_workspace_record()
        return self.env["lhi.document.item"]._workspace_get(
            record,
            query=query,
            category=category,
            workflow_state=workflow_state,
            scope=scope,
            limit=limit,
        )

    def lhi_workspace_action(self, document_uuid, action):
        record = self._lhi_workspace_record()
        return self.env["lhi.document.item"]._workspace_action(
            record, document_uuid, action
        )

    def lhi_workspace_refresh(self, document_uuids):
        record = self._lhi_workspace_record()
        return self.env["lhi.document.item"]._workspace_refresh(
            record, document_uuids
        )

    def lhi_workspace_versions(self, document_uuid):
        record = self._lhi_workspace_record()
        return self.env["lhi.document.item"]._workspace_versions(
            record, document_uuid
        )

    def lhi_workspace_templates(self):
        record = self._lhi_workspace_record()
        return self.env["lhi.document.item"]._workspace_templates(record)

    def lhi_workspace_create_from_template(
        self, template_id, filename, idempotency_key
    ):
        record = self._lhi_workspace_record()
        return self.env["lhi.document.item"]._workspace_create_from_template(
            record, template_id, filename, idempotency_key
        )


WORKSPACE_MODELS = (
    "lhi.project",
    "lhi.funding.opportunity",
    "lhi.proposal.workspace",
    "lhi.award",
    "lhi.workplan",
    "lhi.meal.data",
    "lhi.meal.evidence",
    "lhi.project.report",
    "lhi.partner.profile",
    "lhi.subaward",
    "lhi.purchase.request",
    "lhi.sourcing",
    "lhi.purchase.order",
    "lhi.receipt",
    "stock.picking",
    "stock.lot",
    "lhi.asset",
    "fleet.vehicle",
    "lhi.fleet.trip",
    "lhi.fleet.incident",
    "lhi.reporting.calendar",
    "lhi.project.closeout",
)


for model_name in WORKSPACE_MODELS:
    class_name = "LhiWorkspace" + "".join(
        part.title().replace("_", "") for part in model_name.split(".")
    )
    globals()[class_name] = type(
        class_name,
        (models.Model,),
        {
            "_name": model_name,
            "_inherit": [model_name, "lhi.document.workspace.mixin"],
            "__module__": __name__,
        },
    )
