# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mass_mailing.tests.common import MassMailCommon
from odoo.tests.common import tagged


@tagged('mailing_templates')
@tagged('at_install', '-post_install')
class TestMailingTemplates(MassMailCommon):

    def test_template_duplicate(self):
        # Prepare
        mailing_template = self.env['mailing.mailing'].create([
            {
                "subject": "First template",
                "is_template": True,
            },
        ])

        # Execute
        res_action = mailing_template.action_duplicate_template()
        duplicated_template_id = res_action['res_id']
        rendered_remplate_form_view = self.env.ref('mass_mailing.mailing_templates_view_form', raise_if_not_found=False)

        # Assert
        self.assertNotEqual(duplicated_template_id, mailing_template.id)
        self.assertEqual(rendered_remplate_form_view, self.env['ir.ui.view'].browse(res_action['views'][0][0]))
        self.assertEqual(True, self.env['mailing.mailing'].search([('id', '=', duplicated_template_id)]).favorite)
        self.assertEqual(True, self.env['mailing.mailing'].search([('id', '=', duplicated_template_id)]).is_template)
