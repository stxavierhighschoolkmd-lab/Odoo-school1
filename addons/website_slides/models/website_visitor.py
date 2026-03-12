from odoo import fields, models


class WebsiteVisitor(models.Model):
    _inherit = 'website.visitor'

    visitor_slide_count = fields.Integer(
        string="Slide Views",
        compute='_compute_slide_statistics',
    )
    slide_channel_ids = fields.Many2many(
        comodel_name='slide.channel',
        string="Slides",
        compute='_compute_slide_statistics',
    )

    def _compute_slide_statistics(self):
        self._aggregate_visitor_tracks(field_name='slide_channel_ids', model_name='slide.channel', count_field='visitor_slide_count')

    def _add_viewed_slide(self, slide_channel_id):
        """ add a website_track with a page marked as viewed"""
        self.ensure_one()
        if slide_channel_id:
            domain = [('res_model', '=', 'slide.channel'), ('res_id', '=', slide_channel_id)]
            website_track_values = {
                'res_model': 'slide.channel',
                'res_id': slide_channel_id,
            }
            self._add_tracking(domain, website_track_values)
