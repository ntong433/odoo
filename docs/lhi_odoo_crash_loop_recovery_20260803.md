# LHI ERP production crash-loop recovery — 2026-08-03

## Incident outcome and scope

The production startup failure was reproduced once with the exact deployed
image and a `restart: "no"` diagnostic override. The first fatal error was a
clean-install XML resolution failure in `lhi_base`, before
`lhi_memo_integration` installation began:

```text
Traceback (most recent call last):
  File "/opt/odoo/odoo/tools/convert.py", line 605, in _tag_root
    f(rec)
  File "/opt/odoo/odoo/tools/convert.py", line 305, in _tag_menuitem
    act = self.env.ref(a_action).sudo()
          ^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/odoo/odoo/orm/environments.py", line 166, in ref
    res_model, res_id = self['ir.model.data']._xmlid_to_res_model_res_id(
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/odoo/odoo/addons/base/models/ir_model.py", line 2290, in _xmlid_to_res_model_res_id
    return self._xmlid_lookup(xmlid)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/odoo/odoo/tools/cache.py", line 98, in lookup
    return self.lookup(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/odoo/odoo/tools/cache.py", line 156, in lookup
    value = self.method(*args, **kwargs)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/odoo/odoo/addons/base/models/ir_model.py", line 2283, in _xmlid_lookup
    raise ValueError('External ID not found in the system: %s' % xmlid)
ValueError: External ID not found in the system: lhi_base.action_lhi_project

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/opt/odoo/odoo/service/server.py", line 1582, in preload_registries
    registry = Registry.new(dbname, update_module=update_module, install_modules=config['init'], upgrade_modules=config['update'], reinit_modules=config['reinit'])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/odoo/odoo/tools/func.py", line 88, in locked
    return func(inst, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/odoo/odoo/orm/registry.py", line 183, in new
    load_modules(
  File "/opt/odoo/odoo/modules/loading.py", line 464, in load_modules
    load_module_graph(
  File "/opt/odoo/odoo/modules/loading.py", line 217, in load_module_graph
    load_data(env, idref, 'init', kind='data', package=package)
  File "/opt/odoo/odoo/modules/loading.py", line 59, in load_data
    convert_file(env, package.name, filename, idref, mode, noupdate=kind == 'demo')
  File "/opt/odoo/odoo/tools/convert.py", line 693, in convert_file
    convert_xml_import(env, module, fp, idref, mode, noupdate)
  File "/opt/odoo/odoo/tools/convert.py", line 792, in convert_xml_import
    obj.parse(doc.getroot())
  File "/opt/odoo/odoo/tools/convert.py", line 663, in parse
    self._tag_root(de)
  File "/opt/odoo/odoo/tools/convert.py", line 618, in _tag_root
    raise ParseError('while parsing %s:%s, somewhere inside\n%s' % (
odoo.tools.convert.ParseError: while parsing /opt/odoo/custom-addons/lhi_base/views/menus.xml:4, somewhere inside
<menuitem id="menu_lhi_root" name="Programmatic Operations" sequence="10" action="action_lhi_project"/>
```

`lhi_base/views/menus.xml` referenced `action_lhi_project` before the manifest
loaded the file that declared it. The foundation installation exited with code
255 and rolled back. The former startup wrapper then slept approximately ten
seconds and exited; the container restart policy replayed that same failed
transaction until Coolify stopped the crash loop. The Docker health check was
not the cause.

## Controlled reproduction and backup

- Deployed image tag:
  `bfwmud40od32l7ipwskqusmr_odoo:32ff643d27fc88509f8b71e80f5738e549624e1d`
- Deployed image ID:
  `sha256:e1c8ad099dd48159c7a5a048a572a102e7c0f431190157eb2f3dd1d9eb1cf590`
- Preserved diagnostic tag:
  `lhi-odoo-diagnostic:bfwmud40od32l7ipwskqusmr-32ff643d`
- Controlled diagnostic container: `7d1e12ebf495`
- Exact foreground start:
  `docker start -a 7d1e12ebf495 2>&1 | tee /root/lhi_odoo_controlled_start.log`
- Result: exit 255, `OOMKilled=false`, restart count 0.
- Controlled log SHA-256:
  `4d9e0f13220a0b8313ca5320ca99d7c1d7ae0d3143b3aa012713f58d38994e09`

The production database was backed up before the controlled start:

- Backup: `/root/lhi-erp-backups/lhi_erp_20260803T083844Z.dump`
- Format: PostgreSQL custom format (`pg_dump -Fc`)
- Size: 1,796,400 bytes
- SHA-256:
  `ba05d74597aeb61cb7e8e003e775241d105d09b5979ea7af963d6798756d7104`
- Validation: `pg_restore --list` exit 0; 3,894 TOC lines and 3,890
  non-comment entries.
- PostgreSQL container: `2dbc65a9727b`
- PostgreSQL volume:
  `bfwmud40od32l7ipwskqusmr_postgres-staging-data`

## Database state and Memo 14 discrepancy

Before the controlled Odoo start, all 67 discovered `lhi_*` addons were
uninstalled in the current `lhi_erp` database. The `lhi_memo` table did not
exist, so Memo ID 14, reference `LHI/MEMO/2026/00014`, and document item 78
were not present in the supplied production volume. The controlled failed
foundation transaction rolled back and did not change module state.

No alternate PostgreSQL volume or older server-side backup containing Memo 14
was found during the non-destructive inspection. Therefore the incident work
cannot truthfully claim to have preserved a row that was absent before it
began. The automated migration regression test preserves the document link of
an existing failed Memo, and the migration does not update `lhi_memo` document
fields.

## Permanent corrections

- Declare the `lhi_base.action_lhi_project` action before early menu references.
- Declare the Purchase Request action before its root menu reference.
- Correct the Memo Integration inherited view external ID.
- Retain exactly one declaration of
  `lhi.memo.integration.operation`, owned and imported by
  `lhi_memo_integration`.
- Correct the integration contract validator's falsey-empty-recordset checks.
- Correct LHI Sign preflight configuration lookup.
- Preserve least privilege while allowing server-owned approval-step reads and
  mutations only after current-approver authorization.
- Make Prepare and Sign idempotency checks accessible to ordinary requesters
  without exposing technical fields, and return completed operations before
  mutable-state validation.
- Give historical operation migration rows deterministic required names and
  idempotency keys; verify the migration can run twice without duplicates and
  without changing the Memo document link.
- Import the signature callback controllers so the protected webhook route is
  registered.

## Deterministic startup behavior

`scripts/start_odoo.sh` now performs these fail-closed phases:

1. generate a mode-0600 runtime configuration;
2. validate required configuration without printing secrets;
3. wait for PostgreSQL with a bounded readiness loop;
4. refresh and commit the Odoo module list;
5. install explicitly required, currently uninstalled modules;
6. upgrade only explicitly approved, currently installed modules;
7. validate required module states, the operation model, and required fields;
8. create the normal-server readiness marker and `exec` Odoo.

Every module phase prints its name and module list, writes logs to stdout,
retains the exact nonzero exit status, and exits immediately. There is no
failure sleep. Odoo has `restart: "no"`, and the health check is gated on the
normal-server marker, so a future failed schema phase leaves one stopped
container with diagnostic logs.

## Verification evidence

Static verification:

- `python3 scripts/test_deployment_startup.py` — passed.
- `python3 scripts/validate_memo_module_boundaries.py` — passed; one operation
  model declaration, correct owner/import, no reverse dependency, acyclic
  manifests.
- `python3 scripts/validate_memo_registry_contract.py` — passed; 21 operation
  fields found statically.
- `python3 -m compileall -q custom-addons/lhi_memo_management custom-addons/lhi_memo_integration`
  — passed.
- `sh -n scripts/start_odoo.sh` — passed.
- `git diff --check` — passed.

Restored-copy verification used external sync and storage switches disabled and
Odoo's test network blocker. Final command upgraded the affected addons and ran
the selected LHI suites with `--test-enable --stop-after-init --no-http`.

- Final database clone: `lhi_erp_regression13`
- Result: 64 tests, 0 failures, 0 errors.
- Exit code 0, `OOMKilled=false`, restart count 0.
- Test log:
  `/root/lhi-erp-incident-20260803/regression-run-13.log`
- Test log SHA-256:
  `937e6f67d6314e861208eb6d9c88653076463c0098afe554f89f2013f4c859e0`
- Installed operation model count: 1.
- Required operation fields: 16/16.
- Approval, OpenSign, document, and operation rows after rollback of test
  fixtures: 0/0/0/0.
- `/web/health?db_server_status=1` on the long-running restored-copy server:
  HTTP 200 with restart count 0.

The final immutable image was then built and started once, without repository
bind mounts, against a fresh restored clone:

- Image: `lhi-odoo-diagnostic:rootfix-final-20260803`
- Image ID:
  `sha256:3776df216b2e6f8f104204ab452253841a1063190b9294189dd838c101da98e1`
- Restored database clone: `lhi_erp_finalimage`
- Startup log:
  `/root/lhi-erp-incident-20260803/finalimage-startup.log`
- Startup log SHA-256:
  `4b6f38f47dc51708da4ee3ac27d26d564be8eb126f378d7367db675b565dfe20`
- Result: normal Odoo server running, Docker health `healthy`, HTTP 200,
  `OOMKilled=false`, restart count 0.
- `lhi_memo_integration`: installed at `19.0.2.1.8`.
- `lhi.memo.integration.operation`: one registered model; all 16 required
  runtime fields present.
- Approval request, OpenSign request, provider document, and integration
  operation rows after startup: 0/0/0/0.

## Configuration, permissions, and schema impact

- New environment variables or secrets: none.
- New Microsoft Entra or Graph permissions: none.
- New SharePoint site, library, content type, retention, permission, or webhook
  configuration: none.
- Odoo core changes: none.
- Database schema changes in this correction: none beyond normal Odoo module
  installation/upgrade. The migration fix populates required audit-row values
  only when converting an existing historical Memo failure.
- External writes during install, upgrade, and tests: none.

## Coolify deployment and rollback

Deploy the committed revision once through Coolify for resource
`bfwmud40od32l7ipwskqusmr`. Keep `https://work.lhinigeria.org` as the canonical
URL. Record the Git commit, built image ID, module-phase output, registry
validation, health transition, and restart count in the incident handoff.

Rollback procedure:

1. Stop the Odoo service once; leave PostgreSQL and all volumes intact.
2. Preserve the failed container and logs.
3. Revert to the prior known image or a reviewed corrective commit; do not
   bypass module failures or restore `restart: always`.
4. If and only if database rollback is required, validate the target backup
   with `pg_restore --list`, restore into a separate database first, then follow
   an approved outage/runbook to replace the target. Never recreate the volume.
5. Reconcile integration operations and webhooks before enabling retries. Do
   not replay Memo Prepare and Sign as part of rollback.

The production deployment result, immutable image ID, release commit, and
post-deployment health evidence are runtime facts and belong in the final
incident report; a Git commit cannot embed its own final SHA.
