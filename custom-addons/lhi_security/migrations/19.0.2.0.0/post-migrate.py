# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def _ref(env, xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


def _add_implied(env, source_xmlid, target_xmlid):
    source = _ref(env, source_xmlid)
    target = _ref(env, target_xmlid)
    if not source or not target or target in source.implied_ids:
        return 0
    source.write({"implied_ids": [(4, target.id)]})
    return 1


def _remove_implied(env, source_xmlid, target_xmlid):
    source = _ref(env, source_xmlid)
    target = _ref(env, target_xmlid)
    if not source or not target or target not in source.implied_ids:
        return 0
    source.write({"implied_ids": [(3, target.id)]})
    return 1


def _set_rule_group(env, rule_xmlid, group_xmlid):
    rule = _ref(env, rule_xmlid)
    group = _ref(env, group_xmlid)
    if not rule or not group or rule.groups == group:
        return 0
    rule.write({"groups": [(6, 0, [group.id])]})
    return 1


def _set_acl_group(env, acl_xmlid, group_xmlid):
    acl = _ref(env, acl_xmlid)
    group = _ref(env, group_xmlid)
    if not acl or not group or acl.group_id == group:
        return 0
    acl.write({"group_id": group.id})
    return 1


def migrate(cr, version):
    """Repair the historical additive group graph without broad user grants."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    changes = 0

    # Positive role chains. Commands add only the intended lower role and do
    # not disturb technical groups legitimately implied by optional addons.
    role_chains = (
        ("lhi_security.group_lhi_operations_officer", "lhi_security.group_lhi_operations_viewer"),
        ("lhi_security.group_lhi_operations_manager", "lhi_security.group_lhi_operations_officer"),
        ("lhi_security.group_lhi_hub_viewer", "lhi_security.group_lhi_employee"),
        ("lhi_security.group_lhi_warehouse_officer", "lhi_security.group_lhi_hub_viewer"),
        ("lhi_security.group_lhi_hub_manager", "lhi_security.group_lhi_warehouse_officer"),
        ("lhi_security.group_lhi_asset_officer", "lhi_security.group_lhi_asset_viewer"),
        ("lhi_security.group_lhi_asset_manager", "lhi_security.group_lhi_asset_officer"),
        ("lhi_security.group_lhi_procurement_officer", "lhi_security.group_lhi_procurement_viewer"),
        ("lhi_security.group_lhi_procurement_manager", "lhi_security.group_lhi_procurement_officer"),
        ("lhi_security.group_lhi_store_officer", "lhi_security.group_lhi_inventory_viewer"),
        ("lhi_security.group_lhi_inventory_manager", "lhi_security.group_lhi_store_officer"),
        ("lhi_security.group_lhi_fleet_officer", "lhi_security.group_lhi_fleet_viewer"),
        ("lhi_security.group_lhi_fleet_manager", "lhi_security.group_lhi_fleet_officer"),
        ("lhi_security.group_lhi_project_officer", "lhi_security.group_lhi_programme_viewer"),
        ("lhi_security.group_lhi_project_manager", "lhi_security.group_lhi_project_officer"),
        ("lhi_security.group_lhi_executive_approver", "lhi_security.group_lhi_approvals_viewer"),
        ("lhi_security.group_lhi_approvals_manager", "lhi_security.group_lhi_executive_approver"),
        ("lhi_security.group_lhi_reports_officer", "lhi_security.group_lhi_reports_viewer"),
        ("lhi_security.group_lhi_reports_manager", "lhi_security.group_lhi_reports_officer"),
        ("lhi_security.group_lhi_powerbi_officer", "lhi_security.group_lhi_powerbi_viewer"),
        ("lhi_security.group_lhi_powerbi_manager", "lhi_security.group_lhi_powerbi_officer"),
        ("lhi_security.group_lhi_meal_officer", "lhi_security.group_lhi_meal_viewer"),
        ("lhi_security.group_lhi_meal_manager", "lhi_security.group_lhi_meal_officer"),
        ("lhi_security.group_lhi_hr_officer", "lhi_security.group_lhi_hr_viewer"),
        ("lhi_security.group_lhi_hr_manager", "lhi_security.group_lhi_hr_officer"),
    )
    for source_xmlid, target_xmlid in role_chains:
        with cr.savepoint():
            changes += _add_implied(env, source_xmlid, target_xmlid)

    # Remove only obsolete implied edges. Direct assignments to legitimate
    # functional roles are deliberately preserved.
    obsolete_edges = (
        ("lhi_security.group_lhi_operations_officer", "lhi_security.group_lhi_hub_viewer"),
        ("lhi_security.group_lhi_operations_manager", "lhi_security.group_lhi_warehouse_officer"),
        ("lhi_security.group_lhi_operations_officer", "stock.group_stock_user"),
        ("lhi_security.group_lhi_operations_officer", "stock.group_stock_multi_locations"),
        ("lhi_security.group_lhi_operations_officer", "stock.group_stock_multi_warehouses"),
        ("lhi_security.group_lhi_operations_officer", "stock.group_production_lot"),
        ("lhi_security.group_lhi_project_officer", "lhi_programme_management.group_lhi_programmes_viewer"),
        ("lhi_security.group_lhi_procurement_officer", "lhi_programme_management.group_lhi_programmes_viewer"),
        ("lhi_security.group_lhi_store_officer", "lhi_programme_management.group_lhi_programmes_viewer"),
        ("lhi_security.group_lhi_fleet_officer", "lhi_programme_management.group_lhi_programmes_viewer"),
        ("lhi_security.group_lhi_meal_officer", "lhi_programme_management.group_lhi_programmes_viewer"),
        ("lhi_security.group_lhi_finance_reviewer", "lhi_programme_management.group_lhi_programmes_finance_reviewer"),
        ("lhi_media_communications.group_lhi_media_viewer", "lhi_programme_management.group_lhi_programmes_viewer"),
    )
    for source_xmlid, target_xmlid in obsolete_edges:
        with cr.savepoint():
            changes += _remove_implied(env, source_xmlid, target_xmlid)

    # Preserve legitimate explicit assignments to the retired duplicate
    # Programs Viewer, then remove only that obsolete direct membership.
    legacy_viewer = _ref(env, "lhi_programme_management.group_lhi_programmes_viewer")
    canonical_viewer = _ref(env, "lhi_security.group_lhi_programme_viewer")
    if legacy_viewer and canonical_viewer:
        direct_users = legacy_viewer.user_ids
        if direct_users:
            canonical_viewer.write({"user_ids": [(4, user.id) for user in direct_users]})
            legacy_viewer.write({"user_ids": [(3, user.id) for user in direct_users]})
            changes += len(direct_users)
        changes += _remove_implied(
            env,
            "lhi_programme_management.group_lhi_programmes_viewer",
            "base.group_user",
        )
        changes += _add_implied(
            env,
            "lhi_programme_management.group_lhi_programmes_viewer",
            "lhi_security.group_lhi_programme_viewer",
        )

    erp_managers = (
        "lhi_security.group_lhi_operations_manager",
        "lhi_security.group_lhi_hub_manager",
        "lhi_security.group_lhi_asset_manager",
        "lhi_security.group_lhi_procurement_manager",
        "lhi_security.group_lhi_inventory_manager",
        "lhi_security.group_lhi_fleet_manager",
        "lhi_security.group_lhi_project_manager",
        "lhi_security.group_lhi_approvals_manager",
        "lhi_security.group_lhi_reports_manager",
        "lhi_security.group_lhi_powerbi_manager",
        "lhi_security.group_lhi_meal_manager",
        "lhi_security.group_lhi_hr_manager",
        "lhi_programme_management.group_lhi_programmes_admin",
        "lhi_media_communications.group_lhi_media_manager",
        "lhi_memo_management.group_lhi_memo_admin",
        "lhi_signature_bridge.group_lhi_signature_admin",
    )
    for manager_xmlid in erp_managers:
        with cr.savepoint():
            changes += _add_implied(
                env, "lhi_security.group_lhi_erp_admin", manager_xmlid
            )

    # lhi_base cannot depend on lhi_security, so repair the six foundational
    # Programs ACLs here as well as in ordinary XML data. This remains safe if
    # an older database marked any of those external IDs noupdate.
    for acl_xmlid in (
        "lhi_base.access_lhi_programme_user",
        "lhi_base.access_lhi_donor_user",
        "lhi_base.access_lhi_funding_source_user",
        "lhi_base.access_lhi_award_user",
        "lhi_base.access_lhi_project_user",
        "lhi_base.access_lhi_activity_user",
    ):
        with cr.savepoint():
            changes += _set_acl_group(
                env, acl_xmlid, "lhi_security.group_lhi_programme_viewer"
            )

    # noupdate security records retain their old group relation during a normal
    # upgrade, so repair the exact historical records in place.
    rule_groups = {
        "lhi_asset_management.rule_lhi_asset_officer_scope": "lhi_security.group_lhi_asset_viewer",
        "lhi_fleet_operations.rule_lhi_fleet_trip_company": "lhi_security.group_lhi_fleet_viewer",
        "lhi_fleet_operations.rule_lhi_fleet_incident_company": "lhi_security.group_lhi_fleet_viewer",
        "lhi_funding_opportunity.rule_lhi_funding_opportunity_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_leave_bridge.rule_lhi_unified_inbox_personal": "lhi_security.group_lhi_approvals_viewer",
        "lhi_partner_management.rule_lhi_subaward_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_programme_management.rule_lhi_project_budget_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_programme_management.rule_lhi_project_budget_line_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_programme_management.rule_lhi_activity_allocation_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_programme_management.rule_lhi_activity_memo_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_programme_management.rule_lhi_execution_request_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_programme_management.rule_lhi_payment_retirement_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_procurement.rule_lhi_sourcing_company": "lhi_security.group_lhi_procurement_viewer",
        "lhi_procurement.rule_lhi_bid_company": "lhi_security.group_lhi_procurement_viewer",
        "lhi_procurement_commitment.rule_lhi_procurement_commitment_company": "lhi_security.group_lhi_procurement_viewer",
        "lhi_proposal_management.rule_lhi_proposal_workspace_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_proposal_budget.rule_lhi_proposal_budget_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_proposal_budget.rule_lhi_proposal_submission_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_workplan.rule_lhi_workplan_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_workplan.rule_lhi_workplan_activity_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_risk.rule_lhi_project_risk_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_issue.rule_lhi_project_issue_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_reporting.rule_lhi_project_report_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_compliance.rule_lhi_reporting_calendar_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_amendment.rule_lhi_project_amendment_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_project_closeout.rule_lhi_project_closeout_company": "lhi_security.group_lhi_programme_viewer",
        "lhi_results_framework.rule_lhi_results_framework_company": "lhi_security.group_lhi_meal_viewer",
        "lhi_results_framework.rule_lhi_results_element_company": "lhi_security.group_lhi_meal_viewer",
        "lhi_results_framework.rule_lhi_indicator_company": "lhi_security.group_lhi_meal_viewer",
        "lhi_meal.rule_lhi_meal_data_company": "lhi_security.group_lhi_meal_viewer",
        "lhi_meal.rule_lhi_meal_data_sensitive": "lhi_security.group_lhi_meal_viewer",
        "lhi_meal.rule_lhi_meal_evidence_company": "lhi_security.group_lhi_meal_viewer",
        "lhi_meal.rule_lhi_meal_evidence_sensitive": "lhi_security.group_lhi_meal_viewer",
        "lhi_meal.rule_lhi_meal_initiative_company": "lhi_security.group_lhi_meal_viewer",
        "lhi_vendor_management.rule_lhi_vendor_company": "lhi_security.group_lhi_procurement_viewer",
        "lhi_purchase_request.rule_lhi_budget_line_company": "lhi_security.group_lhi_procurement_viewer",
        "lhi_purchase_request.rule_lhi_purchase_request_company": "lhi_security.group_lhi_procurement_viewer",
        "lhi_purchase_order.rule_lhi_purchase_order_company": "lhi_security.group_lhi_procurement_viewer",
        "lhi_purchase_order.rule_lhi_receipt_company": "lhi_security.group_lhi_procurement_viewer",
    }
    for rule_xmlid, group_xmlid in rule_groups.items():
        with cr.savepoint():
            changes += _set_rule_group(env, rule_xmlid, group_xmlid)

    env.registry.clear_cache()
    _logger.info(
        "LHI RBAC migration completed idempotently with %s relationship updates",
        changes,
    )
