# Defect Register and Remediation Log

| Defect ID | Description | Severity | Module | Status | Remediation Details |
| :--- | :--- | :--- | :--- | :--- | :--- |
| DR-001 | Webhook controller crashes on duplicate Leave event. | High | `lhi_leave_bridge` | Closed | Added idempotency keys to the payload processing cache. |
| DR-002 | Auditor role was able to modify Proposal Amounts. | Critical | `lhi_proposal_management` | Closed | Added explicit `perm_write=0` to the Auditor group in `ir.model.access.csv`. |
| DR-003 | Power BI frame failing to render for users without Odoo admin rights. | Medium | `lhi_powerbi` | Closed | Bound Microsoft Entra Auth token extraction to the `lhi_entra_object_id` rather than Odoo UI permissions. |
| DR-004 | Purchase Request exceeding budget failed silently instead of notifying the user. | Low | `lhi_budget_control` | Closed | Replaced silent return with a `ValidationError` prompting the user to request a Budget Revision. |
| DR-005 | Odoo OOM (Out of Memory) crash during heavy PDF generation. | High | System/Docker | Closed | Tuned Docker Compose `limit_memory_hard` parameter and increased worker count to 4. |

*All critical and high-severity defects identified during the UAT and security phases have been remediated and regression-tested.*
