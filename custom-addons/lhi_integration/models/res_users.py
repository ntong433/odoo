# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    lhi_entra_object_id = fields.Char(string="Entra Object ID", index=True, copy=False)

    _lhi_entra_object_id_unique = models.Constraint(
        "unique(lhi_entra_object_id)",
        "The Entra Object ID must be unique per user!",
    )

    @api.model
    def auth_oauth(self, provider, params):
        """Preserve Odoo's credential tuple and invoke an extension hook after login."""
        credentials = super().auth_oauth(provider, params)
        if not credentials:
            return credentials
        _database, login, _token = credentials
        user = self.sudo().search([("login", "=", login)], limit=1)
        if user:
            if user.oauth_uid and not user.lhi_entra_object_id:
                user.sudo().write({"lhi_entra_object_id": user.oauth_uid})
            user._lhi_queue_entra_profile_sync()
        return credentials

    def _lhi_queue_entra_profile_sync(self):
        """Compatibility hook implemented by the dedicated identity sync module."""
        for user in self.filtered("lhi_entra_object_id"):
            self.env["lhi.integration.job"].sudo().create_job(
                model_name="res.users",
                record_id=user.id,
                action="sync_entra_profile",
                description=f"Sync Entra Profile for User {user.name}",
            )
        return True

    def action_sync_entra_profile(self):
        """ 
        Called by the integration job worker or manually by admin.
        This would communicate with MS Graph API using lhi.integration.connection 
        """
        for user in self:
            if not user.lhi_entra_object_id:
                continue
            
            # Fetch Microsoft Graph API Connection
            connection = self.env['lhi.integration.connection'].search([
                ('provider', '=', 'microsoft_graph'),
                ('active', '=', True)
            ], limit=1)
            
            if not connection:
                _logger.warning("No active Microsoft Graph connection found for Entra Sync.")
                continue

            # Here we would use connection._execute_request(...)
            # For Sprint 6 foundation, we mock the outcome.
            _logger.info("Synchronizing Entra profile for %s (OID: %s)", user.name, user.lhi_entra_object_id)
            
            # Synchronize fields to hr.employee
            if user.employee_id:
                # E.g., user.employee_id.job_title = response.get('jobTitle')
                pass
        
        return True
