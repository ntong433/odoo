from datetime import timedelta

from odoo import api, fields, models


class LhiIntegrationJob(models.Model):
    _inherit = "lhi.integration.job"

    lhi_idempotency_key = fields.Char(index=True, copy=False)
    lhi_operation_kind = fields.Selection(
        [
            ("upload", "Document Upload"),
            ("reconcile", "Document Reconciliation"),
            ("archive", "Document Archive"),
            ("other", "Other"),
        ],
        default="other",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )

    _lhi_idempotency_unique = models.Constraint(
        "unique(lhi_idempotency_key)", "Integration job idempotency keys must be unique."
    )

    @api.model
    def lhi_create_idempotent_job(
        self,
        *,
        model_name,
        record_id,
        action,
        idempotency_key,
        description="",
        company=None,
    ):
        existing = self.search(
            [
                ("lhi_idempotency_key", "=", idempotency_key),
                ("state", "in", ("pending", "running", "failed")),
            ],
            limit=1,
        )
        if existing:
            return existing
        previous = self.search(
            [("lhi_idempotency_key", "=", idempotency_key)], limit=1
        )
        if previous:
            if previous.state == "dead_letter":
                return previous
            previous.write(
                {
                    "state": "pending",
                    "retry_count": 0,
                    "next_retry": False,
                    "last_error": False,
                }
            )
            return previous
        return self.create(
            {
                "name": f"{model_name} / {record_id} [{action}]",
                "model_name": model_name,
                "record_id": record_id,
                "action": action,
                "description": description,
                "lhi_idempotency_key": idempotency_key,
                "lhi_operation_kind": (
                    action if action in ("upload", "reconcile", "archive") else "other"
                ),
                "company_id": (company or self.env.company).id,
                "max_retries": 8,
            }
        )

    def process_jobs(self):
        now = fields.Datetime.now()
        jobs = self.search(
            [
                ("state", "in", ("pending", "failed")),
                "|",
                ("next_retry", "=", False),
                ("next_retry", "<=", now),
            ],
            order="next_retry asc nulls first, id",
            limit=50,
        ).filtered(lambda job: job.retry_count < job.max_retries)
        for job in jobs:
            job.state = "running"
            try:
                target = self.env[job.model_name].browse(job.record_id).exists()
                method = getattr(target, f"action_{job.action}", None) if target else None
                if not method:
                    raise ValueError("Integration job target or action does not exist.")
                method()
                job.write({"state": "done", "last_error": False, "next_retry": False})
            except Exception as error:
                count = job.retry_count + 1
                safe_error = self.env["lhi.graph.connection"]._redact_text(error)
                job.write(
                    {
                        "retry_count": count,
                        "state": "dead_letter" if count >= job.max_retries else "failed",
                        "last_error": safe_error,
                        "next_retry": now
                        + timedelta(minutes=min(15 * (2 ** (count - 1)), 24 * 60)),
                    }
                )
        return True
