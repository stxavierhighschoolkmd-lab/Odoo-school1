import { after, before, expect, test } from "@odoo/hoot";
import { click, queryOne } from "@odoo/hoot-dom";
import { setupInteractionWhiteList, startInteractions } from "@web/../tests/public/helpers";
import { contains } from "@web/../tests/web_test_helpers";

setupInteractionWhiteList("website.whatsapp");

let originalWindowOpen;

function mockWindowOpen() {
    originalWindowOpen = window.open;
    window.open = (url) => {
        expect.step(`window_open ${url}`);
    };
}

function unmockWindowOpen() {
    window.open = originalWindowOpen;
}

before(() => {
    mockWindowOpen();
});

after(() => {
    unmockWindowOpen();
});

function getWhatsappSnippet(dataWhatsappNumber = "") {
    const dataWhatsappNumberAttr = dataWhatsappNumber
        ? `data-whatsapp-number="${dataWhatsappNumber}"`
        : "";
    return `
    <section class="s_whatsapp position-fixed bottom-0 o_no_save" ${dataWhatsappNumberAttr}>
        <div class="position-relative d-inline-flex o_not_editable">
            <i class="fa fa-2x fa-whatsapp wa-fab rounded-circle d-flex align-items-center justify-content-center shadow-lg o_pos_right"></i>
            <span class="notification-badge bg-danger position-absolute rounded-circle"></span>
        </div>
        <div class="chatbox bg-white rounded-3 position-absolute shadow-lg overflow-hidden mb-2 d-none">
            <div class="header d-flex align-items-center p-2 text-white">
                <div class="o_not_editable">
                    <img class="wa-agent-img rounded-circle" src="/website/static/src/img/snippets_demo/s_whatsapp_agent.webp" alt="agent"/>
                </div>
                <div class="ms-2 me-auto flex-grow-1 d-flex flex-column lh-1">
                    <p class="wa-agent-name text-break mb-1 fw-bold">Jane Doe</p>
                    <p class="wa-agent-description m-0 text-break">Online</p>
                </div>
                <div class="o_not_editable">
                    <button class="btn wa-close-btn p-2 text-white">
                        <i class="fa fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="wa-messages p-2">
                <p class="wa-agent-msg text-break w-75 bg-white rounded-3 p-2 m-0 fs-6">Hi there 👋
                    <br/>How can I help you?
                </p>
            </div>
            <div class="wa-user-input">
                <!-- Regular input box -->
                <div class="wa-input-box border-top align-items-end">
                    <textarea name="wa_message" class="wa-user-message flex-grow-1 p-2 border-0" placeholder="Enter Your Message..." rows="1"></textarea>
                    <div class="o_not_editable">
                        <button class="wa-send border-0 p-2 text-white">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M2 21l21-9L2 3v7l15 2-15 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <!-- CTA mode -->
                <div class="wa-cta-box justify-content-center p-2 border-top">
                    <button class="wa-cta-btn d-flex align-items-center gap-2 px-5 py-3 fw-semibold rounded-4 shadow-sm border-0 text-white" >
                        <div class="o_not_editable">
                            <i class="fa fa-whatsapp"></i>
                        </div>
                        <p class="d-inline m-0">Start Conversation</p>
                    </button>
                </div>
            </div>
            <div class="wa-warning alert alert-warning d-none m-2 fs-6">
                <i class="fa fa-info-circle me-1"></i>
                <p class="d-inline m-0">
                    Messaging is not available. Please contact us by another way.
                </p>
            </div>
        </div>
    </section>
`;
}

test("Drop Whatsapp snippet and verify redirection to company number", async () => {
    await startInteractions(getWhatsappSnippet("1234567890"));
    expect(".s_whatsapp").toHaveCount(1);
    const chatboxEl = queryOne(".s_whatsapp .chatbox");
    expect(chatboxEl).toHaveClass("d-none");

    // Simulate opening and closing the chatbox.
    await click(".wa-fab");
    expect(chatboxEl).not.toHaveClass("d-none");
    await click(".wa-close-btn");
    expect(chatboxEl).toHaveClass("d-none");
    await click(".wa-fab");

    // Simulate entering a message and sending it with Enter.
    await contains(".wa-user-message").edit("Hello, I need help!");
    await contains(".wa-user-message").press("Enter");

    // Verify the opened URL
    expect.verifySteps(["window_open https://wa.me/1234567890?text=Hello%2C%20I%20need%20help!"]);
});

test("Drop Whatsapp snippet and verify warning when no number is configured", async () => {
    await startInteractions(getWhatsappSnippet());
    expect(".s_whatsapp").toHaveCount(1);
    expect(".s_whatsapp .wa-warning").not.toHaveClass("d-none");
    expect(".s_whatsapp .wa-user-input").toHaveClass("d-none");
});
