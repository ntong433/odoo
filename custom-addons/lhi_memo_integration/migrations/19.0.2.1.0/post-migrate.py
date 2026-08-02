"""
Migration 19.0.2.1.0 — Create/verify lhi_memo_integration_operation table
and convert historical Memo integration failures into operation rows.

Idempotent: safe to run multiple times.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration steps for lhi_memo_integration 19.0.2.1.0.

    1. Verify lhi_memo_integration_operation table structure, columns, and indexes.
    2. Convert historical Memo records with integration_error_code into
       historical operation rows.
    3. Document item 78 (source_docx_item_id for Memo 14) is preserved.
    """
    _logger.info("Starting lhi_memo_integration post-migration 19.0.2.1.0")
    _ensure_operation_table(cr)
    _migrate_historical_failures(cr)


def _ensure_operation_table(cr):
    """Ensure columns and indexes exist on lhi_memo_integration_operation."""
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'lhi_memo_integration_operation'
        )
        """
    )
    if not cr.fetchone()[0]:
        _logger.warning(
            "lhi_memo_integration_operation table does not yet exist. "
            "It will be created by ORM model loading."
        )
        return

    # Ensure idempotency_key column
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

    # Ensure requested_by_id column
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lhi_memo_integration_operation'
              AND column_name = 'requested_by_id'
        )
        """
    )
    if not cr.fetchone()[0]:
        cr.execute(
            "ALTER TABLE lhi_memo_integration_operation "
            "ADD COLUMN IF NOT EXISTS requested_by_id INTEGER"
        )
        _logger.info("Added requested_by_id column to lhi_memo_integration_operation.")

    # Ensure company_id column
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lhi_memo_integration_operation'
              AND column_name = 'company_id'
        )
        """
    )
    if not cr.fetchone()[0]:
        cr.execute(
            "ALTER TABLE lhi_memo_integration_operation "
            "ADD COLUMN IF NOT EXISTS company_id INTEGER"
        )
        _logger.info("Added company_id column to lhi_memo_integration_operation.")

    # Index on idempotency_key
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

    # Index on correlation_id
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'lhi_memo_integration_operation'
              AND indexname = 'lhi_memo_integration_operation_correlation_id_index'
        )
        """
    )
    if not cr.fetchone()[0]:
        cr.execute(
            "CREATE INDEX IF NOT EXISTS "
            "lhi_memo_integration_operation_correlation_id_index "
            "ON lhi_memo_integration_operation (correlation_id)"
        )

    _logger.info("Verified lhi_memo_integration_operation table structure and indexes.")


def _migrate_historical_failures(cr):
    """
    Idempotently migrate historical failure records from lhi_memo into
    lhi_memo_integration_operation rows.
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
            company_id,
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
            m.company_id                                  AS company_id,
            'HISTORICAL-' || m.id::text                  AS correlation_id,
            'prepare_and_sign'                            AS operation_type,
            'permanent_failure'                           AS state,
            COALESCE(m.integration_error_code, 'failed')  AS current_step,
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
