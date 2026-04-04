# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, _
from odoo.exceptions import UserError


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    @api.model
    def _update_foreign_keys(self, src_partners, dst_partner):
        # prevent merging partners enrolled in common courses
        (src_partners | dst_partner).invalidate_recordset(fnames=['slide_channel_ids'])
        courses_set = set(dst_partner.sudo().slide_channel_ids.ids)
        duplicate_courses = self.env['slide.channel']
        for partner in src_partners:
            for slide_channel in partner.sudo().slide_channel_ids:
                if slide_channel.id in courses_set:
                    duplicate_courses |= slide_channel
                else:
                    courses_set.add(slide_channel.id)
        if duplicate_courses:
            raise UserError(_(
                "You cannot merge these contacts because they are enrolled in the following common courses: %s",
                ', '.join(duplicate_courses.mapped('name'))))
        super()._update_foreign_keys(src_partners, dst_partner)
