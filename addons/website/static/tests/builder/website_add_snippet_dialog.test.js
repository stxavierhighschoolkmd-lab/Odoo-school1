import { expect, test } from "@odoo/hoot";
import { contains } from "@web/../tests/web_test_helpers";
import { confirmAddSnippet } from "@html_builder/../tests/helpers";
import {
    defineWebsiteModels,
    setupWebsiteBuilderWithSnippet,
    waitForSnippetDialog,
} from "./website_helpers";

defineWebsiteModels();

async function openSnippetDialog() {
    await contains(".o_snippet_thumbnail_area").click();
    await waitForSnippetDialog();
}

const MOBILE_BTN = ".o_add_snippet_dialog button[title='Mobile Preview']";
const SNIPPET_IFRAME = ".o_add_snippet_dialog iframe.o_add_snippet_iframe";

test("Toggling mobile preview button manages CSS classes and restores original state", async () => {
    const iframeEl = document.querySelector(SNIPPET_IFRAME);
    const iframeDoc = iframeEl.contentDocument;
    await setupWebsiteBuilderWithSnippet("s_banner");
    await openSnippetDialog();
    expect(MOBILE_BTN).toHaveCount(1);
    expect(`${MOBILE_BTN} .fa-mobile`).toHaveCount(1);

    expect(MOBILE_BTN).not.toHaveClass("text-success");
    expect(SNIPPET_IFRAME).not.toHaveClass("o_is_mobile_preview_iframe");
    expect(iframeDoc.querySelectorAll(".o_snippets_preview_row > div")).toHaveCount(2);

    await contains(MOBILE_BTN).click();
    expect(MOBILE_BTN).toHaveClass("text-success");
    expect(SNIPPET_IFRAME).toHaveClass("o_is_mobile_preview_iframe");
    expect(iframeDoc.documentElement).toHaveClass("o_is_mobile_preview_html");
    expect(iframeDoc.querySelectorAll(".o_snippets_preview_row > div")).toHaveCount(3);

    await contains(MOBILE_BTN).click();
    expect(MOBILE_BTN).not.toHaveClass("text-success");
    expect(SNIPPET_IFRAME).not.toHaveClass("o_is_mobile_preview_iframe");
    expect(iframeDoc.documentElement).not.toHaveClass("o_is_mobile_preview_html");
    expect(iframeDoc.querySelectorAll(".o_snippets_preview_row > div")).toHaveCount(2);
});

test("Selecting a snippet while mobile preview is active drops it into the website", async () => {
    const { getEditableContent } = await setupWebsiteBuilderWithSnippet("s_text_image");
    const editableContent = getEditableContent();
    await openSnippetDialog();
    await contains(MOBILE_BTN).click();
    expect(MOBILE_BTN).toHaveClass("text-success");

    await confirmAddSnippet("s_banner");
    expect(".o_add_snippet_dialog").toHaveCount(0);
    expect(editableContent.querySelectorAll("[data-snippet='s_banner']")).toHaveCount(1);
});
