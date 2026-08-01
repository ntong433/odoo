# LHI application access user guide

Your application assignment now controls every navigation surface in the same
way: dashboard cards, sidebar, launcher, top/root menus and direct actions.

## What each access level means

- **No Access**: the application is not shown. A saved direct link is also
  denied.
- **Viewer**: the application is shown and permitted records can be read, but
  protected records cannot be changed.
- **Officer/User**: the application is shown and assigned operational work is
  available, subject to company, HUB, office, department, project and ownership
  rules.
- **Manager**: the application is shown with the approved management and
  configuration functions for that app.

Memo is available to all internal LHI employees. A Memo role does not expose
signature-provider administration or technical document fields.

## Warehouse Officer example

A Warehouse Officer such as the James Bassey regression user receives:

| Application | Expected result |
|---|---|
| HUB and warehouse functions | Visible and usable within assigned HUB scope |
| Inventory | Visible for the warehouse role |
| Operations Overview | Hidden unless Operations is assigned separately |
| Programs and Grants | Hidden unless a Programs role is assigned separately |
| Asset Register | Hidden unless an Asset role is assigned separately |
| Procurement | Hidden unless a Procurement role is assigned separately |
| Memo | Visible |
| Administrative tools | Hidden |

## If access looks wrong

Reload the web client once after an administrator changes your roles. If the
dashboard, sidebar and launcher still disagree, report the application name,
your expected business role and the navigation surface. Do not ask for generic
Internal User, Settings or administrator rights as a workaround.

An access error from an old bookmark is expected after permission removal. It
confirms that server security is working even when a URL was previously saved.
