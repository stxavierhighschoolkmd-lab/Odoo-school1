from odoo import fields, models


class TestSearchInitialRelation(models.Model):
    _name = 'test_search.initial_rel'
    _description = 'Test Search Model Initial Relation'

    m2o_id = fields.Many2one(comodel_name='test_search.intermediate_rel')
    m2o_required_id = fields.Many2one(comodel_name='test_search.intermediate_rel', required=True)


class TestSearchIntermediateRelation(models.Model):
    _name = 'test_search.intermediate_rel'
    _description = 'Test Search Model Intermediate Relation'

    name = fields.Char()

    o2m_ids = fields.One2many(comodel_name='test_search.initial_rel', inverse_name='m2o_id')
    o2m_required_ids = fields.One2many(comodel_name='test_search.initial_rel', inverse_name='m2o_required_id')

    m2o_id = fields.Many2one(comodel_name='test_search.last_rel')
    m2o_required_id = fields.Many2one(comodel_name='test_search.last_rel', required=True)


class TestSearchLastRelation(models.Model):
    _name = 'test_search.last_rel'
    _description = 'Test Search Model Last Relation'

    name = fields.Char()

    o2m_ids = fields.One2many(comodel_name='test_search.intermediate_rel', inverse_name='m2o_id')
    o2m_required_ids = fields.One2many(comodel_name='test_search.intermediate_rel', inverse_name='m2o_required_id')
