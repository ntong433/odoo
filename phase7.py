assets = env["ir.attachment"].sudo().search([
    ("url", "like", "/web/assets/%"),
])

print(f"Removing {len(assets)} generated web asset attachments")
assets.unlink()
env.cr.commit()
print("Generated assets removed successfully")
