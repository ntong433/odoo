import { describe, expect, test } from "@odoo/hoot";
import {
    buildChunkRanges,
    nextOffsetFromRanges,
} from "@lhi_sharepoint_storage/js/sharepoint_many2many_binary";

describe("SharePoint resumable upload helpers", () => {
    test("builds sequential non-overlapping ranges", () => {
        expect(buildChunkRanges(1000, 320)).toEqual([
            [0, 320],
            [320, 640],
            [640, 960],
            [960, 1000],
        ]);
    });

    test("uses the first nextExpectedRanges offset", () => {
        expect(nextOffsetFromRanges(["655360-"], 0)).toBe(655360);
        expect(nextOffsetFromRanges([], 320)).toBe(320);
    });
});
