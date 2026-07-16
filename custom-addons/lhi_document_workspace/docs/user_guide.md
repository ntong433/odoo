# User guide

Open an authorized project or business record and select its **Documents** or
**Document Workspace** tab.

## Browse and preview

- Search by document name.
- Filter by category or workflow state.
- Where available, switch between **This record** and **Permitted project
  scope**.
- Select a document name to preview it inside Odoo.

The workspace shows at most the newest 100 permitted items at once. Narrow the
search when the information banner says more documents exist.

## Available actions

- **Preview** opens the inline Microsoft preview.
- **Edit in Microsoft 365** opens Word, Excel, or PowerPoint for the web in a
  new tab and leaves the Odoo record open.
- **Open in desktop application** invokes the applicable Office desktop
  protocol.
- **Download** uses the existing secure SharePoint-backed download route.
- **Version history** shows bounded SharePoint version metadata.
- **Copy governed link** copies the existing authenticated SharePoint URL. It
  does not create an anonymous link.
- **Upload new version** and **Replace content** update the same immutable
  SharePoint item.
- **Archive** moves the document to the SharePoint recycle bin.

Unavailable actions are disabled when the user lacks Odoo permission, the
record is workflow-locked, the file type is not supported, or SharePoint has
not confirmed the document as available.

## Create a document from a template

1. Select **New from template**.
2. Choose an approved Office template.
3. Enter the new document name.
4. Select **Create and edit**.

The browser opens a blank tab directly from the click. After Odoo and
SharePoint confirm the new document, that tab opens Microsoft 365 for editing.
If the browser reports that the tab was blocked, allow popups for
`https://work.lhinigeria.org` and try again.

## Returning from Microsoft 365

Keep the original Odoo tab open while editing. When you return to it, the
workspace refreshes the document's version, ETag, modified time, and
modified-by identity. A notification appears when a newer SharePoint version
is detected.

Microsoft 365 and SharePoint authenticate the actual Entra user. Ask an
administrator to correct the relevant Odoo or SharePoint access if an action is
denied; do not request an anonymous sharing link.
