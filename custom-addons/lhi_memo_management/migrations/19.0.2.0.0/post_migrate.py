"""
Migration 19.0.2.0.0 — Create lhi_memo_integration_operation table
and convert any existing Memo integration-failure records into
historical operation rows.

This migration is fully idempotent: running it twice produces the
same result as running it once.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration steps for lhi_memo_management 19.0.2.0.0.

    1. Ensure the lhi_memo_integration_operation table exists
       (the ORM will have created it before this runs, but the guard
       is here for safety in case of partial failures).
    2. Convert existing Memo records with integration_error_code into
       historical operation rows so the audit trail is preserved.
    3. Document item 78 (source_docx_item_id for Memo 14) is
       intentionally untouched.
    """
    _ensure_operation_table(cr)
    _migrate_historical_failures(cr)


def _ensure_operation_table(cr):
    """Ensure the integration operation table has the expected columns."""
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'lhi_memo_integration_operation'
        )
        """
    )
    table_exists = cr.fetchone()[0]
    if not table_exists:
        _logger.warning(
            "lhi_memo_integration_operation table does not yet exist; "
            "the ORM migration may not have run. This is expected only in "
            "non-standard upgrade sequences."
        )
        return

    # Ensure idempotency_key column exists (added in this version)
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lhi_memo_integration_operation'
              AND column_name = 'idempotency_key'
        )
        """
    )
    if not cr.fetchone()[0]:
        cr.execute(
            "ALTER TABLE lhi_memo_integration_operation "
            "ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR"
        )
        _logger.info("Added idempotency_key column to lhi_memo_integration_operation.")

    # Ensure index on idempotency_key
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'lhi_memo_integration_operation'
              AND indexname = 'lhi_memo_integration_operation_idempotency_key_index'
        )
        """
    )
    if not cr.fetchone()[0]:
        cr.execute(
            "CREATE INDEX IF NOT EXISTS "
            "lhi_memo_integration_operation_idempotency_key_index "
            "ON lhi_memo_integration_operation (idempotency_key)"
        )

    _logger.info("lhi_memo_integration_operation table verified.")


def _migrate_historical_failures(cr):
    """
    Insert historical operation records for existing Memo failures.

    Condition: lhi_memo.integration_error_code IS NOT NULL and no
    historical operation record already exists for that memo.

    The correlation_id format for historical records is
    'HISTORICAL-{memo_id}' to avoid collisions with live records
    (which use 'MEMO-INT-YYYYMMDD-XXXXXXXX').
    """
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'lhi_memo_integration_operation'
        )
        """
    )
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        INSERT INTO lhi_memo_integration_operation (
            memo_id,
            correlation_id,
            operation_type,
            state,
            current_step,
            started_at,
            completed_at,
            requested_by_id,
            retry_count,
            failure_code,
            safe_failure_message,
            technical_failure_reference,
            outcome_uncertain,
            requires_reconciliation,
            create_uid,
            write_uid,
            create_date,
            write_date
        )
        SELECT
            m.id                                          AS memo_id,
            'HISTORICAL-' || m.id::text                  AS correlation_id,
            'prepare_and_sign'                            AS operation_type,
            'permanent_failure'                           AS state,
            m.integration_error_code                      AS current_step,
            COALESCE(m.write_date, m.create_date, now()) AS started_at,
            COALESCE(m.write_date, now())                 AS completed_at,
            COALESCE(m.requester_id, 1)                   AS requested_by_id,
            0                                             AS retry_count,
            m.integration_error_code                      AS failure_code,
            LEFT(
                COALESCE(m.integration_error_message, 'Historical failure'),
                500
            )                                             AS safe_failure_message,
            'HISTORICAL-' || m.id::text                  AS technical_failure_reference,
            FALSE                                         AS outcome_uncertain,
            FALSE                                         AS requires_reconciliation,
            1                                             AS create_uid,
            1                                             AS write_uid,
            now()                                         AS create_date,
            now()                                         AS write_date
        FROM lhi_memo m
        WHERE m.integration_error_code IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM lhi_memo_integration_operation o
              WHERE o.correlation_id = 'HISTORICAL-' || m.id::text
          )
        """
    )
    migrated_count = cr.rowcount
    if migrated_count:
        _logger.info(
            "Migrated %d historical Memo integration failure(s) to "
            "lhi_memo_integration_operation records.",
            migrated_count,
        )
    else:
        _logger.info("No historical Memo integration failures to migrate.")
