import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    onWillUpdateProps,
    useRef,
    useState,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";


export function nextOffsetFromRanges(ranges, fallback) {
    if (!ranges || !ranges.length) {
        return fallback;
    }
    const offset = Number.parseInt(String(ranges[0]).split("-", 1)[0], 10);
    return Number.isFinite(offset) ? offset : fallback;
}

export function appendWebMode(url) {
    const parsed = new URL(url);
    parsed.searchParams.set("web", "1");
    return parsed.toString();
}

export function desktopOfficeUri(officeType, url) {
    const schemes = {
        word: "ms-word",
        excel: "ms-excel",
        powerpoint: "ms-powerpoint",
    };
    return `${schemes[officeType]}:ofe|u|${url}`;
}

export function uploadRetryDelayMs(retryAfter, attempt) {
    const seconds = Number.parseInt(retryAfter || "", 10);
    if (Number.isFinite(seconds) && seconds >= 0) {
        return Math.min(seconds * 1000, 60000);
    }
    return Math.min(1000 * 2 ** attempt, 30000);
}

export class LhiDocumentWorkspace extends Component {
    static template = "lhi_document_workspace.DocumentWorkspace";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInput = useRef("versionFileInput");
        this.state = useState({
            loading: true,
            documents: [],
            templates: [],
            selectedUuid: null,
            previewUrl: null,
            query: "",
            category: "",
            workflowState: "",
            scope: this.props.record.resModel === "lhi.project" ? "project" : "record",
            projectScopeAvailable: false,
            projectName: "",
            truncated: false,
            versions: [],
            versionsDocument: null,
            showVersions: false,
            showTemplateDialog: false,
            selectedTemplateId: "",
            templateFilename: "",
            creating: false,
            uploading: false,
        });
        this.pendingVersion = null;
        this.editedDocumentUuids = new Set();
        this.refreshTimer = null;
        this.onWindowFocus = this.onWindowFocus.bind(this);
        this.onVisibilityChange = this.onVisibilityChange.bind(this);

        onWillStart(async () => {
            await this.loadWorkspace();
        });
        onMounted(() => {
            window.addEventListener("focus", this.onWindowFocus);
            document.addEventListener("visibilitychange", this.onVisibilityChange);
        });
        onWillUnmount(() => {
            window.removeEventListener("focus", this.onWindowFocus);
            document.removeEventListener("visibilitychange", this.onVisibilityChange);
            if (this.refreshTimer) {
                window.clearTimeout(this.refreshTimer);
            }
        });
        onWillUpdateProps(async (nextProps) => {
            if (
                nextProps.record.resId !== this.props.record.resId ||
                nextProps.record.resModel !== this.props.record.resModel
            ) {
                this.state.selectedUuid = null;
                this.state.previewUrl = null;
                this.state.scope =
                    nextProps.record.resModel === "lhi.project" ? "project" : "record";
                await this.loadWorkspace(nextProps);
            }
        });
    }

    get recordId() {
        return this.props.record.resId;
    }

    get modelName() {
        return this.props.record.resModel;
    }

    async callRecord(method, extraArgs = [], props = this.props) {
        return this.orm.call(props.record.resModel, method, [
            [props.record.resId],
            ...extraArgs,
        ]);
    }

    async loadWorkspace(props = this.props) {
        if (!props.record.resId) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        try {
            const [workspace, templates] = await Promise.all([
                this.callRecord(
                    "lhi_workspace_get",
                    [
                        this.state.query,
                        this.state.category,
                        this.state.workflowState,
                        this.state.scope,
                        100,
                    ],
                    props
                ),
                this.callRecord("lhi_workspace_templates", [], props).catch(() => []),
            ]);
            this.state.documents = workspace.documents;
            this.state.projectScopeAvailable = workspace.project_scope_available;
            this.state.projectName = workspace.project_name || "";
            this.state.truncated = workspace.truncated;
            this.state.templates = templates;
            if (
                this.state.selectedUuid &&
                !this.state.documents.some((value) => value.uuid === this.state.selectedUuid)
            ) {
                this.state.selectedUuid = null;
                this.state.previewUrl = null;
            }
        } catch (error) {
            this.notifyError(error, _t("The document workspace could not be loaded."));
        } finally {
            this.state.loading = false;
        }
    }

    notifyError(error, fallback) {
        this.notification.add(error?.message || fallback, {
            title: _t("Document workspace"),
            type: "danger",
            sticky: true,
        });
    }

    selectDocument(document) {
        if (!document.can_preview) {
            this.notification.add(_t("This document is not available for preview."), {
                type: "warning",
            });
            return;
        }
        this.state.selectedUuid = document.uuid;
        this.state.previewUrl = `${document.preview_url}?fresh=${Date.now()}`;
    }

    async runOpenAction(document, action, newTab = true) {
        const opened = newTab ? window.open("about:blank", "_blank") : null;
        if (newTab && !opened) {
            this.notification.add(
                _t("Allow popups for this Odoo site, then try the Microsoft 365 action again."),
                { type: "warning" }
            );
            return;
        }
        try {
            const result = await this.callRecord("lhi_workspace_action", [
                document.uuid,
                action,
            ]);
            this.editedDocumentUuids.add(document.uuid);
            if (opened) {
                opened.opener = null;
                opened.location.replace(result.url);
            } else {
                window.location.href = result.url;
            }
        } catch (error) {
            opened?.close();
            this.notifyError(error, _t("Microsoft 365 could not open the document."));
        }
    }

    async editDocument(document) {
        await this.runOpenAction(document, "edit");
    }

    async openDesktop(document) {
        await this.runOpenAction(document, "desktop", false);
    }

    async downloadDocument(document) {
        await this.runOpenAction(document, "download");
    }

    async copyGovernedLink(document) {
        try {
            const result = await this.callRecord("lhi_workspace_action", [
                document.uuid,
                "governed_link",
            ]);
            await navigator.clipboard.writeText(result.url);
            this.notification.add(_t("Governed SharePoint link copied."), {
                type: "success",
            });
        } catch (error) {
            this.notifyError(error, _t("The governed link could not be copied."));
        }
    }

    async showVersions(document) {
        try {
            this.state.versions = await this.callRecord("lhi_workspace_versions", [
                document.uuid,
            ]);
            this.state.versionsDocument = document;
            this.state.showVersions = true;
        } catch (error) {
            this.notifyError(error, _t("Version history could not be loaded."));
        }
    }

    chooseVersionFile(document, action) {
        this.pendingVersion = { document, action };
        this.fileInput.el.click();
    }

    async uploadVersionFragment(uploadUrl, file, offset, end) {
        let lastError = null;
        for (let attempt = 0; attempt < 5; attempt++) {
            const controller = new AbortController();
            const timeout = window.setTimeout(() => controller.abort(), 120000);
            try {
                const response = await fetch(uploadUrl, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/octet-stream",
                        "Content-Range": `bytes ${offset}-${end - 1}/${file.size}`,
                    },
                    body: file.slice(offset, end),
                    signal: controller.signal,
                });
                if (
                    ![429, 500, 502, 503, 504].includes(response.status) ||
                    attempt === 4
                ) {
                    return response;
                }
                await new Promise((resolve) =>
                    window.setTimeout(
                        resolve,
                        uploadRetryDelayMs(response.headers.get("Retry-After"), attempt)
                    )
                );
            } catch (error) {
                lastError = error;
                if (attempt === 4) {
                    throw error;
                }
                await new Promise((resolve) =>
                    window.setTimeout(resolve, uploadRetryDelayMs(null, attempt))
                );
            } finally {
                window.clearTimeout(timeout);
            }
        }
        throw lastError || new Error(_t("SharePoint upload retry limit reached."));
    }

    async onVersionFileSelected(event) {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (!file || !this.pendingVersion) {
            return;
        }
        const { document, action } = this.pendingVersion;
        this.pendingVersion = null;
        this.state.uploading = true;
        try {
            const session = await this.callRecord("lhi_workspace_action", [
                document.uuid,
                action,
            ]);
            if (file.size <= 0 || file.size > session.maximum_size) {
                throw new Error(_t("The selected file is empty or exceeds the policy limit."));
            }
            let offset = 0;
            let finalItem = null;
            while (offset < file.size) {
                const end = Math.min(offset + session.chunk_size, file.size);
                const response = await this.uploadVersionFragment(
                    session.upload_url,
                    file,
                    offset,
                    end
                );
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
                throw new Error(_t("SharePoint did not confirm the new version."));
            }
            const refreshed = await rpc("/lhi/document-workspace/version/confirm", {
                document_uuid: session.document_uuid,
                item_id: finalItem.id,
            });
            this.replaceDocument(refreshed);
            this.notification.add(_t("SharePoint confirmed the new document version."), {
                type: "success",
            });
        } catch (error) {
            this.notifyError(error, _t("The new version could not be uploaded."));
        } finally {
            this.state.uploading = false;
        }
    }

    async archiveDocument(document) {
        if (!window.confirm(_t("Archive this document to the SharePoint recycle bin?"))) {
            return;
        }
        try {
            await this.callRecord("lhi_workspace_action", [document.uuid, "archive"]);
            this.state.documents = this.state.documents.filter(
                (value) => value.uuid !== document.uuid
            );
            if (this.state.selectedUuid === document.uuid) {
                this.state.selectedUuid = null;
                this.state.previewUrl = null;
            }
            this.notification.add(_t("Document archived in SharePoint."), {
                type: "success",
            });
        } catch (error) {
            this.notifyError(error, _t("The document could not be archived."));
        }
    }

    openTemplateDialog() {
        if (!this.state.templates.length) {
            this.notification.add(
                _t("No approved Office templates are configured for this record type."),
                { type: "warning" }
            );
            return;
        }
        this.state.selectedTemplateId = String(this.state.templates[0].id);
        this.state.templateFilename = "";
        this.state.showTemplateDialog = true;
    }

    async createFromTemplate() {
        const filename = this.state.templateFilename.trim();
        if (!filename) {
            this.notification.add(_t("Enter a name for the new document."), {
                type: "warning",
            });
            return;
        }
        const opened = window.open("about:blank", "_blank");
        if (!opened) {
            this.notification.add(
                _t("Allow popups for this Odoo site, then create the Office document again."),
                { type: "warning" }
            );
            return;
        }
        this.state.creating = true;
        try {
            const document = await this.callRecord(
                "lhi_workspace_create_from_template",
                [
                    Number(this.state.selectedTemplateId),
                    filename,
                    crypto.randomUUID(),
                ]
            );
            this.state.documents = [document, ...this.state.documents];
            this.state.showTemplateDialog = false;
            this.editedDocumentUuids.add(document.uuid);
            opened.opener = null;
            opened.location.replace(document.edit_url);
            this.notification.add(_t("SharePoint created the Office document."), {
                type: "success",
            });
        } catch (error) {
            opened?.close();
            this.notifyError(error, _t("The Office document could not be created."));
        } finally {
            this.state.creating = false;
        }
    }

    replaceDocument(document) {
        const index = this.state.documents.findIndex(
            (value) => value.uuid === document.uuid
        );
        if (index >= 0) {
            this.state.documents.splice(index, 1, document);
        }
    }

    onWindowFocus() {
        this.scheduleFocusRefresh();
    }

    onVisibilityChange() {
        if (document.visibilityState === "visible") {
            this.scheduleFocusRefresh();
        }
    }

    scheduleFocusRefresh() {
        if (!this.editedDocumentUuids.size || this.refreshTimer) {
            return;
        }
        this.refreshTimer = window.setTimeout(async () => {
            this.refreshTimer = null;
            await this.refreshEditedDocuments();
        }, 500);
    }

    async refreshEditedDocuments() {
        const uuids = Array.from(this.editedDocumentUuids);
        if (!uuids.length) {
            return;
        }
        try {
            const refreshed = await this.callRecord("lhi_workspace_refresh", [uuids]);
            let newer = false;
            for (const document of refreshed) {
                newer ||= document.newer;
                this.replaceDocument(document);
            }
            if (newer) {
                this.notification.add(
                    _t("A newer SharePoint version is available and metadata was refreshed."),
                    { type: "info" }
                );
            }
            this.editedDocumentUuids.clear();
        } catch (error) {
            this.notification.add(
                error?.message || _t("Document metadata refresh will be retried later."),
                { type: "warning" }
            );
        }
    }
}

registry.category("fields").add("lhi_document_workspace", {
    component: LhiDocumentWorkspace,
    supportedTypes: ["boolean"],
});
