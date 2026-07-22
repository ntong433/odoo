# Memo user workflow

1. Open **Memos → Raise Memo**.
2. Select a category, title, subject, purpose, recipients, department, and an
   optional work context. Project, grant, and procurement fields are required
   only for their matching contexts.
3. Save. Odoo creates the reference and synchronously asks SharePoint to create
   the Word document. If SharePoint does not confirm storage, the memo fails
   closed and shows a safe retry option.
4. Select **Open in Word**, author and save the document in Word for the web,
   then select **Finish Authoring**.
5. Select **Prepare and Sign**. Odoo captures the current ETag/version, converts
   it to PDF through Microsoft Graph, verifies the Word item did not change
   during capture, stores the PDF in SharePoint, and opens LHI Sign in a new
   tab.
6. In LHI Sign, place signature/name/date fields for the requester and final
   authority, plus any explicitly required signer fields. Send only after
   preparation validation passes.
7. Select **Sign and Submit for Approval**. Active Odoo approval starts only
   after the provider confirms the requester signature.
8. Each participant uses **Open Approval in LHI Sign** when it is their turn.
   Later participants cannot act early.
9. Use **Track Approval** to see the route and timestamps.
10. On completion, use **View Signed Memo** and **View Audit Certificate**.

If returned, correct the original Word document and prepare a new cycle. The
old PDF, signature request, hash, and audit history remain preserved; no old
signature is transferred to changed content.
