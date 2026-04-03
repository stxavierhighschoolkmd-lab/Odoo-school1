from odoo import fields, models


class TestOrmMixed(models.Model):
    _name = 'test_orm.mixed'
    _description = 'Test ORM Mixed'

    # Binary Fields
    binary_with_attachment = fields.Binary()
    binary_without_attachment = fields.Binary(attachment=False)
    image_with_attachment = fields.Image()
    image_without_attachment = fields.Image(attachment=False)

    # Misc Fields
    boolean = fields.Boolean()
    json = fields.Json()

    # Numeric Fields
    integer = fields.Integer()
    float_double_precision = fields.Float()
    float_numeric = fields.Float(digits=(0, False))
    # number = fields.Float(digits=(10, 2), default=3.14)
    float_precision = fields.Float(digits='ORM Precision')
    monetary = fields.Monetary()

    # Reference Fields
    reference = fields.Reference(selection=[('option_1', 'Option 1')])
    many2one_reference = fields.Many2oneReference(model_field='res_model')

    # Relational Fields
    many2one_id = fields.Many2one(comodel_name='test_orm.mixed_relations')
    one2many_ids = fields.One2many(comodel_name='test_orm.mixed_relations', inverse_name='many2one_id')
    many2many_ids = fields.Many2many(comodel_name='test_orm.mixed_relations')

    # Selection Fields
    selection = fields.Selection(selection=[('option_1', 'Option 1')])

    # Temporal Fields
    date = fields.Date()
    datetime = fields.Datetime()

    # Textual Fields
    char = fields.Char()
    html = fields.Html()
    text = fields.Text()

    # Other
    currency_id = fields.Many2one('res.currency')  # Needed for the monetary field.
    res_model = fields.Char()  # Needed for the many2one_reference field.


class TestOrmMixedRelations(models.Model):
    # This model is used to set up 'test_orm.mixed' relations.
    _name = 'test_orm.mixed_relations'
    _description = 'Test ORM Mixed Relations'

    many2one_id = fields.Many2one(comodel_name='test_orm.mixed')
    one2many_ids = fields.One2many(comodel_name='test_orm.mixed', inverse_name='many2one_id')
    many2many_ids = fields.Many2many(comodel_name='test_orm.mixed')
