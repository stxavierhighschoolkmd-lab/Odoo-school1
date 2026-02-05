from odoo import http

from odoo.addons.website.controllers.main import Website


class ForumWebsite(Website):

    @http.route()
    def track(self, res_model, res_id, url, **kwargs):
        # EXTENDS website
        res = super().track(res_model, res_id, url, **kwargs)
        if res_model == 'forum.post':
            # increment view counter
            question = self.env['forum.post'].browse(res_id)
            question.sudo()._set_viewed()
        return res
