# -*- coding: utf-8 -*-
import hashlib

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import html_escape

from .hub_structure import LHI_HUB_SYSTEM_TOKEN


class LhiHubNotification(models.Model):
    _name = "lhi.hub.notification"
    _description = "HUB Notification Delivery Queue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    deduplication_key = fields.Char(required=True, readonly=True, index=True)
    source_model = fields.Char(required=True, readonly=True, index=True)
    source_id = fields.Integer(required=True, readonly=True, index=True)
    source_reference = fields.Char(required=True, readonly=True)
    event_type = fields.Char(required=True, readonly=True, index=True)
    recipient_id = fields.Many2one(
        "res.users", required=True, readonly=True, ondelete="restrict", index=True
    )
    message = fields.Text(required=True, readonly=True)
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("no_transport", "No Outbound Email Transport"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="queued",
        readonly=True,
        index=True,
    )
    in_system_delivered = fields.Boolean(readonly=True)
    email_queued = fields.Boolean(readonly=True)
    mail_id = fields.Many2one("mail.mail", readonly=True, ondelete="set null")
    attempt_count = fields.Integer(readonly=True, default=0)
    next_attempt_at = fields.Datetime(readonly=True)
    last_attempt_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    delivered_at = fields.Datetime(readonly=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True)

    _deduplication_key_unique = models.Constraint(
        "unique(deduplication_key)",
        "The HUB notification event has already been queued.",
    )

    @api.model
    def enqueue(self, *, source, event_type, message, users, company=None):
        source.ensure_one()
        users = users.exists().filtered("active")
        company = company or getattr(source, "company_id", False) or self.env.company
        notifications = self.browse()
        for user in users:
            raw = "%s:%s:%s:%s:%s" % (
                source._name,
                source.id,
                event_type,
                user.id,
                hashlib.sha256(message.encode("utf-8")).hexdigest(),
            )
            key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            existing = self.sudo().search([("deduplication_key", "=", key)], limit=1)
            if existing:
                notifications |= existing
                continue
            try:
                with self.env.cr.savepoint():
                    notification = (
                        self.sudo()
                        .with_context(lhi_hub_notification_system=LHI_HUB_SYSTEM_TOKEN)
                        .create(
                            {
                                "deduplication_key": key,
                                "source_model": source._name,
                                "source_id": source.id,
                                "source_reference": source.display_name,
                                "event_type": event_type,
                                "recipient_id": user.id,
                                "message": message,
                                "company_id": company.id,
                            }
                        )
                    )
            except IntegrityError:
                # A concurrent delivery of the same business event won the
                # unique-key race. Reuse it without failing the workflow.
                notification = self.sudo().search(
                    [("deduplication_key", "=", key)], limit=1
                )
            notifications |= notification
        return notifications

    @api.model_create_multi
    def create(self, vals_list):
        if (
            self.env.context.get("lhi_hub_notification_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB notifications are created by workflow events."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            self.env.context.get("lhi_hub_notification_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB notification delivery state is system-managed."))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("module_uninstall"):
            raise AccessError(_("HUB notification history is retained for audit."))
        return super().unlink()

    def _deliver_one(self):
        self.ensure_one()
        source = self.env[self.source_model].browse(self.source_id).exists()
        values = {
            "attempt_count": self.attempt_count + 1,
            "last_attempt_at": fields.Datetime.now(),
            "last_error": False,
        }
        try:
            in_system = False
            activity_source = self
            if source and hasattr(source, "activity_schedule"):
                try:
                    source.with_user(self.recipient_id).check_access("read")
                    activity_source = source
                except AccessError:
                    # Keep the in-system activity on the recipient-readable
                    # queue record when the business source is out of scope.
                    pass
            if activity_source:
                activity_source.sudo().activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=self.recipient_id.id,
                    note=self.message,
                    summary=_("HUB: %s") % self.event_type.replace("_", " ").title(),
                )
                in_system = True

            email_queued = False
            mail = self.env["mail.mail"]
            # Missing SMTP is an observable operating state, not a workflow
            # failure.  The in-system activity still reaches the user.
            has_transport = bool(self.env["ir.mail_server"].sudo().search([], limit=1))
            if has_transport and self.recipient_id.email:
                mail = (
                    self.env["mail.mail"]
                    .sudo()
                    .create(
                        {
                            "subject": _("HUB notification: %s")
                            % self.source_reference,
                            "body_html": "<p>%s</p>" % html_escape(self.message),
                            "email_to": self.recipient_id.email,
                            "auto_delete": False,
                        }
                    )
                )
                email_queued = True

            values.update(
                {
                    "state": (
                        "sent"
                        if email_queued
                        else "no_transport"
                        if in_system
                        else "failed"
                    ),
                    "in_system_delivered": in_system,
                    "email_queued": email_queued,
                    "mail_id": mail.id,
                    "delivered_at": fields.Datetime.now() if in_system else False,
                    "last_error": (
                        False
                        if in_system or email_queued
                        else _("No in-system source or outbound email transport.")
                    ),
                }
            )
        except Exception as error:  # delivery failure must not roll back the source
            values.update(
                {
                    "state": "failed",
                    "last_error": _("Notification delivery failed (%s).")
                    % type(error).__name__,
                    "next_attempt_at": fields.Datetime.add(
                        fields.Datetime.now(),
                        minutes=min(2 ** (self.attempt_count + 1), 240),
                    ),
                }
            )
        self.sudo().with_context(
            lhi_hub_notification_system=LHI_HUB_SYSTEM_TOKEN
        ).write(values)
        return self.state in ("sent", "no_transport")

    def action_requeue(self):
        for notification in self:
            if (
                notification.recipient_id != self.env.user
                and not self.env.user.has_group(
                    "lhi_security.group_lhi_operations_manager"
                )
                and not self.env.user.has_group("lhi_security.group_lhi_erp_admin")
            ):
                raise AccessError(
                    _("Only the recipient or Operations Management may resend.")
                )
            notification.with_context(
                lhi_hub_notification_system=LHI_HUB_SYSTEM_TOKEN
            ).write(
                {
                    "state": "queued",
                    "next_attempt_at": False,
                    "last_error": False,
                }
            )
        return True

    @api.model
    def _cron_deliver_notifications(self):
        candidates = self.search(
            [
                ("state", "in", ["queued", "failed"]),
                ("attempt_count", "<", 8),
                "|",
                ("next_attempt_at", "=", False),
                ("next_attempt_at", "<=", fields.Datetime.now()),
            ],
            order="create_date, id",
            limit=100,
        )
        for notification in candidates:
            locked = notification.try_lock_for_update()
            if locked:
                with self.env.cr.savepoint():
                    locked._deliver_one()
        return True

    @api.model
    def _cron_enqueue_stock_alerts(self):
        """Queue bounded, daily low-stock and pharmaceutical-expiry alerts."""
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        raw_days = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("lhi_hub.expiry_alert_days", "90")
        )
        try:
            expiry_days = min(max(int(raw_days), 1), 365)
        except (TypeError, ValueError):
            expiry_days = 90
        expiry_limit = fields.Datetime.add(now, days=expiry_days)

        hubs = (
            self.env["stock.warehouse"]
            .sudo()
            .search([("active", "=", True)], order="company_id, id", limit=200)
        )
        products = (
            self.env["product.product"]
            .sudo()
            .search(
                [
                    ("lhi_hub_item_type", "!=", False),
                    ("lhi_low_stock_threshold", ">", 0),
                    ("active", "=", True),
                ],
                order="id",
                limit=500,
            )
        )
        quant_model = self.env["stock.quant"].sudo()
        for hub in hubs:
            recipients = (
                hub.lhi_operations_manager_id
                | hub.lhi_warehouse_officer_ids
                | hub.lhi_operations_officer_ids
            )
            if not recipients:
                continue
            for product in products.filtered(
                lambda item: not item.company_id or item.company_id == hub.company_id
            ):
                available = quant_model._get_available_quantity(
                    product,
                    hub.lot_stock_id,
                    strict=False,
                )
                if available <= product.lhi_low_stock_threshold:
                    self.enqueue(
                        source=product,
                        event_type="low_stock",
                        message=_(
                            "%(product)s is low at %(hub)s: %(available)s available "
                            "against a threshold of %(threshold)s on %(date)s."
                        )
                        % {
                            "product": product.display_name,
                            "hub": hub.display_name,
                            "available": available,
                            "threshold": product.lhi_low_stock_threshold,
                            "date": today,
                        },
                        users=recipients,
                        company=hub.company_id,
                    )

        expiring_lots = (
            self.env["stock.lot"]
            .sudo()
            .search(
                [
                    ("product_id.lhi_hub_item_type", "=", "pharmaceuticals"),
                    ("lhi_hub_id", "!=", False),
                    ("expiration_date", ">", now),
                    ("expiration_date", "<=", expiry_limit),
                    ("lhi_quarantine_status", "=", "released"),
                ],
                order="expiration_date, id",
                limit=500,
            )
        )
        for lot in expiring_lots:
            hub = lot.lhi_hub_id
            available = quant_model._get_available_quantity(
                lot.product_id,
                hub.lot_stock_id,
                lot_id=lot,
                strict=False,
            )
            if available <= 0:
                continue
            recipients = (
                hub.lhi_operations_manager_id
                | hub.lhi_warehouse_officer_ids
                | hub.lhi_operations_officer_ids
            )
            self.enqueue(
                source=lot,
                event_type="expiring_pharmaceutical",
                message=_(
                    "%(product)s lot %(lot)s at %(hub)s expires on %(expiry)s; "
                    "%(quantity)s remains on %(date)s."
                )
                % {
                    "product": lot.product_id.display_name,
                    "lot": lot.name,
                    "hub": hub.display_name,
                    "expiry": fields.Date.to_date(lot.expiration_date),
                    "quantity": available,
                    "date": today,
                },
                users=recipients,
                company=hub.company_id,
            )
        return True
