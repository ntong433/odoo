import json
import logging
import os

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

MEMO_ORCHESTRATION_CONTRACT_VERSION = 1
EXPECTED_APPROVAL_CONTRACT_VERSION = 1
EXPECTED_STORAGE_CONTRACT_VERSION = 1
EXPECTED_SIGNATURE_CONTRACT_VERSION = 1
EXPECTED_IDENTITY_CONTRACT_VERSION = 1


class LhiMemoIntegrationContracts(models.AbstractModel):
    _name = "lhi.memo.integration.contracts"
    _description = "LHI Memo Integration Contract Validator"

    @api.model
    def validate_all_contracts(self):
        """Verifies that all dependency service contracts expose expected versions."""
        errors = []

        # 1. Approval Contract
        matrix_model = self.env.get("lhi.approval.matrix")
        if not matrix_model or not hasattr(matrix_model, "_lhi_get_memo_approval_route"):
            errors.append(_("lhi_approval_matrix does not expose _lhi_get_memo_approval_route."))
        else:
            version = getattr(matrix_model, "MEMO_APPROVAL_CONTRACT_VERSION", 0)
            if version != EXPECTED_APPROVAL_CONTRACT_VERSION:
                errors.append(
                    _("lhi_approval_matrix version mismatch: expected %s, got %s.")
                    % (EXPECTED_APPROVAL_CONTRACT_VERSION, version)
                )

        # 2. Storage Contract
        item_model = self.env.get("lhi.document.item")
        if not item_model or not hasattr(item_model, "_lhi_prepare_and_confirm_memo_document"):
            errors.append(_("lhi_sharepoint_storage does not expose _lhi_prepare_and_confirm_memo_document."))
        else:
            version = getattr(item_model, "MEMO_STORAGE_CONTRACT_VERSION", 0)
            if version != EXPECTED_STORAGE_CONTRACT_VERSION:
                errors.append(
                    _("lhi_sharepoint_storage version mismatch: expected %s, got %s.")
                    % (EXPECTED_STORAGE_CONTRACT_VERSION, version)
                )

        # 3. Signature Contract
        request_model = self.env.get("lhi.opensign.request")
        if not request_model or not hasattr(request_model, "_lhi_create_memo_signature_draft"):
            errors.append(_("lhi_signature_bridge does not expose _lhi_create_memo_signature_draft."))
        else:
            version = getattr(request_model, "MEMO_SIGNATURE_CONTRACT_VERSION", 0)
            if version != EXPECTED_SIGNATURE_CONTRACT_VERSION:
                errors.append(
                    _("lhi_signature_bridge version mismatch: expected %s, got %s.")
                    % (EXPECTED_SIGNATURE_CONTRACT_VERSION, version)
                )

        # 4. Identity Contract
        user_model = self.env.get("res.users")
        if not user_model or not hasattr(user_model, "_lhi_get_memo_identity_contract"):
            errors.append(_("lhi_entra_identity_sync does not expose _lhi_get_memo_identity_contract."))
        else:
            version = getattr(user_model, "MEMO_IDENTITY_CONTRACT_VERSION", 0)
            if version != EXPECTED_IDENTITY_CONTRACT_VERSION:
                errors.append(
                    _("lhi_entra_identity_sync version mismatch: expected %s, got %s.")
                    % (EXPECTED_IDENTITY_CONTRACT_VERSION, version)
                )

        if errors:
            raise ValidationError(
                _("Memo Integration Contract Validation Failed:\n%s") % "\n".join(errors)
            )
        return True
