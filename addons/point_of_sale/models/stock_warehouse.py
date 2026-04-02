# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    pos_type_id = fields.Many2one('stock.picking.type', string="Point of Sale Operation Type", copy=False)

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        for warehouse, vals in zip(self, vals_list):
            if 'code' not in default:
                name = vals.get('name', warehouse.name)
                clean_name = "".join(filter(str.isalnum, name)).upper()
                base_code = clean_name[:3] if len(clean_name) >= 3 else (clean_name or 'WH')

                new_code = base_code
                counter = 1
                # Ensure unique code in company
                while self.env['stock.warehouse'].search_count([
                    ('code', '=', new_code),
                    ('company_id', '=', warehouse.company_id.id)
                ], limit=1):
                    counter += 1
                    new_code = base_code + str(counter)

                vals['code'] = new_code
        return vals_list

    def _get_sequence_values(self, name=False, code=False):
        sequence_values = super()._get_sequence_values(name=name, code=code)
        company_id = self.company_id.id
        wh_code = self.code or (self.name[:3].upper() if self.name else 'WH')

        pos_prefix = wh_code + '/POS/'
        sequence_values.update({
            'pos_type_id': {
                'name': _('%(name)s Picking POS', name=self.name),
                'prefix': pos_prefix,
                'padding': 5,
                'company_id': company_id,
            }
        })

        # Ensure prefix uniqueness within the company
        IrSequence = self.env['ir.sequence'].sudo()
        for key, vals in sequence_values.items():
            base_prefix = vals.get('prefix', '')
            if not base_prefix:
                continue

            final_prefix = base_prefix
            counter = 1
            while IrSequence.search_count([
                ('company_id', '=', vals['company_id']),
                ('prefix', '=', final_prefix),
            ], limit=1):
                counter += 1
                # If prefix is 'BRU/POS/', we try 'BRU2/POS/'
                parts = base_prefix.split('/', 1)
                if len(parts) > 1:
                    final_prefix = f"{wh_code}{counter}/{parts[1]}"
                else:
                    final_prefix = f"{wh_code}{counter}/{base_prefix}"

            vals['prefix'] = final_prefix

        return sequence_values

    def _get_picking_type_update_values(self):
        picking_type_update_values = super()._get_picking_type_update_values()
        picking_type_update_values.update({
            'pos_type_id': {'default_location_src_id': self.lot_stock_id.id}
        })
        return picking_type_update_values

    def _get_picking_type_create_values(self, max_sequence):
        picking_type_create_values, max_sequence = super()._get_picking_type_create_values(max_sequence)
        picking_type_create_values.update({
            'pos_type_id': {
                'name': _('PoS Orders'),
                'code': 'outgoing',
                'default_location_src_id': self.lot_stock_id.id,
                'default_location_dest_id': self.env.ref('stock.stock_location_customers').id,
                'sequence': max_sequence + 1,
                'company_id': self.company_id.id,
            }
        })
        return picking_type_create_values, max_sequence + 2

    @api.model
    def _create_missing_pos_picking_types(self):
        warehouses = self.env['stock.warehouse'].search([('pos_type_id', '=', False)])
        for warehouse in warehouses:
            new_vals = warehouse._create_or_update_sequences_and_picking_types()
            warehouse.write(new_vals)
