# LHI Memo Management

`lhi_memo_management` provides the governed LHI internal-memo lifecycle for
Odoo 19 Community. Odoo owns the business record and authorization, Microsoft
Word for the web owns authoring, SharePoint Online owns every persistent
business-document byte, and LHI Sign/OpenSign owns signatures and its audit
certificate.

## Architecture

```text
Employee -> Odoo memo -> SharePoint DOCX -> Word for the web
                           |
                           +-> exact version -> Graph PDF conversion
                                                |
                                                v
Approval matrix -> strict recipients -> LHI Sign preparation/signing
                                                |
                                                v
                              signed PDF + certificate -> SharePoint
                                                |
                                                v
                                      Odoo memo completed
```

No project, grant, or procurement reference is required for a standalone
departmental memo. Context-specific references become mandatory only when the
corresponding context is selected.

The custom sidebar places the Memos workspace under **General**. It never adds
a direct sidebar shortcut to the Raise Memo form.

## State machine

```text
draft -> authoring -> ready_for_preparation -> preparing
       -> requester_signature_pending -> under_approval
       -> final_signature_pending -> completed

active states -> returned -> authoring (new PDF/hash/envelope)
active states -> rejected | expired | cancelled | failed
terminal historical record -> superseded
```

Transitions are enforced by `lhi.memo._transition`; UI visibility is not an
authorization control.

## Document locations

The existing controlled-documents library and existing ERP SharePoint site are
used. Each memo is routed under:

```text
Memos/{Year}/{Department}/{Memo Reference}/
```

Files are named `{reference}.docx`, `{reference}-Submitted.pdf`,
`{reference}-Signed.pdf`, and `{reference}-Audit-Certificate.pdf`. Odoo stores
immutable DriveItem IDs, hashes, version metadata, workflow state, and audit
links; it does not retain newly received document binaries.

See [administrator configuration](docs/administrator_guide.md),
[user workflow](docs/user_guide.md), and
[deployment and rollback](docs/deployment_and_rollback.md).
