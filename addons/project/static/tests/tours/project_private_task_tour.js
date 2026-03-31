import { registry } from "@web/core/registry";

/**
 * This tour tests that a Private task (To-Do with no project) opened via the
 * Project app retains its "Private" placeholder and is not treated as required.
 */
registry.category("web_tour.tours").add("project_private_task_tour", {
    url: "/odoo/my-tasks?view_type=list",
    steps: () => [
        {
            content: "Wait for list view to load",
            trigger: ".o_list_view .o_data_row",
        },
        {
            content: "Open the private task",
            trigger: ".o_data_row .o_data_cell:contains('Private Task Test')",
            run: "click",
        },
        {
            content: "Wait for form view to load then reload to trigger field attribute merging",
            trigger: ".o_form_view .o_field_widget[name='project_id']",
            expectUnloadPage: true,
            run() {
                window.location.reload();
            },
        },
        {
            content: "After reload, project field should still show the Private placeholder",
            trigger: "div[name='project_id'] .o_many2one.private_placeholder input[placeholder='Private']",
        },
    ],
});
