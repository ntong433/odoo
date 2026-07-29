# Administrator guide

## Safe activation order

1. Install or upgrade `lhi_integration`, `lhi_approval_matrix`,
   `lhi_microsoft_graph_core`, and `lhi_entra_identity_sync`.
2. Confirm the active Graph connection uses the approved LHI tenant and the
   protected `ENTRA_CLIENT_SECRET` Coolify environment value.
3. Grant the application `User.Read.All` and `GroupMember.Read.All` application
   permissions with tenant administrator consent. Retain the existing
   SharePoint `Sites.Selected` assignment for document access.
4. Configure the Coolify environment variables documented below and redeploy.
5. Designate two existing local accounts as protected maintenance administrators.
   Each must already hold both LHI ERP Administrator and Odoo Settings
   Administrator. Keep their passwords in the approved password vault.
6. Create mappings from approved Entra group object IDs to existing Odoo groups.
   Never create replacement Odoo roles. Classify every mapping as Entra-managed,
   Odoo-managed, Hybrid, or Protected.
7. Keep the user scope at **Existing Odoo Entra Identities** for routine
   reconciliation, or configure one approved Entra scope group for controlled
   provisioning discovery. The scope-group option includes nested members. Entire
   tenant directory mode is intended only for bounded administrator diagnostics.
8. Use **Configure Tenant SSO**. Confirm the OAuth provider uses the tenant-specific
   authority and `https://work.lhinigeria.org/auth_oauth/signin`.
9. Run a dry synchronization. Resolve every block and segregation conflict.
10. Approve that exact dry run, then enable write mode within 24 hours. Activation
    and apply fail closed if configuration, mappings, protected groups, or
    segregation-of-duties rules changed after planning.
11. Run a controlled write synchronization in staging and verify user, manager,
    department, office, and group results. No employee record is created or
    required.
12. Enable primary Entra login only after both maintenance accounts have been
    tested through `/lhi/maintenance/login`.
13. Enable the two scheduled actions only after staging acceptance.

## Mapping modes

- **Entra-managed:** Entra membership adds the mapped existing Odoo group and
  Entra non-membership removes it.
- **Odoo-managed:** synchronization observes but never changes membership.
- **Hybrid:** Entra can add membership; removal remains an Odoo administrator
  decision.
- **Protected:** synchronization can neither grant nor remove the group.

Odoo superuser, Settings administration, ERP administration, integration
administration, audit administration, accounting activation access, and local
maintenance accounts are protected. A user who already holds a protected role is
excluded from automatic profile, manager, group, deactivation, password, and
archive changes.

## Organizational scope

Entra department and office strings are matched case-insensitively to existing
`lhi.department` and `lhi.office` records in the user's company. The sync never
creates master data. Missing or ambiguous values appear in dry-run diagnostics.

When organizational-scope synchronization is enabled, a unique match replaces the
user's department or office scope. Project assignments are never synchronized and
remain controlled by existing Odoo project assignment workflows and record rules.

## Managers and approvals

The synchronized manager is stored as the immutable Entra manager object ID on
`res.users` and resolved to `res.users.entra_manager_user_id`. Approval matrix
stages may explicitly choose **Requester's Synchronized Manager** while retaining
an existing Odoo approver group as the authorization requirement. This path does
not read or create `hr.employee`.

Approvers are resolved and copied onto the approval request at submission.
Subsequent manager changes do not alter submitted requests. A manager can use
**Reassign Current Manager** to perform an explicit, audited reassignment.

## Disabled accounts

All disabled Entra identities are blocked from Entra and password login.

- **Block login and require review** preserves the active Odoo record for audit and
  manual review.
- **Archive** also archives the Odoo user.

Protected administrators are never disabled or archived by this integration.

## Failure handling

Graph token, network, throttling, and service failures use the retry and
`Retry-After` handling in `lhi_microsoft_graph_core`. Failed synchronization runs
form an administrator-visible failure queue. Retry processing is bounded and uses
exponential delays. No existing local role is removed when Graph cannot be read.

## Diagnostics

Review **Integrations → Monitoring → Entra Sync Diagnostics** for:

- would add;
- would remove;
- would preserve;
- would block;
- segregation conflict;
- missing mapping; and
- missing manager.

Graph request metadata is available in the existing Graph diagnostics screens.
Tokens and credentials are not included in synchronization findings or logs.
