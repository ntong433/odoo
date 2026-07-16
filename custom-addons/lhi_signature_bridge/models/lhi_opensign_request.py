# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api, _

class LhiOpenSignRequest(models.Model):
    _name = 'lhi.opensign.request'
    _description = 'LHI OpenSign Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Reference', required=True, copy=False, default='New')
    res_model = fields.Char(string='Resource Model', required=True)
    res_id = fields.Integer(string='Resource ID', required=True)
    
    source_pdf = fields.Binary(string='Source PDF Document')
    source_pdf_name = fields.Char(default='source.pdf')
    source_pdf_hash = fields.Char(string='Source PDF Hash', readonly=True, tracking=True)
    
    signatories = fields.Text(string='Signatories (JSON)', required=True)
    sequence_type = fields.Selection([
        ('sequential', 'Sequential'),
        ('parallel', 'Parallel')
    ], string='Routing Sequence', default='sequential')
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent for Signature'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed')
    ], string='Status', default='draft', tracking=True)
    
    expiry_date = fields.Datetime(string='Expiry Date')
    
    signed_pdf = fields.Binary(string='Signed PDF Document')
    signed_pdf_hash = fields.Char(string='Signed PDF Hash', readonly=True)
    audit_certificate = fields.Binary(string='Audit Certificate')
    source_document_item_id = fields.Many2one(
        'lhi.document.item', readonly=True, copy=False
    )
    signed_document_item_id = fields.Many2one(
        'lhi.document.item', readonly=True, copy=False
    )
    certificate_document_item_id = fields.Many2one(
        'lhi.document.item', readonly=True, copy=False
    )
    source_stored = fields.Boolean(compute='_compute_storage_flags')
    signed_stored = fields.Boolean(compute='_compute_storage_flags')
    certificate_stored = fields.Boolean(compute='_compute_storage_flags')
    
    callback_logs = fields.Text(string='Callback Logs')
    retry_count = fields.Integer(string='Retry Count', default=0)
    error_message = fields.Text(string='Last Error Message')

    @api.depends(
        'source_document_item_id',
        'signed_document_item_id',
        'certificate_document_item_id',
    )
    def _compute_storage_flags(self):
        for request in self:
            request.source_stored = bool(request.source_document_item_id)
            request.signed_stored = bool(request.signed_document_item_id)
            request.certificate_stored = bool(request.certificate_document_item_id)

    def _store_sharepoint_binary(self, field_name, value, target_field, suffix):
        content = self.env['lhi.document.item']._decode_binary_value(value)
        if not content:
            return
        for request in self:
            item = self.env['lhi.document.item'].create_from_bytes(
                name=f'{request.name}-{suffix}.pdf',
                content=content,
                mime_type='application/pdf',
                linked_model=request._name,
                linked_record_id=request.id,
                linked_field=field_name,
                requested_by=self.env.user,
                synchronous=True,
            )
            super(
                LhiOpenSignRequest,
                request.with_context(lhi_sharepoint_opensign_skip=True),
            ).write({field_name: False, target_field: item.id})

    @api.model_create_multi
    def create(self, vals_list):
        payloads = [
            {
                name: values.get(name)
                for name in ('source_pdf', 'signed_pdf', 'audit_certificate')
            }
            for values in vals_list
        ]
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.opensign.request') or 'OS-New'
        records = super(
            LhiOpenSignRequest,
            self.with_context(lhi_sharepoint_skip_adapter=True),
        ).create(vals_list)
        for request, payload in zip(records, payloads):
            request._store_sharepoint_binary(
                'source_pdf', payload.get('source_pdf'), 'source_document_item_id', 'source'
            )
            request._store_sharepoint_binary(
                'signed_pdf', payload.get('signed_pdf'), 'signed_document_item_id', 'signed'
            )
            request._store_sharepoint_binary(
                'audit_certificate',
                payload.get('audit_certificate'),
                'certificate_document_item_id',
                'certificate',
            )
        return records

    def write(self, vals):
        if self.env.context.get('lhi_sharepoint_opensign_skip'):
            return super().write(vals)
        payloads = {
            name: vals.get(name)
            for name in ('source_pdf', 'signed_pdf', 'audit_certificate')
            if vals.get(name)
        }
        result = super(
            LhiOpenSignRequest,
            self.with_context(lhi_sharepoint_skip_adapter=True),
        ).write(vals)
        mapping = {
            'source_pdf': ('source_document_item_id', 'source'),
            'signed_pdf': ('signed_document_item_id', 'signed'),
            'audit_certificate': ('certificate_document_item_id', 'certificate'),
        }
        for field_name, value in payloads.items():
            target_field, suffix = mapping[field_name]
            self._store_sharepoint_binary(field_name, value, target_field, suffix)
        return result

    def _document_download_action(self, document):
        self.ensure_one()
        document.with_user(self.env.user).check_linked_access('read')
        return {
            'type': 'ir.actions.act_url',
            'url': f'/lhi/sharepoint/document/{document.uuid}/download',
            'target': 'new',
        }

    def action_download_source_document(self):
        self.ensure_one()
        return self._document_download_action(self.source_document_item_id.sudo())

    def action_download_signed_document(self):
        self.ensure_one()
        return self._document_download_action(self.signed_document_item_id.sudo())

    def action_download_audit_certificate(self):
        self.ensure_one()
        return self._document_download_action(self.certificate_document_item_id.sudo())

    def _lhi_source_pdf_bytes(self):
        self.ensure_one()
        if self.source_document_item_id:
            return self.source_document_item_id.download_bytes(auth_context='application')
        return self.env['lhi.document.item']._decode_binary_value(self.source_pdf)

    def action_send(self):
        for request in self:
            if (
                not request.source_document_item_id
                or request.source_document_item_id.storage_state != 'available'
            ):
                request.write({
                    'status': 'failed',
                    'error_message': _(
                        "The source document is not confirmed in SharePoint. "
                        "OpenSign transmission was blocked."
                    ),
                })
                request.message_post(
                    body=_(
                        "OpenSign transmission was blocked because SharePoint "
                        "has not confirmed the source document."
                    )
                )
                continue
            # The existing OpenSign transport remains authoritative. This bridge
            # only releases a confirmed SharePoint-backed source to that transport.
            request.write({'status': 'sent', 'error_message': False})
            request.message_post(body=_("Document sent to OpenSign for signatures."))

    def action_cancel(self):
        self.write({'status': 'cancelled'})
        self.message_post(body=_("OpenSign request cancelled."))

    def process_callback(self, status, signed_pdf=False, signed_hash=False, cert=False, error=False):
        vals = {'status': status}
        log_msg = f"Callback received: Status = {status}\n"
        if signed_pdf:
            signed_content = self.env[
                'lhi.document.item'
            ]._decode_binary_value(signed_pdf)
            vals['signed_pdf'] = base64.b64encode(signed_content)
        if signed_hash:
            vals['signed_pdf_hash'] = signed_hash
        if cert:
            certificate_content = self.env[
                'lhi.document.item'
            ]._decode_binary_value(cert)
            vals['audit_certificate'] = base64.b64encode(certificate_content)
        if error:
            vals['error_message'] = error
            log_msg += f"Error: {error}\n"
            
        vals['callback_logs'] = (self.callback_logs or '') + log_msg
        self.write(vals)

        if status == 'completed' and (
            not self.signed_document_item_id
            or self.signed_document_item_id.storage_state != 'available'
            or (cert and (
                not self.certificate_document_item_id
                or self.certificate_document_item_id.storage_state != 'available'
            ))
        ):
            self.write({
                'status': 'failed',
                'error_message': _(
                    "OpenSign completion was received, but SharePoint did not "
                    "confirm all signed artefacts."
                ),
            })
            self.message_post(
                body=_(
                    "The signature callback was quarantined until signed "
                    "documents are confirmed in SharePoint."
                )
            )
            return

        # If completed, notify source document
        if status == 'completed':
            source = self.env[self.res_model].browse(self.res_id)
            if source.exists() and hasattr(source, 'opensign_completed_hook'):
                source.opensign_completed_hook(self.id)
