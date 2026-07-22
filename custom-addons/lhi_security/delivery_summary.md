# LHI Security 19.0.1.0.1 Delivery Summary

## Change

`lhi_security.group_lhi_erp_admin` now directly implies both
`group_lhi_manager` and `group_lhi_employee`. The existing ERP administrator
assignments for `base.user_root` and `base.user_admin` remain unchanged. The
Manager and Employee group definitions, `base.group_system`, ACLs, record
rules, and all production user assignments were not changed.

## Changed files

- `lhi_security/__manifest__.py`
- `lhi_security/security/security_groups.xml`
- `lhi_security/tests/test_security_rules.py`
- `lhi_security/delivery_summary.md`
- `lhi_memo_management/tests/test_memo_management.py` (integration test only)

No models, fields, environment variables, secrets, Microsoft Graph or Entra
permissions, SharePoint configuration, webhooks, or document-retention settings
were added or changed. No Odoo core file was modified.

## Data and upgrade behavior

There is no database schema migration. A targeted `lhi_security` module update
uses the stable `group_lhi_erp_admin` XML ID and the additive `(4, ref(...))`
commands to add the Employee implication without replacing existing group or
user relationships. Do not use direct SQL and do not run `-u all`.

## Verification

- XML parsing and Odoo `import_xml.rng` validation: passed for 11 affected-module
  XML files.
- Python compilation: passed for `lhi_security` and `lhi_memo_management`.
- Ruff checks: passed for both modified test files.
- Manifest checks: `lhi_security` is `19.0.1.0.1`; `lhi_memo_management` remains
  `19.0.1.0.0`.
- `git diff --check`: passed.
- Targeted Odoo test command: attempted, but no test assertion ran because this
  workstation has no PostgreSQL server at
  `/var/run/postgresql/.s.PGSQL.5432`; exit code `1`. Rerun the same targeted
  suite against a disposable Coolify database and require exit code `0` before
  production approval.

The automated tests cover ERP Admin inheritance, unchanged ordinary Employee
and Manager roles, Memo read ACL and root-menu visibility for `base.user_admin`,
and continued Entra protection for ERP Admin and Memo Admin roles.

## Deployment and rollback

Deploy source through Coolify at `https://work.lhinigeria.org`. After a passing
disposable test and database backup, update only `lhi_security`; install or
update `lhi_memo_management` separately only when required by its deployment
state. Restart Odoo and verify the administrator, employee, and manager cases.

Rollback by reverting the source commit and running a targeted
`-u lhi_security` against the backed-up deployment. If production validation
detects unexpected authorization changes, restore the pre-update database
backup. No queue, webhook, or remote integration rollback is required.

## Remaining gate

Runtime authorization and menu assertions require the PostgreSQL-backed
disposable suite. Owner: deployment operator. Approval is required before the
targeted production module update; this source change does not perform it.
