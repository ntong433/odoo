# LHI Nigeria ERP — Development Platform & Module Skeletons

This document provides instructions for setting up, running, testing, and deploying the Life Helpers Initiative (LHI) Nigeria ERP platform.

---

## 1. Directory Structure

- `odoo/`: standard Odoo core checkout (Community Edition, version 19.0).
- `custom-addons/`: houses all custom-addons (outside of Odoo core).
  - `lhi_base/`: core organizational parameters and dependencies.
  - `lhi_security/`: user/manager security groups and least-privilege configurations.
  - `lhi_approval_matrix/`: dynamic multi-step approval matrix workflows.
  - `lhi_audit/`: immutable chatter logs and event tracking.
  - `lhi_feature_control/`: secure feature flags gate for Accounting/beta releases.
  - `lhi_web_shell/`: technical console helpers for development/maintenance.
  - `lhi_dashboard/`: KPIs and management dashboard.
- `scripts/`: utility check and deployment scripts.
  - `lint-checks.py`: custom linter validating Python syntax, XML files, Odoo manifests, and security files.
  - `test-install-upgrades.sh`: script executing clean installation, upgrade, and test verification.
  - `backup-restore.sh`: postgres database and filestore backup/restore tool.

---

## 2. Setting Up the Local Development Environment

### Prerequisites
- Docker & Docker Compose
- PostgreSQL client libraries (if executing commands locally)

### Step 1: Environment Variables
Copy and modify the environment configuration variables in the `.env` file at the root:
```env
ODOO_MASTER_PASSWORD=admin_master_secret
POSTGRES_DB=lhi_erp_dev
POSTGRES_USER=odoo
POSTGRES_PASSWORD=odoo_db_password
ODOO_PORT=8069
```

### Step 2: Running with Docker Compose
Start up the database and Odoo application container:
```bash
docker compose up --build -d
```
You can inspect logs in real time using:
```bash
docker compose logs -f odoo
```

---

## 3. Automated Module Installation & Test Suite

Verify that all custom Odoo modules install and upgrade cleanly.
The script `./scripts/test-install-upgrades.sh` detects if Odoo is running inside Docker or locally, drops/creates a clean test database `lhi_erp_test`, installs the 7 custom module skeletons, runs Odoo tests, and tests the upgrades:

```bash
./scripts/test-install-upgrades.sh
```

---

## 4. Lint and Manifest Verification

Run the custom lint checks to validate python file compile correctness, XML well-formedness, Odoo manifest constraints (license `LGPL-3`, correct target version `19.0.x.y.z`), and correct security CSV alignments:

```bash
python3 ./scripts/lint-checks.py
```

---

## 5. Non-Production Backups and Restores

A dedicated script handles backups and restores of the PostgreSQL database and Odoo filestore.

### Backup
Create a snapshot of the database and filestore:
```bash
./scripts/backup-restore.sh backup [backup_name]
```
Outputs:
- SQL Dump: `backups/[backup_name].sql`
- Filestore: `backups/[backup_name]_filestore.tar.gz`

### Restore
Restore a snapshot:
```bash
./scripts/backup-restore.sh restore backups/[backup_name].sql
```

---

## 6. Staging Deployment

The staging configuration builds a sealed, immutable Odoo container where our custom addons and core code are backed directly into the Docker image (rather than using live host volume mounts):

Build and start staging:
```bash
docker compose -f docker-compose.staging.yml up --build -d
```

---

## 7. Structured Logging Baseline

Logging configuration is managed in `odoo.conf`:
- `log_level`: Default log verbosity level (set to `info`).
- `log_handler`: Custom modules can output debug levels by mapping specific handlers.
  ```ini
  log_handler = :INFO,odoo.addons.lhi_audit:DEBUG
  ```
All operations on feature flags, approvals, and critical database transactions are captured in the Odoo chatter and tracked fields inside `lhi_audit` and `lhi_feature_control`.
