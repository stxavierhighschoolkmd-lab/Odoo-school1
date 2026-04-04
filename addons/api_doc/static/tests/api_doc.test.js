import { animationFrame, expect, getFixture, test, waitFor } from "@odoo/hoot";
import { DocClient } from "@api_doc/doc_client";
import { mockDocIndex, mockDocModel } from "./doc_test_helpers";
import {
    contains,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";

async function mountDocClient() {
    const fixture = getFixture();
    fixture.style.height = "768px"; // Default desktop height in HOOT
    fixture.style.overflow = "auto";
    return mountWithCleanup(DocClient, {});
}

function setupMockModel(modelNames) {
    onRpc("/doc/index.json", () => {
        return mockDocIndex(modelNames);
    });
    modelNames.forEach((modelName) => {
        onRpc(`/doc/${modelName}.json`, () => {
            const model = mockDocModel(modelName);
            return model;
        });
    });
}

async function shortcutSetupDocModel(index=0, modelNames=["M1", "M2", "M3"]) {
    setupMockModel(modelNames);
    await mountDocClient();
    await waitFor(".o-doc-sidebar-content div a");
    await contains(`.o-doc-sidebar-content div a:eq(${index})`).click();
    await contains(".o-doc-model-aside .o-doc-module-checks").click();
    await waitFor(".o-doc-method");
}

test("ApiDoc: simple test, load sidebar and aside", async () => {
    setupMockModel(["M1", "M2", "M3"]);
    await mountDocClient();
    await animationFrame();
    // Check sidebar contains all models
    expect(".o-doc-sidebar-content div a").toHaveCount(3);
    expect(".o-doc-sidebar-content div a:eq(0)").toHaveText("Model_M1\nM1");
    expect(".o-doc-sidebar-content div a:eq(1)").toHaveText("Model_M2\nM2");
    expect(".o-doc-sidebar-content div a:eq(2)").toHaveText("Model_M3\nM3");
    await contains(".o-doc-sidebar-content div a:eq(0)").click();
    expect(".o-doc-model h2").toHaveText("Model_M1");
    // Check aside contains module and methods
    expect(".o-doc-model-aside .o-doc-module-checks").toHaveText("test_module");
    await contains(".o-doc-model-aside .o-doc-module-checks").click();
    // Select/Deselect + methods
    await waitFor(".o-doc-model-aside .o-doc-aside-methods")
    expect(".o-doc-model-aside .o-doc-aside-methods").toHaveCount(2);
    expect(".o-doc-model-aside .o-doc-aside-methods:eq(0)").toHaveText("method_1_M1");
    expect(".o-doc-model-aside .o-doc-aside-methods:eq(1)").toHaveText("method_2_M1");
});

test("ApiDoc: methods are parsed properly", async () => {
    await shortcutSetupDocModel();
    // Headers
    expect(".o-doc-method").toHaveCount(2);
    expect(".o-doc-method:eq(0) .o-doc-method-header").toHaveText("method_1_M1\n#\ntest_module");
    expect(".o-doc-method:eq(1) .o-doc-method-header").toHaveText("method_2_M1\n#\ntest_module");
    await contains(".o-doc-method:eq(1) .o-doc-method-header").click();
    // Route + Return Type
    expect(".o-doc-method pre").toHaveCount(2);
    expect(".o-doc-method pre:eq(0)").toHaveText("/json/2/M1/method_1_M1");
    expect(".o-doc-method pre:eq(1)").toHaveText("None");
    // Inner and return docstring
    expect(".o-doc-method .doc_method_description").toHaveCount(2);
    expect(".o-doc-method .doc_method_description:eq(0)").toHaveText("This is a method.");
    expect(".o-doc-method .doc_method_description:eq(1)").toHaveText("Some return doc");
    // Parameters
    expect(".o-doc-method .o-doc-table tr").toHaveCount(3);
    expect(".o-doc-method .o-doc-table tr:eq(1)").toHaveText("param_a list[int] null");
    expect(".o-doc-method .o-doc-table tr:eq(2)").toHaveText("param_b int null");
    // TODO: Check tooltip content
});

test("ApiDoc: fields are parsed properly", async () => {
    await shortcutSetupDocModel();
    expect(".o-doc-table").toHaveCount(4, {
        message: "There should be 4 'o-doc-table': model name + fields + 2 method parameters"
    });
    expect(".o-doc-table:eq(1) tr").toHaveCount(3);
    expect(".o-doc-table:eq(1) tr:eq(1) td").toHaveCount(6);

    const firstRow = ["field_1_M1", "string", "Field 1 M1", "optional", "", "test_module"];
    const secondRow = ["field_2_M1", "boolean", "Field 2 M1", "optional", "", "test_module"];

    firstRow.forEach((value, index) => {
        expect(`.o-doc-table:eq(1) tr:eq(1) td:eq(${index})`).toHaveText(value);
    });
    secondRow.forEach((value, index) => {
        expect(`.o-doc-table:eq(1) tr:eq(2) td:eq(${index})`).toHaveText(value);
    });
});

test("ApiDoc: request editor", async () => {
    await shortcutSetupDocModel();
});

test("ApiDoc: generate api key hyperlink", async () => {
    await shortcutSetupDocModel();
});

test("ApiDoc: run request and get rpc error", async () => {
    await shortcutSetupDocModel();
});

test("ApiDoc: pin method in url", async () => {
    await shortcutSetupDocModel();
});

test("ApiDoc: search for model", async () => {
    await shortcutSetupDocModel();
});

test("ApiDoc: search in top bar", async () => {
    await shortcutSetupDocModel();
});
