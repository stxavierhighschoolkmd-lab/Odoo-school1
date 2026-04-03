from ast import literal_eval

from odoo import api, fields, models


class MailingMailing(models.Model):
    _inherit = 'mailing.mailing'

    mailing_domain = fields.Char(compute='_compute_mailing_domain', readonly=False, store=True)

    @api.depends('card_campaign_id', 'mailing_model_id')
    def _compute_mailing_domain(self):
        super()._compute_mailing_domain()
        # if we have a default domain specifying some event_id condition
        # assume the user specifically selected that one in advance
        if default_domain_str := self.env.context.get('default_mailing_domain'):
            try:
                default_domain = fields.Domain(literal_eval(default_domain_str))
            except (SyntaxError, TypeError, ValueError):
                default_domain = fields.Domain.TRUE
            if any(condition.field_expr == 'event_id' for condition in default_domain.iter_conditions()):
                return

        # we consider if the card campaign is based on an (allowed) model, from the event module, that has an "event_id" field
        # it's always relevant to limit the domain to the related event
        for mailing in self.filtered(lambda m: (
            m.card_campaign_id
            and m.card_campaign_id.res_model.startswith('event.')
            and m.card_campaign_id.res_model in m.card_campaign_id._get_allowed_event_model_names()
        )):
            try:
                mailing_domain = fields.Domain(literal_eval(mailing.mailing_domain))
            except (SyntaxError, TypeError, ValueError):
                mailing_domain = fields.Domain.TRUE
            TargetModel = self.env[mailing.card_campaign_id.res_model]
            if (event_record := mailing.card_campaign_id.preview_record_ref) and 'event_id' in event_record:
                # we can assume if there is any condition on 'event_id' that is not '=' or 'in'
                # the user knows what they are doing
                if not any(condition.field_expr == 'event_id' for condition in mailing_domain.iter_conditions()):
                    final_domain = fields.Domain('event_id', '=', event_record.event_id.id) & mailing_domain
                else:
                    final_domain = mailing_domain.optimize(TargetModel).map_domain(
                        lambda condition: (
                            fields.Domain('event_id', '=', event_record.event_id)
                            if condition.field_expr == 'event_id' and condition.operator == 'in'
                            else condition
                        )
                    ).optimize(TargetModel)
            mailing.mailing_domain = repr(final_domain)
