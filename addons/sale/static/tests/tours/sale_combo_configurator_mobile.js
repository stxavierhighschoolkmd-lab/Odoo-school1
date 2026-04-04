import { registry } from '@web/core/registry';
import { stepUtils } from '@web_tour/tour_service/tour_utils';
import comboConfiguratorTourUtils from '@sale/js/tours/combo_configurator_tour_utils';
import productConfiguratorTourUtils from '@sale/js/tours/product_configurator_tour_utils';

/**
 * Tour verifying that adding a combo product on mobile (isSmall=true) correctly
 * opens the combo configurator dialog and sets a non-zero price on the order line.
 *
 * On mobile, the order_line x2many renders as a kanban. Adding a product opens an
 * X2ManyFieldDialog using the inline <form> view, which uses the
 * sol_product_many2one_barcode widget. This widget must route combo products to the
 * combo configurator instead of directly saving with price=0.
 */
registry
    .category('web_tour.tours')
    .add('sale_combo_configurator_mobile', {
        url: '/odoo',
        steps: () => [
            ...stepUtils.goToAppSteps('sale.sale_menu_root', "Open the sales app"),
            {
                content: "Create new order",
                trigger: '.o-kanban-button-new, .o_list_button_add',
                run: 'click',
            },
            {
                content: "Click on customer field to open search dialog",
                trigger: '.o_field_widget[name=partner_id] input',
                run: 'click',
            },
            ...stepUtils.mobileKanbanSearchMany2X('Customer', 'Test Partner'),
            {
                content: "Wait for partner to be selected",
                trigger: '.o_field_widget[name="partner_id"] .o_external_button',
            },
            {
                content: "Open the add product dialog",
                trigger: '.o_field_widget[name="order_line"] .o_x2m_control_panel button:first-child',
                run: 'click',
            },
            {
                content: "Click on product field to open search dialog",
                trigger: '.modal:not(.o_inactive_modal) [name="product_id"] input, .modal:not(.o_inactive_modal) [name="product_template_id"] input',
                run: 'click',
            },
            ...stepUtils.mobileKanbanSearchMany2X('Product', 'Combo product'),
            comboConfiguratorTourUtils.selectComboItem("Test product"),
            productConfiguratorTourUtils.selectAttribute(
                "Test product", "Attribute B", "B", 'multi'
            ),
            ...productConfiguratorTourUtils.saveConfigurator(),
            ...comboConfiguratorTourUtils.saveConfigurator(),
            {
                content: "Save the order line",
                trigger: '.modal:not(.o_inactive_modal) .o_form_button_save',
                run: 'click',
            },
            {
                content: "Wait for the dialog to close",
                trigger: 'body:not(:has(.modal))',
            },
            {
                content: "Assert combo product line has non-zero price",
                trigger: '.o_field_widget[name="order_line"] .o_kanban_record .o_field_monetary:not(:contains("0.00"))',
            },
            ...stepUtils.saveForm(),
        ],
    });
