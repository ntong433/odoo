# Sprint 21 Delivery Summary: Data Layer & Embedded Power BI

## Objectives Met
Successfully delivered `lhi_reporting_hub` and `lhi_powerbi` modules. These lay the foundation for advanced, scalable analytics by physically detaching heavy BI queries from the live transactional database, while securely integrating Microsoft Power BI dashboards directly into the Odoo user interface.

## Models and Features

### 1. Reporting Hub (`lhi_reporting_hub`)
- **Data Sync Jobs (`lhi.reporting.job`)**: Created a configuration framework for scheduling ETL (Extract, Transform, Load) routines. This prevents heavy Star Schema aggregations from locking up the production Postgres instance. Jobs explicitly track extraction queries, target schemas, and success/failure timestamps.
- **Data Quality Assurance (`lhi.data.quality.check`)**: Implemented automated SQL rule evaluations (e.g., "Budget cannot be negative", "Donors must have a valid country"). These run automatically post-sync and flag anomalies to the admin team, ensuring the Power BI model consumes reliable data.
- **Automated Scheduler**: Wired `ir.cron_run_all_reporting_jobs` to automatically fire all active data extraction jobs overnight.

### 2. Power BI Embedded (`lhi_powerbi`)
- **Report Registry (`lhi.powerbi.report`)**: Developed an Odoo model acting as a catalog for available Power BI reports. It securely stores `workspace_id` and `report_id` configurations, protecting against unauthorized access.
- **Row-Level Security (RLS) Bridge**: Power BI reports are embedded natively, relying on the `lhi_entra_object_id` (established in Sprint 20) to authenticate the user against Azure/Power BI. This ensures that even if a user accesses a dashboard in Odoo, Power BI enforces strict organizational visibility controls (RLS).
- **Owl Component Viewer**: Created `lhi_powerbi.report_viewer`, a modern Javascript (Owl) component that dynamically mounts the Power BI iframe without forcing the user to leave the Odoo ecosystem.

## Security & Reliability
- **Access Segregation**: Odoo menu visibility alone is not trusted as a security measure. Standard users can view the reports they are explicitly allowed to via `allowed_group_ids`, but the actual data rendered inside the frame is filtered securely by Microsoft Entra.
- **Automated Testing**: Python tests (`test_reporting_hub.py` and `test_powerbi.py`) were run via the Docker test runner. They successfully verified the job state transitions, the data quality checks, and the Power BI embed URL formulation logic. There were no new errors generated during the test run.
