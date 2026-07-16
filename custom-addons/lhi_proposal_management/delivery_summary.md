# Sprint 8: Proposal Workspace and Collaboration Delivery Summary

## Objective
Manage concept notes and proposal development.

## Deliverables
- **Concept-note & Proposal Workspaces**: Created `lhi.proposal.workspace` to encapsulate the proposal drafting cycle, tracking states from `Drafting` through to `Internal Review`, `Approved for Submission`, and `Submitted`.
- **Automated Workspace Instantiation**: Interfaced with `lhi.funding.opportunity` via buttons (`action_create_concept_note` and `action_create_full_proposal`), ensuring opportunities can generate proposals while inherently linking the same donor and context data, eliminating duplication. 
- **Configurable Proposal Sections**: Configured `lhi.proposal.section.template` containing standard templates across technical narrative, MEAL, budget, risk, staffing, procurement, etc. These dynamically auto-populate within a Workspace based on whether it is a Concept Note or Full Proposal.
- **Section Owners and Reviewers**: Each generated `lhi.proposal.section` tracks explicit owners, contributors (Many2many), and assigned reviewers. Status transitions (`Draft`, `Review`, `Needs Revision`, `Approved`) route Odoo To-Do activities automatically.
- **Internal Deadlines**: Built automated constraints mapping Workspace internal deadlines strictly against the parent Funding Opportunity's ultimate submission deadline, ensuring compliant timelines.
- **Approval Cycles**: Integrated with `lhi_approval_matrix`. A Workspace's final approval locks execution until all internal sections are marked `Approved` and all required `Annexes` are marked `Completed`.
- **Annex Checklist**: Built `lhi.proposal.annex` model functioning as a checklist for critical document uploads required for final submission.
- **Submission-readiness Dashboard**: Created dynamic Kanbans, Trees, and form views providing immediate visibility into overall readiness, section-by-section bottlenecks, and reviewer delays.

## Security Controls Enforced
- Base read/write rules isolated via multi-company boundaries in `lhi_proposal_security.xml`.
- Standardized group allocations assigning `base.group_erp_manager` access for managing configuration (Section Templates).
- Removed deprecated UI constructs (`attrs`) ensuring full Odoo 19 web-client compliance natively over RPC endpoints.

## Automated Verification
Executed Python unit tests:
- `test_workspace_creation`: Verified section templating and initialization mechanics.
- `test_workspace_constraints`: Tested that an internal proposal deadline cannot exceed the parent opportunity's final submission deadline.

Installation, upgrade, and runtime tests complete without regression.
