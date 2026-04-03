import { expect, test } from "@odoo/hoot";
import { contains } from "@web/../tests/web_test_helpers";
import { setupEditor } from "../_helpers/editor";
import { expandToolbar } from "../_helpers/toolbar";

test("should apply border color", async () => {
    await setupEditor(
        `<table class="o_selected_table"><tbody><tr>
            <td class="o_selected_td">11[]</td>
        </tr></tbody></table>`,
        {
            // Force a predefined color because they can be different.
            styleContent: ":root { --600: rgb(126, 87, 192); }",
        }
    );
    await expandToolbar();
    await contains(".btn:has(.fa-pencil)").click();
    await contains("[data-color='600']").click();
    expect("td").toHaveStyle({ "border-color": "rgb(126, 87, 192)" }, { inline: true });
});

test("should apply border width", async () => {
    await setupEditor(`
        <table class="o_selected_table"><tbody><tr>
            <td class="o_selected_td">11[]</td>
        </tr></tbody></table>`);
    await expandToolbar();
    await contains(".btn[name='table_border_width']").click();
    await contains("button:has(.o-border-preview[style*='border-width: 3px'])").click();
    expect("td").toHaveStyle({ "border-width": "3px" }, { inline: true });
});

test("should apply border style", async () => {
    await setupEditor(`
        <table class="o_selected_table"><tbody><tr>
            <td class="o_selected_td">11[]</td>
        </tr></tbody></table>`);
    await expandToolbar();
    await contains(".btn[name='table_border_style']").click();
    await contains("button:has(.o-border-preview[style*='border-style: dotted'])").click();
    expect("td").toHaveStyle({ "border-style": "dotted" }, { inline: true });
});

test("should remove all border specification on color delete", async () => {
    await setupEditor(`
        <table class="o_selected_table"><tbody><tr>
            <td class="o_selected_td" style="border-color: #FF9C00; border-width: 1px; border-style: solid;">11[]</td>
        </tr></tbody></table>`);
    await expandToolbar();
    await contains(".btn:has(.fa-pencil)").click();
    await contains(".o_font_color_selector .fa-trash").click();
    expect("td").not.toHaveStyle("border-color", { inline: true });
    expect("td").not.toHaveStyle("border-width", { inline: true });
    expect("td").not.toHaveStyle("border-style", { inline: true });
});
