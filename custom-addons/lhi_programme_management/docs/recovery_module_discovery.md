# LHI application discovery report

Repository evidence recorded on 2026-07-20 from commit
`26de48d3cf837918b6bee29467aa56f3f74b883f` plus the pending recovery patch.
All listed source directories are present in the workspace custom-addons path.
The Coolify image, configured production `addons_path`, database module state,
and user-specific menu visibility cannot be inspected from this development
shell and must be verified inside the running production container.

| Application | Technical addon | Installable / application | Root menu XML ID | Root action XML ID | Principal functional access |
|---|---|---:|---|---|---|
| Programs & Grants | `lhi_programme_management` | Yes / Yes | `lhi_base.menu_lhi_root` | `lhi_base.action_lhi_project` | Programs and Grants viewer or an implied programme role |
| MEAL | `lhi_meal` with root supplied by `lhi_results_framework` | Yes / Yes | `lhi_results_framework.menu_lhi_meal_root` | `lhi_results_framework.action_lhi_results_framework` | MEAL officer or sensitive-data role as applicable |
| Media & Communications | `lhi_media_communications` | Yes / Yes | `lhi_media_communications.menu_lhi_media_root` | `lhi_media_communications.action_lhi_media_request` | Media viewer/requester/officer/reviewer/manager |
| Procurement | `lhi_purchase_request` | Yes / No | `lhi_purchase_request.menu_lhi_procurement_root` | `lhi_purchase_request.action_lhi_purchase_request` | Procurement officer or manager |
| Fleet | `lhi_fleet_operations` | Yes / Yes | `fleet.menu_root` | Native Fleet root action | Fleet officer |
| Inventory | `lhi_inventory` | Yes / No | `stock.menu_stock_root` | Native Inventory root action | Store officer |
| Assets | `lhi_asset_management` | Yes / Yes | `lhi_asset_management.menu_lhi_asset` | `lhi_asset_management.action_lhi_asset` | Store officer |
| Approvals | `lhi_approval_matrix` | Yes / No | `lhi_approval_matrix.menu_lhi_my_pending_approvals` | `lhi_approval_matrix.action_lhi_my_pending_approvals` | Assigned approver, manager, or executive approver |
| Reports | `lhi_reporting_hub` | Yes / Yes | `lhi_reporting_hub.menu_lhi_reporting_hub_root` | Root has child actions; no direct root action | Manager, programme director, or finance reviewer |

## Discovery interpretation

- `application=False` explains why Procurement, Inventory, Approvals, and the
  MEAL root provider may not appear as separately activatable Apps under the
  default Apps filter. Their source can still be installed as a dependency and
  their menus can be available after installation.
- A present source directory does not prove it is inside the running image or
  configured production `addons_path`.
- An installed module does not guarantee menu visibility. Native menu/action
  groups, model ACLs, record rules, and the user's LHI functional groups remain
  authoritative.
- In this repository the installable Programs & Grants application is
  `lhi_programme_management`. `lhi_grant_award` is a non-application dependency
  extending the canonical `lhi.award` model from `lhi_base`.
- Media relational fields resolve to `lhi.award`, which is defined by the
  explicit `lhi_base` dependency; no `lhi.grant.award` comodel remains.
- Production-specific missing-module reasons must be determined from the
  running image, `addons_path`, Apps update result, dependency state, and the
  affected user's groups. No production state is inferred in this report.
