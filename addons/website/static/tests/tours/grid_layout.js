import {
    clickOnSave,
    clickOnSnippet,
    insertSnippet,
    registerWebsitePreviewTour,
    goBackToBlocks,
} from "@website/js/tours/tour_utils";

const snippet = {
    id: "s_text_image",
    name: "Text - Image",
    groupName: "Content",
};

registerWebsitePreviewTour(
    "website_replace_grid_image",
    {
        edition: true,
    },
    () => [
        ...insertSnippet(snippet),
        {
            // TODO: should check if o_loading_screen is not present (TO check with PIPU)
            // Await step in the history
            trigger: `:iframe:has(#wrap[contenteditable='true'])`,
        },
        ...clickOnSnippet(snippet),
        {
            content: "Toggle to grid mode",
            trigger: "[data-action-id='setGridLayout']",
            run: "click",
        },
        {
            content: "Replace image",
            trigger: ":iframe .s_text_image img",
            run: "dblclick",
        },
        {
            content: "Pick new image",
            trigger:
                '.o_select_media_dialog .o_button_area[aria-label="s_banner_default_image.jpg"]',
            run: "click",
        },
        {
            content: `Target the "Text - Image" group`,
            trigger: `.options-container[data-container-title="Text - Image"]:has(.options-container-label i.fa-caret-right) button[title="Select only this block"]`,
            run: "click",
        },
        goBackToBlocks(),
        {
            content: "Add new image to grid",
            trigger:
                ".o_block_tab:not(.o_we_ongoing_insertion) .o_snippet[name='Image'].o_draggable .o_snippet_thumbnail",
            run: "drag_and_drop :iframe .s_text_image .row.o_grid_mode",
        },
        {
            content: "Pick new image",
            trigger:
                '.o_select_media_dialog .o_button_area[aria-label="s_banner_default_image2.webp"]',
            run: "click",
        },
        {
            content: "Replace new image",
            trigger: ':iframe .s_text_image img[src*="s_banner_default_image2.webp"]',
            run: "dblclick",
        },
        {
            content: "Pick new image",
            trigger:
                '.o_select_media_dialog .o_button_area[aria-label="s_banner_default_image.jpg"]',
            run: "click",
        },
        ...clickOnSave(),
    ]
);
