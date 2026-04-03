from unittest.mock import patch

from odoo.sql_db import Savepoint
from odoo.tests import TransactionCase, tagged


# Main nightly test of the Populate
# run with `populate.test_all_blueprints`
@tagged('populate', '-standard', '-at_install', 'post_install')
class TestAllBlueprint(TransactionCase):
    """Run all blueprints 1 by 1."""

    def test_all_blueprints(self):
        blueprints = self.env['populate.blueprint'].search([], order='id')
        self.assertTrue(blueprints, "No blueprints found.")

        for blueprint in blueprints:
            with self.subTest(blueprint=blueprint.name):
                with self.env.cr.savepoint():
                    self._run_blueprint(blueprint)

    def _run_blueprint(self, blueprint):
        savepoint: Savepoint | None = Savepoint(self.env.cr._obj)

        def fake_commit():
            nonlocal savepoint
            if savepoint is not None:
                savepoint.close(rollback=False)
            savepoint = Savepoint(self.env.cr._obj)

        def fake_rollback():
            nonlocal savepoint
            if savepoint is not None:
                savepoint.close(rollback=True)
                savepoint = Savepoint(self.env.cr._obj)

        with (
            patch.object(type(self.env['populate.session']), 'lock_for_update', lambda *_: None),
            patch.object(type(self.env['populate.job']), 'lock_for_update', lambda *_: None),
            patch.object(self.env.cr, 'commit', fake_commit),
            patch.object(self.env.cr, 'rollback', fake_rollback),
        ):
            savepoint = Savepoint(self.env.cr._obj)
            session = self.env['populate.session'].create({
                'blueprint_id': blueprint.id,
                'seed': 42,
            })
            session.start()

        self.assertTrue(session.is_done, f"Session for '{blueprint.name}' did not complete.")


# Test isn't primordial and takes a bit of time (+-1.5s)
# Can be launch manually with a prefix `populate` test tag,
# e.g. `populate.test_all_sample_blueprints`
@tagged('populate', '-standard')
class TestSampleBlueprints(TransactionCase):
    """Run one session per blueprint defined in the test_populate module."""

    def test_all_sample_blueprints(self):
        blueprints = self.env['populate.blueprint'].search([
            ('id', 'in', self.env['ir.model.data'].search([
                ('module', '=', 'test_populate'),
                ('model', '=', 'populate.blueprint'),
            ]).mapped('res_id')),
        ])

        self.assertTrue(blueprints, "No sample blueprints found for module 'test_populate'.")

        for blueprint in blueprints:
            with self.subTest(blueprint=blueprint.name):
                with patch.object(self.env.cr, 'commit', lambda: None):
                    session = self.env['populate.session'].create({
                        'blueprint_id': blueprint.id,
                    })
                    session.start()

                self.assertTrue(
                    session.is_done,
                    msg=f"Session for '{blueprint.name}' did not complete.",
                )
