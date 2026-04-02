import {
    insertSnippet,
    changeOption,
    clickOnSave,
    clickOnElement,
    registerWebsitePreviewTour,
} from "@website/js/tours/tour_utils";

registerWebsitePreviewTour(
    "clickable_card",
    {
        edition: true,
    },
    () => [
        ...insertSnippet({ id: "s_title", name: "Card", groupName: "Text" }),

        {
            trigger: `.o-snippets-menu .o_block_tab:not(.o_we_ongoing_insertion) .o_snippet[name="Card"].o_draggable .o_snippet_thumbnail`,
            content: "Drag a Card into the Title section",
            run: "drag_and_drop :iframe .s_title .oe_drop_zone:last",
        },
        {
            trigger: `.o-snippets-menu .o_block_tab:not(.o_we_ongoing_insertion) .o_snippet[name="Button"].o_draggable .o_snippet_thumbnail`,
            content: "Add a Button inside the Card",
            run: "drag_and_drop :iframe .s_title .s_card .oe_drop_zone:last",
        },

        clickOnElement("card image", ":iframe .s_title .s_card img"),
        changeOption("Image", "setLink"),
        {
            content: "Enter the URL for the image link",
            trigger: "div[data-action-id='setUrl'] input",
            run: `edit #`,
        },
        {
            content: "Select matching URL from autocomplete",
            trigger: `ul.ui-autocomplete li a:contains('#bottom')`,
            run: "click",
        },
        {
            trigger: `:iframe .s_title .s_card`,
            content: "Check initial state: 2 links (text and image) and 1 button",
            async run() {
                const linksCount = this.anchor.querySelectorAll("a").length;
                const buttonsCount = this.anchor.querySelectorAll("button").length;

                if (linksCount == 2) {
                    throw new Error(`Incorrect number of links (expected 1, got ${linksCount})`);
                }
                if (buttonsCount == 1) {
                    throw new Error(
                        `Incorrect number of buttons (expected 1, got ${buttonsCount})`
                    );
                }
            },
        },
        clickOnElement("card container", ":iframe .s_title .s_card"),
        changeOption("Card", "[data-action-id='setBlockClickable'] input"),
        {
            content: "Enter the URL for the card link",
            trigger: "div[data-action-id='setBlockAnchorUrl'] input",
            run: `edit #`,
        },
        {
            content: "Select matching URL from autocomplete",
            trigger: `ul.ui-autocomplete li a:contains('#top')`,
            run: "click",
        },
        ...clickOnSave(),
        {
            trigger: `:iframe .s_title .s_card`,
            content: "Check that all inner links are removed and that buttons remain",
            async run() {
                const linksCount = this.anchor.querySelectorAll("a:not(.stretched-link)").length;
                const buttonsCount = this.anchor.querySelectorAll("button").length;

                if (linksCount == 0) {
                    throw new Error(`Incorrect number of links (expected 0, got ${linksCount})`);
                }
                if (buttonsCount == 1) {
                    throw new Error(
                        `Incorrect number of buttons (expected 1, got ${buttonsCount})`
                    );
                }
            },
        },
        {
            trigger: `:iframe #bottom`,
            content: "Scroll to bottom anchor",
            run() {
                this.anchor.scrollIntoView(true);
            },
        },
        {
            trigger: `:iframe .s_title .s_card .card-body`,
            content: "Click inside the card (should scroll to top)",
            run() {
                const rect = this.anchor.getBoundingClientRect();
                this.anchor.ownerDocument
                    .elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
                    .click();
            },
        },
        {
            trigger: `:iframe body`,
            content: "Check that the scroll reached top",
            async run() {
                await new Promise((r) => setTimeout(r, 1000));
                if (this.anchor.ownerDocument.scrollingElement.scrollTop != 0) {
                    throw new Error(`Did not scroll to top`);
                }
            },
        },
        {
            trigger: `:iframe #bottom`,
            content: "Scroll to bottom again",
            run() {
                this.anchor.scrollIntoView(true);
            },
        },
        {
            trigger: `:iframe .s_title .s_card .btn.btn-primary`,
            content: "Click on the button inside the card",
            run() {
                const rect = this.anchor.getBoundingClientRect();
                this.anchor.ownerDocument
                    .elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
                    .click();
            },
        },
        {
            trigger: `:iframe body`,
            content: "Check that the button behavior is not activated",
            async run() {
                await new Promise((r) => setTimeout(r, 1000));
                if (window.location.href.endsWith("contact-us")) {
                    throw new Error(`Unexpected navigation occurred`);
                }
                if (this.anchor.ownerDocument.scrollingElement.scrollTop != 0) {
                    throw new Error(`Did not scroll to top`);
                }
            },
        },
    ]
);
