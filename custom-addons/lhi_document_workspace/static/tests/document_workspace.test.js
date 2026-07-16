import { describe, expect, test } from "@odoo/hoot";
import {
    appendWebMode,
    desktopOfficeUri,
    nextOffsetFromRanges,
    uploadRetryDelayMs,
} from "@lhi_document_workspace/js/document_workspace";


describe("LHI document workspace helpers", () => {
    test("adds browser editing without dropping existing query parameters", () => {
        expect(appendWebMode("https://tenant.sharepoint.com/doc.aspx?id=1")).toBe(
            "https://tenant.sharepoint.com/doc.aspx?id=1&web=1"
        );
    });

    test("builds Office desktop protocol links", () => {
        expect(desktopOfficeUri("word", "https://tenant/doc.docx")).toBe(
            "ms-word:ofe|u|https://tenant/doc.docx"
        );
    });

    test("resumes from SharePoint's next expected range", () => {
        expect(nextOffsetFromRanges(["983040-"], 0)).toBe(983040);
        expect(nextOffsetFromRanges([], 320)).toBe(320);
    });

    test("honors Retry-After and bounds exponential upload backoff", () => {
        expect(uploadRetryDelayMs("7", 0)).toBe(7000);
        expect(uploadRetryDelayMs(null, 3)).toBe(8000);
        expect(uploadRetryDelayMs(null, 12)).toBe(30000);
        expect(uploadRetryDelayMs("120", 0)).toBe(60000);
    });
});
