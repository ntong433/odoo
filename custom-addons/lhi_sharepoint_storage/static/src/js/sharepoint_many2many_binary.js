import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import {
    Many2ManyBinaryField,
    many2ManyBinaryField,
} from "@web/views/fields/many2many_binary/many2many_binary_field";


export function buildChunkRanges(size, chunkSize) {
    const ranges = [];
    for (let start = 0; start < size; start += chunkSize) {
        ranges.push([start, Math.min(start + chunkSize, size)]);
    }
    return ranges;
}

export function nextOffsetFromRanges(ranges, fallback) {
    if (!ranges || !ranges.length) {
        return fallback;
    }
    const offset = Number.parseInt(String(ranges[0]).split("-", 1)[0], 10);
    return Number.isFinite(offset) ? offset : fallback;
}

export class LhiSharePointMany2ManyBinaryField extends Many2ManyBinaryField {
    static template = "lhi_sharepoint_storage.Many2ManyBinaryField";

    async uploadFile(file) {
        if (!this.props.record.resId) {
            this.notification.add(_t("Save the business record before adding documents."), {
                type: "warning",
            });
            return;
        }
        const session = await rpc("/lhi/sharepoint/upload/session", {
            model: this.props.record.resModel,
            record_id: this.props.record.resId,
            field_name: this.props.name,
            name: file.name,
            size: file.size,
            mime_type: file.type || "application/octet-stream",
        });
        let finalItem = null;
        let offset = 0;
        while (offset < file.size) {
            const end = Math.min(offset + session.chunk_size, file.size);
            const response = await fetch(session.upload_url, {
                method: "PUT",
                headers: {
                    "Content-Range": `bytes ${offset}-${end - 1}/${file.size}`,
                },
                body: file.slice(offset, end),
            });
            if (![200, 201, 202].includes(response.status)) {
                throw new Error(_t("SharePoint rejected an upload fragment."));
            }
            const payload = await response.json();
            if (response.status === 202) {
                offset = nextOffsetFromRanges(payload.nextExpectedRanges, end);
            } else {
                finalItem = payload;
                offset = file.size;
            }
        }
        if (!finalItem?.id) {
            throw new Error(_t("SharePoint did not confirm the completed upload."));
        }
        const confirmed = await rpc("/lhi/sharepoint/upload/confirm", {
            document_uuid: session.document_uuid,
            item_id: finalItem.id,
        });
        await this.operations.saveRecord([confirmed.attachment_id]);
    }

    async onDirectFilesSelected(event) {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        for (const file of files) {
            try {
                await this.uploadFile(file);
                this.notification.add(_t("SharePoint confirmed the document upload."), {
                    type: "success",
                });
            } catch (error) {
                this.notification.add(error.message || _t("The SharePoint upload failed."), {
                    title: _t("Uploading error"),
                    type: "danger",
                    sticky: true,
                });
            }
        }
    }

    async onFileRemove(deleteId) {
        await rpc("/lhi/sharepoint/attachment/remove", { attachment_id: deleteId });
        const record = this.props.record.data[this.props.name].records.find(
            (value) => value.resId === deleteId
        );
        if (record) {
            this.operations.removeRecord(record);
        }
    }
}

export const lhiSharePointMany2ManyBinaryField = {
    ...many2ManyBinaryField,
    component: LhiSharePointMany2ManyBinaryField,
    relatedFields: [
        ...many2ManyBinaryField.relatedFields,
        { name: "lhi_storage_state", type: "selection" },
        { name: "lhi_remote_file_size", type: "integer" },
    ],
};

registry
    .category("fields")
    .add("lhi_sharepoint_many2many_binary", lhiSharePointMany2ManyBinaryField);
