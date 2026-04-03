import { useLayoutEffect } from "@web/owl2/utils";
import { AddSnippetDialog } from "@html_builder/snippets/add_snippet_dialog";

export class WebsiteAddSnippetDialog extends AddSnippetDialog {
    static template = "website.AddSnippetDialog";

    setup() {
        super.setup();
        this.state.isMobilePreviewMode = false;

        useLayoutEffect(
            (isMobilePreviewMode) => {
                const iframeEl = this.iframeRef.el;
                const htmlEl = iframeEl.contentDocument.documentElement;
                iframeEl.classList.toggle("o_is_mobile_preview_iframe", isMobilePreviewMode);
                htmlEl.classList.toggle("o_is_mobile_preview_html", isMobilePreviewMode);
            },
            () => [this.state.isMobilePreviewMode]
        );
    }

    toggleMobilePreview() {
        this.state.isMobilePreviewMode = !this.state.isMobilePreviewMode;
    }
}
