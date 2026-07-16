#!/usr/bin/env bash
# backup-restore.sh
# Script for non-production environment backup and restore operations.

set -euo pipefail

BACKUP_DIR="./backups"
mkdir -p "${BACKUP_DIR}"

usage() {
    echo "Usage: $0 {backup|restore} [backup_name|file_path]"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

ACTION=$1

# Load environment variables
if [ -f .env ]; then
    # Parse environment variables safely
    export $(grep -v '^#' .env | xargs)
fi

DB_NAME=${POSTGRES_DB:-lhi_erp_dev}
DB_USER=${POSTGRES_USER:-odoo}

# Dynamic container detection
get_db_container() {
    docker ps --format '{{.Names}}' | grep -E 'db|postgres' | head -n 1 || echo ""
}

do_backup() {
    local name=${2:-"backup_$(date +%Y%m%d_%H%M%S)"}
    local db_file="${BACKUP_DIR}/${name}.sql"
    local filestore_file="${BACKUP_DIR}/${name}_filestore.tar.gz"
    
    echo "Starting backup: ${name}..."
    
    # DB Backup
    local container=$(get_db_container)
    if [ -n "$container" ]; then
        echo "PostgreSQL container found ($container). Dumping database..."
        docker compose exec db pg_dump -U "$DB_USER" "$DB_NAME" > "$db_file"
    else
        echo "No running DB container found. Attempting local pg_dump..."
        pg_dump -U "$DB_USER" -h localhost "$DB_NAME" > "$db_file"
    fi
    
    # Filestore Backup
    echo "Backing up Odoo filestore..."
    if [ -d "./odoo-data" ]; then
        tar -czf "$filestore_file" -C "./odoo-data" .
    elif docker volume inspect odoo_postgres_data &>/dev/null; then
        echo "Backing up Docker volume odoo_odoo_data..."
        docker run --rm -v odoo_odoo_data:/volume -v "$(pwd)/${BACKUP_DIR}:/backup" alpine tar -czf "/backup/$(basename "$filestore_file")" -C /volume .
    else
        echo "No local filestore directory or docker volume found. Skipping filestore."
    fi
    
    echo "Backup completed successfully!"
    echo "Database: $db_file"
    if [ -f "$filestore_file" ]; then
        echo "Filestore: $filestore_file"
    fi
}

do_restore() {
    local backup_path=$2
    if [ ! -f "$backup_path" ]; then
        echo "Error: Backup file '$backup_path' not found."
        exit 1
    fi
    
    echo "Restoring database from $backup_path..."
    local container=$(get_db_container)
    if [ -n "$container" ]; then
        echo "PostgreSQL container found ($container). Restoring database..."
        docker compose exec db dropdb -U "$DB_USER" --if-exists "$DB_NAME"
        docker compose exec db createdb -U "$DB_USER" "$DB_NAME"
        docker compose exec db psql -U "$DB_USER" "$DB_NAME" < "$backup_path"
    else
        echo "No running DB container found. Attempting local restore..."
        dropdb -U "$DB_USER" -h localhost --if-exists "$DB_NAME"
        createdb -U "$DB_USER" -h localhost "$DB_NAME"
        psql -U "$DB_USER" -h localhost "$DB_NAME" < "$backup_path"
    fi
    
    # Filestore Restore
    local filestore_path="${backup_path%.sql}_filestore.tar.gz"
    if [ -f "$filestore_path" ]; then
        echo "Restoring Odoo filestore from $filestore_path..."
        if [ -d "./odoo-data" ]; then
            rm -rf ./odoo-data/*
            tar -xzf "$filestore_path" -C "./odoo-data"
        elif docker volume inspect odoo_odoo_data &>/dev/null; then
            echo "Restoring to Docker volume odoo_odoo_data..."
            docker run --rm -v odoo_odoo_data:/volume -v "$(pwd)/$(dirname "$filestore_path"):/backup" alpine sh -c "rm -rf /volume/* && tar -xzf /backup/$(basename "$filestore_path") -C /volume"
        fi
    else
        echo "Warning: No associated filestore backup found at $filestore_path. Skipping filestore."
    fi
    
    echo "Restore completed successfully!"
}

case "$ACTION" in
    backup)
        do_backup "$@"
        ;;
    restore)
        if [ $# -lt 2 ]; then
            echo "Error: Please specify the backup file path to restore."
            usage
        fi
        do_restore "$@"
        ;;
    *)
        usage
        ;;
esac
