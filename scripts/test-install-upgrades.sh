#!/usr/bin/env bash
# test-install-upgrades.sh
# Automated module installation and upgrade testing for Odoo 19.

set -euo pipefail

DB_NAME="lhi_erp_test"
CONFIG_FILE="./odoo.conf"
MODULES="lhi_base,lhi_security,lhi_approval_matrix,lhi_audit,lhi_feature_control,lhi_web_shell,lhi_dashboard"

# Load environment variables if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

get_docker_status() {
    docker compose ps --format '{{.Names}}' | grep -E 'odoo' > /dev/null && echo "docker" || echo "local"
}

run_test() {
    local mode=$1
    echo "=========================================================="
    echo "Running Odoo Module Installation & Test Suite ($mode mode)"
    echo "=========================================================="
    
    if [ "$mode" = "docker" ]; then
        echo "Running inside Docker..."
        # First drop/recreate database in DB container
        docker compose exec db dropdb -U "${POSTGRES_USER:-odoo}" --if-exists "$DB_NAME" || true
        docker compose exec db createdb -U "${POSTGRES_USER:-odoo}" "$DB_NAME" || true
        
        # Run Odoo install & test
        docker compose run --rm odoo python3 /opt/odoo/odoo/odoo-bin server \
            -c /etc/odoo/odoo.conf \
            -d "$DB_NAME" \
            -i "$MODULES" \
            --stop-after-init \
            --test-enable \
            --logfile ""
            
        echo "=========================================================="
        echo "Running Module Upgrade Test ($mode mode)"
        echo "=========================================================="
        
        docker compose run --rm odoo python3 /opt/odoo/odoo/odoo-bin server \
            -c /etc/odoo/odoo.conf \
            -d "$DB_NAME" \
            -u "$MODULES" \
            --stop-after-init \
            --test-enable \
            --logfile ""
    else
        echo "Running locally..."
        # Export PGPASSWORD to avoid password prompting
        export PGPASSWORD="${POSTGRES_PASSWORD:-odoo_db_password}"
        # Drop/recreate database locally
        dropdb -h localhost -U "${POSTGRES_USER:-odoo}" --if-exists "$DB_NAME" || true
        createdb -h localhost -U "${POSTGRES_USER:-odoo}" "$DB_NAME" || true
        
        # Run Odoo install & test
        python3 ./odoo/odoo-bin server \
            -c "$CONFIG_FILE" \
            -d "$DB_NAME" \
            -i "$MODULES" \
            --stop-after-init \
            --test-enable
            
        echo "=========================================================="
        echo "Running Module Upgrade Test ($mode mode)"
        echo "=========================================================="
        
        python3 ./odoo/odoo-bin server \
            -c "$CONFIG_FILE" \
            -d "$DB_NAME" \
            -u "$MODULES" \
            --stop-after-init \
            --test-enable
    fi
}

MODE=$(get_docker_status)
run_test "$MODE"
echo "All modules installed and upgraded successfully with test coverage."
