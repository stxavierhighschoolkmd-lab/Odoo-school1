# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request
from odoo.addons.mail.controllers.discuss.channel import DiscussChannelWebclientController
from odoo.addons.mail.tools.discuss import Store


class CalendarDiscussChannelWebclientController(DiscussChannelWebclientController):
    @classmethod
    def _process_request_for_all(cls, store: Store, name, params):
        super()._process_request_for_all(store, name, params)
        if name == "/discuss/channel/messages":
            channel_id = params.get("channel_id")
            if channel_id:
                channel = request.env["discuss.channel"].browse(channel_id)
                if channel and channel.channel_type == "chat":
                    chat_partner = channel.mapped("channel_member_ids").filtered(lambda m: not m.is_self).mapped("partner_id")
                    statuses = request.env["res.users"]._get_user_meeting_statuses(partner_id=chat_partner.ids)
                    store.add_global_values(userMeetingStatuses=statuses)
