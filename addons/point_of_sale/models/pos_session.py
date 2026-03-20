# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_is_zero, plaintext2html

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _name = 'pos.session'
    _order = 'id desc'
    _description = 'Point of Sale Session'
    _inherit = ['mail.thread', 'mail.activity.mixin', "pos.bus.mixin", 'pos.load.mixin']

    POS_SESSION_STATE = [
        ('opening_control', 'Opening Control'),
        ('opened', 'In Progress'),
        ('closing_control', 'Closing Control'),
        ('closed', 'Closed & Posted'),
    ]

    company_id = fields.Many2one('res.company', related='config_id.company_id', string="Company", readonly=True)

    config_id = fields.Many2one(
        'pos.config', string='Point of Sale',
        required=True,
        index=True)
    name = fields.Char(string='Session ID', readonly=True, default='/')
    user_id = fields.Many2one(
        'res.users', string='Opened By',
        required=True,
        index=True,
        readonly=False,
        default=lambda self: self.env.uid,
        ondelete='restrict')
    currency_id = fields.Many2one('res.currency', related='config_id.currency_id', string="Currency", readonly=False)
    start_at = fields.Datetime(string='Opening Date', readonly=True)
    stop_at = fields.Datetime(string='Closing Date', readonly=True, copy=False)

    state = fields.Selection(
        POS_SESSION_STATE, string='Status',
        required=True, readonly=True,
        index=True, copy=False, default='opening_control')

    opening_notes = fields.Text(string="Opening Notes")
    closing_notes = fields.Text(string="Closing Notes")

    # Cash control fields
    cash_control = fields.Boolean(
        related='config_id.cash_control',
        string='Cash Control',
        readonly=True,
        store=True)  # Need to be stored in case of change of config
    cash_register_balance_start = fields.Monetary(
        string="Starting Balance",
        readonly=True)
    cash_register_balance_end = fields.Monetary(
        string="Theoretical Closing Balance",
        help="Opening balance summed to all cash transactions.",
        readonly=True)
    cash_register_difference = fields.Monetary(
        string='Before Closing Difference',
        help="Difference between the theoretical closing balance and the real closing balance.",
        readonly=True)

    # Total Cash In/Out
    order_ids = fields.One2many('pos.order', 'session_id', string='Orders')
    order_count = fields.Integer(compute='_compute_order_count')
    statement_line_ids = fields.One2many('account.bank.statement.line', 'pos_session_id', string='Cash Lines', readonly=True)
    failed_pickings = fields.Boolean(compute='_compute_picking_count')
    picking_count = fields.Integer(compute='_compute_picking_count')
    picking_ids = fields.One2many('stock.picking', 'pos_session_id')
    rescue = fields.Boolean(string='Recovery Session',
        help="Auto-generated session for orphan orders, ignored in constraints",
        readonly=True,
        copy=False)
    sales_move_id = fields.Many2one('account.move', string='Sales Journal', index=True)
    refunds_move_id = fields.Many2one('account.move', string='Refunds Journal', index=True)
    move_ids = fields.Many2many(
        'account.move',
        string='Related Journal Entries',
        compute='_compute_move_ids',
        search='_search_move_ids')
    payment_method_ids = fields.Many2many('pos.payment.method', related='config_id.payment_method_ids', string='Payment Methods')
    total_payments_amount = fields.Float(compute='_compute_total_payments_amount', string='Total Payments Amount')
    is_in_company_currency = fields.Boolean('Is Using Company Currency', compute='_compute_is_in_company_currency')
    update_stock_at_closing = fields.Boolean('Stock should be updated at closing')
    bank_payment_ids = fields.One2many('account.payment', 'pos_session_id', 'Bank Payments', help='Account payments representing aggregated and bank split payments.')

    def write(self, vals):
        if vals.get('state') == 'closed':
            for record in self:
                record.config_id._notify(('CLOSING_SESSION', {
                    'device_identifier': self.env.context.get('device_identifier', False),
                    'session_id': record.id,
                }))
        return super().write(vals)

    @api.model
    def _load_pos_data_relations(self, model, fields):
        model_fields = self.env[model]._fields
        relations = {}

        for name, params in model_fields.items():
            if (name not in fields and len(fields)) or (params.manual and not len(fields)):
                continue

            if params.comodel_name:
                relations[name] = {
                    'name': name,
                    'model': params.model_name,
                    'compute': bool(params.compute),
                    'related': bool(params.related),
                    'relation': params.comodel_name,
                    'type': params.type,
                }
                if params.type == 'many2one' and params.ondelete:
                    relations[name]['ondelete'] = params.ondelete
                if params.type == 'one2many' and params.inverse_name:
                    relations[name]['inverse_name'] = params.inverse_name
                if params.type == 'many2many':
                    relations[name]['relation_table'] = self.env[model]._fields[name].relation
            else:
                relations[name] = {
                    'name': name,
                    'type': params.type,
                    'compute': bool(params.compute),
                    'related': bool(params.related),
                }

        return relations

    @api.model
    def _load_pos_data_models(self, config):
        return ['pos.config', 'pos.preset', 'resource.calendar.attendance', 'pos.order', 'pos.order.line', 'pos.pack.operation.lot', 'pos.payment', 'pos.payment.method', 'pos.printer',
            'pos.category', 'pos.bill', 'res.company', 'account.tax', 'account.tax.group', 'product.template', 'product.product', 'product.attribute', 'product.attribute.custom.value',
            'product.template.attribute.line', 'product.template.attribute.value', 'product.combo', 'product.combo.item', 'res.users', 'res.partner', 'product.uom',
            'decimal.precision', 'uom.uom', 'res.country', 'res.country.state', 'res.lang', 'product.category', 'product.pricelist', 'product.pricelist.item',
            'account.cash.rounding', 'account.fiscal.position', 'stock.picking.type', 'res.currency', 'pos.note', 'product.tag', 'ir.module.module', 'account.move', 'account.account', 'pos.product.template.snooze']

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [('id', '=', self.id)]

    @api.model
    def _load_pos_data_fields(self, config):
        return [
            'id', 'name', 'user_id', 'config_id', 'start_at', 'stop_at', 'cash_register_balance_start',
            'payment_method_ids', 'state', 'update_stock_at_closing', 'access_token',
        ]

    def load_data(self, models_to_load):
        response = {}
        response['pos.session'] = self._load_pos_data_search_read(response, self.config_id)

        for model in self._load_pos_data_models(self.config_id):
            if models_to_load and model not in models_to_load:
                continue

            try:
                response[model] = self.env[model]._load_pos_data_search_read(response, self.config_id)
            except AccessError as e:
                response[model] = []
                _logger.info("Could not load model %s due to AccessError: %s", model, e)

        return response

    def load_data_params(self):
        response = {}
        fields = self._load_pos_data_fields(self.config_id)
        response['pos.session'] = {
            'fields': fields,
            'relations': self._load_pos_data_relations('pos.session', fields),
        }

        for model in self._load_pos_data_models(self.config_id):
            fields = self.env[model]._load_pos_data_fields(self.config_id)
            response[model] = {
                'fields': fields,
                'relations': self._load_pos_data_relations(model, fields),
            }

        return response

    def filter_local_data(self, models_to_filter):
        response = {}
        for model, ids in models_to_filter.items():
            existing_records = self.env[model].browse(ids).exists()

            non_existent_ids = set(ids) - set(existing_records.ids)
            inactive_ids = set(existing_records._unrelevant_records(self.config_id))

            response[model] = list(non_existent_ids | inactive_ids)
        return response

    def delete_opening_control_session(self):
        self.ensure_one()
        if not self.exists():
            return {
                'status': 'success',
            }
        if self.state != 'opening_control' or len(self.order_ids) > 0:
            raise UserError(_("You can only cancel a session that is in opening control state and has no orders."))
        self.sudo().unlink()
        return {
            'status': 'success',
        }

    def get_pos_ui_product_pricelist_item_by_product(self, product_tmpl_ids, product_ids, config_id):
        pos_config = self.env['pos.config'].browse(config_id)
        pricelist_fields = self.env['product.pricelist']._load_pos_data_fields(pos_config)
        pricelist_item_fields = self.env['product.pricelist.item']._load_pos_data_fields(pos_config)
        today = fields.Date.today()
        pricelist_item_domain = [
            '&',
            ('pricelist_id', 'in', self.config_id._get_available_pricelists().ids),
            *self.env['product.pricelist.item']._check_company_domain(self.company_id),
            '|',
            '&', ('product_id', '=', False), ('product_tmpl_id', 'in', product_tmpl_ids),
            ('product_id', 'in', product_ids),
            '|', ('date_start', '=', False), ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today)]

        pricelist_item = self.env['product.pricelist.item'].search(pricelist_item_domain)
        pricelist = pricelist_item.pricelist_id

        return {
            'product.pricelist.item': pricelist_item.read(pricelist_item_fields, load=False),
            'product.pricelist': pricelist.read(pricelist_fields, load=False),
        }

    @api.depends('currency_id', 'company_id.currency_id')
    def _compute_is_in_company_currency(self):
        for session in self:
            session.is_in_company_currency = session.currency_id == session.company_id.currency_id

    @api.depends('order_ids.payment_ids.amount')
    def _compute_total_payments_amount(self):
        result = self.env['pos.payment']._read_group(self._get_captured_payments_domain(), ['session_id'], ['amount:sum'])
        session_amount_map = {session.id: amount for session, amount in result}
        for session in self:
            session.total_payments_amount = session_amount_map.get(session.id) or 0

    def _search_move_ids(self, operator, value):
        moves = self.env['account.move'].search([('id', operator, value)])
        return [
            '|',
            ('sales_move_id', 'in', moves.ids),
            ('refunds_move_id', 'in', moves.ids),
        ]

    @api.depends('sales_move_id', 'refunds_move_id')
    def _compute_move_ids(self):
        for session in self:
            session.move_ids = session.sales_move_id | session.refunds_move_id

    def _compute_order_count(self):
        orders_data = self.env['pos.order']._read_group([('session_id', 'in', self.ids)], ['session_id'], ['__count'])
        sessions_data = {session.id: count for session, count in orders_data}
        for session in self:
            session.order_count = sessions_data.get(session.id, 0)

    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_picking_count(self):
        for session in self:
            session.picking_count = self.env['stock.picking'].search_count([('pos_session_id', 'in', session.ids)])
            session.failed_pickings = bool(self.env['stock.picking'].search([('pos_session_id', 'in', session.ids), ('state', '!=', 'done')], limit=1))

    def action_stock_picking(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_ready')
        action['display_name'] = _('Pickings')
        action['context'] = {}
        action['domain'] = [('id', 'in', self.picking_ids.ids)]
        return action

    @api.constrains('config_id')
    def _check_pos_config(self):
        onboarding_creation = self.env.context.get('onboarding_creation', False)
        if not onboarding_creation and self.search_count([
                ('state', '!=', 'closed'),
                ('config_id', '=', self.config_id.id),
                ('rescue', '=', False),
            ]) > 1:
            raise ValidationError(_("Another session is already opened for this point of sale."))

    @api.constrains('start_at')
    def _check_start_date(self):
        for record in self:
            journal = record.config_id.journal_id
            company = journal.company_id
            start_date = record.start_at.date()
            violated_lock_dates = company._get_violated_lock_dates(start_date, True, journal)
            if violated_lock_dates:
                raise ValidationError(_("You cannot create a session starting before: %(lock_date_info)s",
                                        lock_date_info=self.env['res.company']._format_lock_dates(violated_lock_dates)))

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        for session in sessions:
            closing = session.config_id.company_id.point_of_sale_update_stock_quantities == "closing"
            cash_pm = session._get_cash_payment_method()
            starting_amount = cash_pm.account_bank_statement_id.balance_end_real if cash_pm else 0
            session.write({
                'update_stock_at_closing': closing,
                'cash_register_balance_start': starting_amount,
            })
        return sessions

    def get_session_orders(self):
        return self.order_ids.filtered(lambda o:
            not (o.preset_time and o.preset_time.date() > fields.Date.today()),
        )

    def _close_session_action(self, amount_to_balance):
        default_account = self._get_balancing_account()
        wizard = self.env['pos.close.session.wizard'].create({
            'amount_to_balance': amount_to_balance,
            'account_id': default_account.id,
            'account_readonly': not self.env.user.has_group('account.group_account_readonly'),
            'message': _("There is a difference between the amounts to post and the amounts of the orders, it is probably caused by taxes or accounting configurations changes."),
        })
        return {
            'name': _("Force Close Session"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'pos.close.session.wizard',
            'res_id': wizard.id,
            'target': 'new',
            'context': {**self.env.context, 'active_ids': self.ids, 'active_model': 'pos.session'},
        }

    def action_pos_session_closing_control(self):
        """
        This method is called in pos.session form view by clicking on
        close session button, this happen when an error occurs during
        the closing of the session from the UI.

        DO NOT CALL THIS METHOD FROM THE UI !
        """
        self.ensure_one()
        result = self.close_session_from_ui()
        if not result['status'] and result['type'] == 'accounting_error':
            return self._close_session_action(result['data']['amount_residual'])
        return True

    def close_session_from_ui(self, counted_cash=0):
        """
        Main entry point for closing a session from the UI. It will
        perform all necessary checks and operations to close the session
        """
        self.ensure_one()
        if any(order.state == 'draft' for order in self.get_session_orders()):
            return {
                'status': False,
                'type': 'draft_orders',
                'message': _("You cannot close the POS while there are still draft orders for the day."),
                'redirect': False,
            }

        if self.state == 'closed':
            return {
                'status': False,
                'type': 'session_already_closed',
                'message': _("This session is already closed."),
                'redirect': True,
            }

        self.config_id.close_session_snoozes()
        future_orders = self.order_ids.filtered_domain([
            ('preset_time', '!=', False),
            ('preset_time', '>', fields.Datetime.now()),
            ('state', '=', 'draft'),
        ])
        future_orders.session_id = False
        self.write({
            'state': 'closing_control',
            'stop_at': fields.Datetime.now(),
        })
        amount_residual = self._validate_session_accounting(counted_cash)
        if not float_is_zero(amount_residual, precision_rounding=self.currency_id.rounding):
            self.state = 'closing_control'
            formatted = self.currency_id.format(amount_residual)
            return {
                'status': False,
                'type': 'accounting_error',
                'redirect': True,
                'data': {
                    'amount_residual': amount_residual,
                },
                'message': _(
                    "The session cannot be closed due to an accounting"
                    " difference of %s. Please review the journal entries"
                    " and try again.", formatted),
            }

        if self.update_stock_at_closing:
            self._create_picking_at_end_of_session()
            order_to_compute = self._get_closed_orders().filtered(
                lambda o: not o.is_total_cost_computed,
            )
            order_to_compute._compute_total_cost_at_session_closing(
                self.picking_ids.move_ids,
            )

        if self.config_id.order_edit_tracking:
            edited_orders = self.get_session_orders().filtered(lambda o: o.is_edited)
            if len(edited_orders) > 0:
                order_links = Markup().join(
                    Markup("<li>%s</li>") % order._get_html_link() for order in edited_orders
                )
                body = _(
                    "Edited order(s) during the session:%s",
                    Markup("<br/><ul>%s</ul>") % order_links,
                )
                self.message_post(body=body)

        # Make sure to trigger reordering rules
        self.picking_ids.move_ids.sudo()._trigger_scheduler()
        self.write({'state': 'closed'})
        self.env.flush_all()  # ensure sale.report is up to date

        if self.env.user.email:
            self.post_close_register_message()

        return {'status': True}

    def post_close_register_message(self):
        self.message_post(body=_('Closed Register'))

    def _get_diff_account_move_ref(self, payment_method):
        return _('Closing difference in %(payment_method)s (%(session)s)', payment_method=payment_method.name, session=self.name)

    def get_cash_in_out_list(self):
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("You don't have the access rights to get the cash in/out list."))
        cash_in_count = 0
        cash_out_count = 0
        cash_in_out_list = []
        for cash_move in self.sudo().statement_line_ids.sorted('create_date'):
            if cash_move.amount > 0:
                cash_in_count += 1
                name = f'Cash in {cash_in_count}'
            else:
                cash_out_count += 1
                name = f'Cash out {cash_out_count}'
            cash_in_out_list.append({
                'name': cash_move.payment_ref or name,
                'amount': cash_move.amount,
                'id': cash_move.id,
                'date': cash_move.create_date,
                'cashier_name': cash_move.partner_id.name,
            })
        return cash_in_out_list

    def get_closing_control_data(self):
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("You don't have the access rights to get the point of sale closing control data."))
        self.ensure_one()
        orders = self._get_closed_orders()
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")
        cash_payment_method_ids = self._get_cash_payment_method()
        default_cash_payment_method_id = cash_payment_method_ids[0] if cash_payment_method_ids else None
        default_cash_payments = payments.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id) if default_cash_payment_method_id else []
        total_default_cash_payment_amount = sum(default_cash_payments.mapped('amount')) if default_cash_payment_method_id else 0
        non_cash_payment_method_ids = self.payment_method_ids - default_cash_payment_method_id if default_cash_payment_method_id else self.payment_method_ids
        non_cash_payments_grouped_by_method_id = {pm: orders.payment_ids.filtered(lambda p: p.payment_method_id == pm) for pm in non_cash_payment_method_ids}
        ending_cash_balance = default_cash_payment_method_id.account_bank_statement_id.balance_end if default_cash_payment_method_id else 0
        cash_in_out_list = self.get_cash_in_out_list()

        return {
            'orders_details': {
                'quantity': len(orders),
                'amount': sum(orders.mapped('amount_total')),
            },
            'opening_notes': self.opening_notes,
            'default_cash_details': {
                'name': default_cash_payment_method_id.name,
                'amount': ending_cash_balance + total_default_cash_payment_amount,
                'opening': self.cash_register_balance_start,
                'payment_amount': total_default_cash_payment_amount,
                'moves': cash_in_out_list,
                'id': default_cash_payment_method_id.id,
            } if default_cash_payment_method_id else {},
            'non_cash_payment_methods': [{
                'name': pm.name,
                'amount': sum(non_cash_payments_grouped_by_method_id[pm].mapped('amount')),
                'number': len(non_cash_payments_grouped_by_method_id[pm]),
                'id': pm.id,
                'type': pm.type,
            } for pm in non_cash_payment_method_ids],
            'is_manager': self.env.user.has_group("point_of_sale.group_pos_manager"),
            'amount_authorized_diff': self.config_id.amount_authorized_diff if self.config_id.set_maximum_difference else None,
        }

    def _create_picking_at_end_of_session(self):
        self.ensure_one()
        lines_grouped_by_dest_location = {}
        picking_type = self.config_id.picking_type_id

        if not picking_type or not picking_type.default_location_dest_id:
            session_destination_id = self.env['stock.warehouse']._get_partner_locations()[0].id
        else:
            session_destination_id = picking_type.default_location_dest_id.id

        for order in self._get_closed_orders():
            if order._force_create_picking_real_time() or order.shipping_date:
                continue
            destination_id = order.partner_id.property_stock_customer.id or session_destination_id
            if destination_id in lines_grouped_by_dest_location:
                lines_grouped_by_dest_location[destination_id] |= order.lines
            else:
                lines_grouped_by_dest_location[destination_id] = order.lines

        for location_dest_id, lines in lines_grouped_by_dest_location.items():
            pickings = self.env['stock.picking']._create_picking_from_pos_order_lines(location_dest_id, lines, picking_type)
            pickings.write({'pos_session_id': self.id, 'origin': self.name})

    def _get_balancing_account(self):
        return self.config_id.default_partner_id.property_account_receivable_id

    def _amount_converter(self, amount, date, round):
        # self should be single record as this method is only called in the subfunctions of self._validate_session
        return self.currency_id._convert(amount, self.company_id.currency_id, self.company_id, date, round=round)

    def show_journal_items(self):
        self.ensure_one()
        all_related_moves = self._get_related_account_moves()
        return {
            'name': _('Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list',
            'view_id': self.env.ref('account.view_move_line_tree').id,
            'domain': [('id', 'in', all_related_moves.mapped('line_ids').ids)],
            'context': {
                'journal_type': 'general',
                'search_default_group_by_sales_move': 1,
                'group_by': 'sales_move_id', 'search_default_posted': 1,
            },
        }

    def _get_other_related_moves(self):
        # TODO This is not an ideal way to get the diff account.move's for
        # the session. It would be better if there is a relation field where
        # these moves are saved.

        # Unfortunately, the 'ref' of account.move is not indexed, so
        # we are querying over the account.move.line because its 'ref' is indexed.
        # And yes, we are only concern for split bank payment methods.
        diff_lines_ref = [self._get_diff_account_move_ref(pm) for pm in self.payment_method_ids if pm.type == 'bank' and pm.split_transactions]
        cost_move_lines = ['pos_order_' + str(rec.id) for rec in self._get_closed_orders()]
        sales_move = self.env['account.move.line'].search([('ref', 'in', diff_lines_ref + cost_move_lines)]).mapped('sales_move_id')
        refunds_move = self.env['account.move.line'].search([('ref', 'in', diff_lines_ref + cost_move_lines)]).mapped('refunds_move_id')
        return sales_move | refunds_move

    def _get_related_account_moves(self):
        pickings = self.picking_ids | self._get_closed_orders().mapped('picking_ids')
        invoices = self.mapped('order_ids.account_move')
        invoice_payments = self.mapped('order_ids.payment_ids.account_move_id')
        stock_account_moves = pickings.move_ids.account_move_id
        cash_moves = self.statement_line_ids.mapped('move_id')
        bank_payment_moves = self.bank_payment_ids.mapped('move_id')
        reversal_moves = self.mapped('order_ids.reversed_move_ids')
        other_related_moves = self._get_other_related_moves()
        return invoices | invoice_payments | self.sales_move_id | self.refunds_move_id | stock_account_moves | cash_moves | bank_payment_moves | reversal_moves | other_related_moves

    def action_show_payments_list(self):
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.payment',
            'view_mode': 'list,form',
            'domain': self._get_captured_payments_domain(),
            'context': {'search_default_group_by_payment_method': 1},
        }

    def _get_captured_payments_domain(self):
        return [('session_id', 'in', self.ids), ('pos_order_id.state', 'in', ['paid', 'invoiced', 'done'])]

    def open_frontend_cb(self):
        """Open the pos interface with config_id as an extra argument.

        In vanilla PoS each user can only have one active session, therefore it was not needed to pass the config_id
        on opening a session. It is also possible to login to sessions created by other users.

        :returns: dict
        """
        if not self.ids:
            return {}
        return self.config_id.open_ui()

    def _set_opening_control_data(self, cashbox_value: int, notes: str):
        """
        Internal logic for opening the session.
        Inherit this method to add custom logic before the sequence is assigned.
        """
        self.state = 'opened'
        self.start_at = fields.Datetime.now()
        self._handle_starting_cash_balance(cashbox_value)

        if notes:
            self.opening_notes = notes
        elif notes:
            message = _('Opening control message: ')
            message += notes
            self.message_post(body=plaintext2html(message))

    def set_opening_control(self, cashbox_value: int, notes: str):
        """
        Public method to open the session.
        This calls the internal logic and, if successful, assigns the sequence name.

        DO NOT INHERIT THIS METHOD. Inherit _set_opening_control_data instead.
        """
        if self.state != 'opening_control':
            return

        sequence = self.env['ir.sequence'].with_context(
            company_id=self.config_id.company_id.id,
        ).search([('code', '=', 'pos.session'), ('company_id', 'in', [self.config_id.company_id.id, False])], order='company_id', limit=1)

        self.name = (self.config_id.name if sequence.prefix == '/' else '') + sequence.next_by_code('pos.session') + (self.name if self.name != '/' else '')
        self._set_opening_control_data(cashbox_value, notes)

    def action_view_order(self):
        return {
            'name': _('Orders'),
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('point_of_sale.view_pos_order_tree_no_session_id').id, 'list'),
                (self.env.ref('point_of_sale.view_pos_pos_form').id, 'form'),
                ],
            'type': 'ir.actions.act_window',
            'domain': [('session_id', 'in', self.ids)],
        }

    @api.model
    def _alert_old_session(self):
        # If the session is open for more then one week,
        # log a next activity to close the session.
        sessions = self.sudo().search([('start_at', '<=', (fields.Datetime.now() - timedelta(days=7))), ('state', '!=', 'closed')])
        for session in sessions:
            if self.env['mail.activity'].search_count([('res_id', '=', session.id), ('res_model', '=', 'pos.session')]) == 0:
                session.activity_schedule(
                    'point_of_sale.mail_activity_old_session',
                    user_id=session.user_id.id,
                    note=_(
                        "Your PoS Session is open since %(date)s, we advise you to close it and to create a new one.",
                        date=session.start_at,
                    ),
                )

    def _check_if_no_draft_orders(self):
        draft_orders = self.get_session_orders().filtered(lambda order: order.state == 'draft')
        if draft_orders:
            raise UserError(_(
                    'There are still orders in draft state in the session. '
                    'Pay or cancel the following orders to validate the session:\n%s',
                    ', '.join(draft_orders.mapped('name')),
            ))
        return True

    def try_cash_in_out(self, _type, amount, reason, partner_id):
        sign = 1 if _type == 'in' else -1
        cash_pm = self._get_cash_payment_method()
        if not cash_pm:
            raise UserError(_("There is no cash payment method for this PoS Session"))

        message = _('Cash move: "%s" from %s', reason, self.name)
        signed_amount = amount * sign
        partner = self.env['res.partner'].browse(partner_id)
        cash_pm._create_cash_payment_line(self, signed_amount, partner, message)

    def delete_cash_in_out(self, absl_id, partner_id):
        if not self.env.user.has_group('account.group_account_basic'):
            raise AccessError(_("You don't have the access rights to delete a cash in/out."))
        absl = self.env['account.bank.statement.line'].browse(absl_id)
        if absl not in self.statement_line_ids:
            raise AccessError(_("You cannot delete a cash move that is not linked to this session."))
        cashier_name = absl.partner_id.name
        amount = absl.amount
        action = cashier_name + ': ' + str(amount)
        absl.unlink()
        self.log_partner_message(partner_id, action, "CASH_IN_OUT_UNLINK")

    def _get_invoice_total_list(self):
        invoice_list = []
        for order in self.order_ids.filtered(lambda o: o.is_invoiced):
            invoice = {
                'total': order.account_move.amount_total_signed,
                'name': order.account_move.name,
                'order_ref': order.pos_reference,
            }
            invoice_list.append(invoice)

        return invoice_list

    def _get_total_invoice(self):
        amount = 0
        for order in self.order_ids.filtered(lambda o: o.is_invoiced):
            amount += order.amount_paid

        return amount

    def log_partner_message(self, partner_id, action, message_type):
        if message_type == 'ACTION_CANCELLED':
            body = _('Action cancelled (%(ACTION)s)', ACTION=action)
        elif message_type == 'CASH_DRAWER_ACTION':
            body = _('Cash drawer opened (%(ACTION)s)', ACTION=action)
        elif message_type == 'CASH_IN_OUT_UNLINK':
            body = _('Cash move deleted: %s', action)

        self.message_post(body=body, author_id=partner_id)

    def _get_closed_orders(self):
        return self.order_ids.filtered(lambda o: o.state not in ['draft', 'cancel'])

    ##############################################################
    #                 Accounting related methods                 #
    ##############################################################
    def _get_cash_payment_method(self):
        self.ensure_one()
        return self.config_id.payment_method_ids.filtered(
            lambda pm: pm.type == 'cash',
        )

    def _handle_starting_cash_balance(self, cashbox_value=0):
        self.ensure_one()
        if cash_pm := self._get_cash_payment_method():
            current_balance = cash_pm.account_bank_statement_id.balance_end_real or 0
            correction = cashbox_value - current_balance
            is_zero = float_is_zero(correction, precision_rounding=self.currency_id.rounding)
            if not is_zero:
                message = _('Opening cash correction in %s', self.name)
                partner = self.env.user.partner_id
                cash_pm._create_cash_payment_line(self, correction, partner, message)

    def _handle_ending_cash_balance(self, cashbox_value=0):
        self.ensure_one()
        cash_pm = self._get_cash_payment_method()
        if cash_pm:
            balance_end = cash_pm.account_bank_statement_id.balance_end or 0
            difference = cashbox_value - balance_end
            if not float_is_zero(difference, precision_rounding=self.currency_id.rounding):
                reason = _('Cash closing difference of %s in %s', self.currency_id.format(difference), self.name)
                partner = self.env.user.partner_id
                cash_pm._create_cash_payment_line(self, difference, partner, reason)
            cash_pm.account_bank_statement_id._compute_balance_end_real()

    def _get_receivable_account(self):
        """
        PoS session receivable account is now accessed through the linked
        default partner of the linked config.
        """
        self.ensure_one()
        return self.config_id.default_partner_id.property_account_receivable_id

    def _validate_session_accounting(self, counted_cash=0):
        """
        This method is the ONLY entry point for the session closing
        process, and should contain all the necessary logic to create
        the accounting entries of the session closing.
        """
        self.ensure_one()

        # Get all paid and invoiced orders of the session
        non_invoiced_orders, invoiced_orders = self._get_invoiced_and_non_invoiced_orders()
        self._check_invoiced_orders_are_posted(invoiced_orders)

        # Build the out_receipt lines. Returns pm_data_list so we can
        # create the matching account.payment / statement line records after posting.
        sale_orders = non_invoiced_orders.filtered(lambda order: not order.is_refund)
        refund_orders = non_invoiced_orders - sale_orders
        sales_move = self._create_session_account_move(sale_orders)
        refunds_move = self._create_session_account_move(refund_orders, True)

        # Ensure tracking of pos orders in the account moves
        sale_orders.account_move = sales_move
        refund_orders.account_move = refunds_move

        self.sales_move_id = sales_move
        self.refunds_move_id = refunds_move
        cash_pm = self._get_cash_payment_method()
        if cash_pm:
            self._handle_ending_cash_balance(counted_cash)
            self.cash_register_balance_end = cash_pm.account_bank_statement_id.balance_end_real

        return abs(sales_move.amount_residual) + abs(refunds_move.amount_residual)

    def _create_session_account_move(self, orders, refund=False):
        """
        This method creates the receipt of the session closing, with all
        the details of the session accounting. This will only take into
        account the orders that were paid but not invoiced, as the ones
        that were invoiced already have their details in the invoice.

        We'll create following account.move.line:
        - One line per (revenue account + VAT rate) group with net amount + tax_ids
        - One tax line per (tax account + tax) combination
        - One line per payment method with the total amount
          (display_type='payment_term' on the POS receivable account,
          so it can be reconciled with account.payment)

        After posting, one account.payment is created per payment method
        and reconciled against the matching payment_term line, marking
        the receipt as fully paid via standard Odoo reconciliation.

        Returns the pm_data_list (list of dicts) for payment creation
        in _validate_session_accounting.
        """
        if not orders:
            return self.env['account.move']

        AccountJournal = self.env['account.journal']
        journal = AccountJournal._ensure_company_account_journal()
        if self.config_id.journal_id != journal:
            self.config_id.journal_id = journal

        move_type = 'out_refund' if refund else 'out_invoice'
        move = self.env['account.move'].create({
            'move_type': move_type,
            'journal_id': self.config_id.journal_id.id,
            'date': fields.Date.context_today(self),
            'ref': self.name,
            'partner_id': self.config_id.default_partner_id.id,
        })

        payment_methods = orders.payment_ids.payment_method_id
        cash_payment_method = payment_methods.filtered(
            lambda pm: pm.type == 'cash',
        )

        if len(cash_payment_method) > 1:
            raise UserError(_(
                "Only one cash payment method can be used in a session.",
            ))

        # product_commands => invoice_line_ids (display_type=product, net price_unit)
        sales, refunds = orders._prepare_account_move_line_data()
        sales_commands = [Command.create(line) for line in sales]
        refunds_commands = [Command.create(line) for line in refunds]

        # tax_commands     => line_ids (display_type=tax, one per tax repartition key)
        payments = orders._prepare_out_receipt_payment_line_data()
        line_data = [pm['account.move.line'] for pm in payments]
        payment_commands = [Command.create(pm_data) for pm_data in line_data]

        move_ctx = move.with_context(check_move_validity=False)
        move_ctx.with_company(self.company_id).write({
            'invoice_line_ids': sales_commands + refunds_commands,
            'line_ids': payment_commands,
        })
        move_ctx._post()

        all_payment_lines = self.env['pos.order']._create_payment_moves(self, payments)
        move_lines = move_ctx.line_ids
        payment_term_lines = move_lines.filtered(
            lambda line: line.display_type == 'payment_term',
        )

        to_reconcile = (payment_term_lines | all_payment_lines)
        to_reconcile.with_context(skip_invoice_sync=True).reconcile()
        return move

    def _get_invoiced_and_non_invoiced_orders(self):
        """ Return the paid orders of the session that are not invoiced. """
        self.ensure_one()
        orders = self._get_closed_orders()
        invoiced_orders = orders.filtered(
            lambda order: order.to_invoice or order.account_move,
        )
        non_invoiced_orders = orders - invoiced_orders
        return non_invoiced_orders, invoiced_orders

    def _check_invoiced_orders_are_posted(self, invoiced_orders):
        account_move = invoiced_orders.account_move
        unposted = account_move.filtered(lambda move: move.state != 'posted')
        if unposted:
            invoices = '\n'.join(f'{invoice.name} - {invoice.state}' for invoice in unposted)
            raise UserError(_(
                'You cannot close the POS when invoices are not posted.\nInvoices: %(invoices)s',
                invoices=invoices,
            ))
