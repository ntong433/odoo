# Sprint 13 Delivery Summary: Risks, Issues, Amendments, and Change Control

## Objectives Met
Successfully implemented the `lhi_project_risk`, `lhi_project_issue`, and `lhi_project_amendment` modules for structured control of project risks, active issues, and authorized amendments.

## Models and Features
### 1. Risk Management (`lhi_project_risk`)
- **Risk Configuration**: Matrix-based approach with models for `lhi.risk.likelihood` and `lhi.risk.impact` preloaded with 1-5 scales, alongside customizable `lhi.risk.category` entries.
- **Risk Register (`lhi.project.risk`)**: Captures risks specific to projects with dedicated Risk Owners. Automatically computes both **Inherent Risk Scores** and **Residual Risk Scores** using the matrix. Tracks mitigation actions, review dates, and escalation levels up to Donor.

### 2. Issue Management (`lhi_project_issue`)
- **Issue Register (`lhi.project.issue`)**: Fully separated from Risks to handle active problems. Tracks corrective actions, issue owners, and due dates. 
- **Resolution Evidence**: Allows attachment of direct evidence to verify issue resolution. Ensures closure via a formal approval step (`closure_approval_id`).

### 3. Change Control / Amendments (`lhi_project_amendment`)
- **Amendment Tracker (`lhi.project.amendment`)**: Provides a strict change control system. Categorizes changes (No-Cost Extension, Budget Revision, Target Revision, etc.).
- **Value Tracking & Approval Guards**: Preserves original values versus proposed values and includes a mandatory justification. Implements a multi-stage workflow from Internal Review -> Donor Submission -> Donor Approval.
- **Effective Date Enforcement**: Includes logic and an automated `ir.cron` job to prevent approved changes from transitioning to an "Applied" state before the authorized effective date is reached.

## Dashboards
- **Executive Risk Dashboard**: Provided a high-level pivot and graph view analyzing residual scores by project and risk category to quickly identify vulnerabilities.

## Security & Reliability
- **Permissions**: Fully configured `ir.model.access.csv` and multi-company record rules ensuring teams can only view/manage risks and issues linked to their authorized companies.
- **Automated Testing**: Created `TransactionCase` tests for all modules validating proper matrix score multiplication, workflow constraints (like blocking pre-effective date applications), and correct resolution tagging. Tests have executed seamlessly through the deployment verification script.
