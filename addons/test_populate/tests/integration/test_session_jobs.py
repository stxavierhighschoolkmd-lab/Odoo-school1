from unittest.mock import patch

from odoo.tests import TransactionCase


class TestJobTypes(TransactionCase):

    def test_eval_generator(self):
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Eval Generator Test',
            'definition_json': [
                {
                    'name': 'test_populate.product',
                    'count': 3,
                    'fields': {
                        'name': {'eval': '"Test Product"'},
                        'price': {'eval': '99.99'},
                        'active': {'eval': 'True'},
                        'stock_quantity': {'eval': '100'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        initial_count = self.env['test_populate.product'].search_count([])

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        final_count = self.env['test_populate.product'].search_count([])
        self.assertEqual(final_count - initial_count, 3)

        created_products = self.env['test_populate.product'].search([
            ('name', '=', 'Test Product'),
            ('price', '=', 99.99),
            ('active', '=', True),
            ('stock_quantity', '=', 100),
        ])
        self.assertEqual(len(created_products), 3)

    def test_eval_lambda_generator(self):
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Eval Lambda Generator Test',
            'definition_json': [
                {
                    'name': 'test_populate.product',
                    'count': 5,
                    'fields': {
                        'name': {'eval': '"Product"'},
                        'price': {
                            'generator': 'scalar.float',
                            'start': 10.0,
                            'end': 100.0,
                        },
                        'stock_quantity': {
                            'eval': 'int(price * 2)',
                        },
                        'description': {
                            'eval': 'f"{name} costs ${price:.2f}"',
                        },
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        initial_count = self.env['test_populate.product'].search_count([])

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        final_count = self.env['test_populate.product'].search_count([])
        self.assertEqual(final_count - initial_count, 5)

        product_ids = self.env['populate.model.data'].search([
            ('session_id', '=', session.id),
            ('res_model', '=', 'test_populate.product'),
        ]).mapped('res_id')

        created_products = self.env['test_populate.product'].browse(product_ids)
        self.assertEqual(len(created_products), 5)

        for product in created_products:
            expected_stock = int(product.price * 2)
            self.assertEqual(product.stock_quantity, expected_stock)

            expected_description = f"{product.name} costs ${product.price:.2f}"
            self.assertEqual(product.description, expected_description)

            self.assertEqual(product.name, "Product")

    def test_write_job_type(self):
        existing_products = self.env['test_populate.product'].create([
            {'name': 'Product 1', 'price': 10.0},
            {'name': 'Product 2', 'price': 20.0},
        ])

        blueprint = self.env['populate.blueprint'].create({
            'name': 'Write Test Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.product',
                    'type': 'write',
                    'count': 1,
                    'fields': {
                        'description': {'generator': 'textual.text', 'length': 50, 'null_frac': 0},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        updated_products = self.env['test_populate.product'].browse(existing_products.ids)
        for product in updated_products:
            self.assertTrue(product.description)

    def test_blueprint_with_write_jobs_and_references(self):
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Create and Write Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.supplier',
                    'ref': 'test_suppliers',
                    'count': 2,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 20},
                        'email': {'generator': 'textual.char', 'length': 25},
                        'is_active': {'eval': 'True', 'null_frac': 0},
                    },
                },
                {
                    'name': 'test_populate.supplier',
                    'type': 'write',
                    'ref': 'test_suppliers',
                    'fields': {
                        'rating': {'generator': 'scalar.float', 'start': 4.0, 'end': 5.0, 'null_frac': 0},
                        'notes': {'eval': '"Updated via write job"', 'null_frac': 0},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        initial_supplier_count = self.env['test_populate.supplier'].search_count([])

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        final_supplier_count = self.env['test_populate.supplier'].search_count([])

        self.assertEqual(final_supplier_count - initial_supplier_count, 2)

        model_data_entries = self.env['populate.model.data'].search([
            ('res_model', '=', 'test_populate.supplier'),
            ('session_id', '=', session.id),
            ('ref', '=', 'test_suppliers'),
        ])
        self.assertEqual(len(model_data_entries), 2)

        created_supplier_ids = [entry.res_id for entry in model_data_entries]
        updated_suppliers = self.env['test_populate.supplier'].browse(created_supplier_ids)

        for supplier in updated_suppliers:
            self.assertTrue(supplier.is_active)
            self.assertTrue(supplier.rating)
            self.assertEqual(supplier.notes, "Updated via write job")

    def test_write_job_without_ref_updates_all_records(self):
        existing_suppliers = self.env['test_populate.supplier'].create([
            {'name': 'Existing Supplier 1', 'is_active': True},
            {'name': 'Existing Supplier 2', 'is_active': True},
        ])

        blueprint = self.env['populate.blueprint'].create({
            'name': 'Write All Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.supplier',
                    'type': 'write',
                    'fields': {
                        'notes': {'eval': '"Global update"', 'null_frac': 0},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        updated_suppliers = self.env['test_populate.supplier'].browse(existing_suppliers.ids)
        for supplier in updated_suppliers:
            self.assertEqual(supplier.notes, "Global update")


class TestSubjobs(TransactionCase):

    def test_large_record_count_subjobs(self):
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Large Count Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.product',
                    'count': 25000,
                    'fields': {
                        'name': {'generator': 'textual.char'},
                        'price': {'generator': 'scalar.float'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
            'worker_count': 3,
        })

        self.assertTrue(session.job_ids.child_ids)

    def test_write_job_record_count_with_ref(self):
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Write Ref Count Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.customer',
                    'count': 50,
                    'ref': 'my_customers',
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 10},
                        'email': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.customer',
                    'type': 'write',
                    'ref': 'my_customers',
                    'fields': {
                        'is_vip': {'eval': 'True'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        jobs = session.job_ids
        create_job = jobs.filtered(lambda j: j.type == 'create')
        write_job = jobs.filtered(lambda j: j.type == 'write')

        self.assertEqual(create_job.record_count, 50)
        self.assertEqual(write_job.record_count, 50,
                         "Write job should have the same record_count as the referenced create job")

    def test_write_job_record_count_without_ref_existing_records(self):
        self.env['test_populate.customer'].create([
            {'name': f'Customer {i}', 'email': f'c{i}@test.com'}
            for i in range(10)
        ])

        blueprint = self.env['populate.blueprint'].create({
            'name': 'Write No Ref Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.customer',
                    'type': 'write',
                    'fields': {
                        'is_vip': {'eval': 'True'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        write_job = session.job_ids.filtered(lambda j: j.type == 'write')
        expected_count = self.env['test_populate.customer'].search_count([])
        self.assertEqual(write_job.record_count, expected_count,
                         "Write job without ref should have record_count equal to existing records in DB")

    def test_write_job_record_count_without_ref_includes_preceding_creates(self):
        existing = self.env['test_populate.customer'].create([
            {'name': 'Existing', 'email': 'existing@test.com'},
        ])

        blueprint = self.env['populate.blueprint'].create({
            'name': 'Create Then Write No Ref Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.customer',
                    'count': 20,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 10},
                        'email': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.customer',
                    'type': 'write',
                    'fields': {
                        'is_vip': {'eval': 'True'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        write_job = session.job_ids.filtered(lambda j: j.type == 'write')
        self.assertEqual(write_job.record_count, len(existing) + 20,
                         "Write job without ref should count existing records + records from preceding create jobs")

    def test_write_job_creates_subjobs_when_large(self):
        create_count = 25000  # > MAX_RECORD_COMMIT_SIZE (10000)

        blueprint = self.env['populate.blueprint'].create({
            'name': 'Large Write Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.customer',
                    'count': create_count,
                    'ref': 'big_customers',
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 10},
                        'email': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.customer',
                    'type': 'write',
                    'ref': 'big_customers',
                    'fields': {
                        'is_vip': {'eval': 'True'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
            'worker_count': 3,
        })

        write_job = session.job_ids.filtered(lambda j: j.type == 'write' and not j.parent_id)
        self.assertTrue(write_job.child_ids,
                        "Write job with large record_count should be split into subjobs")
        self.assertEqual(write_job.record_count, create_count)
        self.assertEqual(
            sum(write_job.child_ids.mapped('record_count')),
            write_job.record_count,
            "Subjobs record counts should sum up to parent's record_count",
        )

    def test_write_subjobs_have_correct_offset_and_limit(self):
        self.env['test_populate.customer'].create([
            {'name': f'Customer {i}', 'email': f'c{i}@test.com'}
            for i in range(5)
        ])

        blueprint = self.env['populate.blueprint'].create({
            'name': 'Write Ref Small Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.customer',
                    'count': 5,
                    'ref': 'some_customers',
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 10},
                        'email': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.customer',
                    'type': 'write',
                    'ref': 'some_customers',
                    'fields': {
                        'notes': {'eval': '"Updated"', 'null_frac': 0},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        # Verify the created records were updated (write job targeted them via ref)
        model_data = self.env['populate.model.data'].search([
            ('session_id', '=', session.id),
            ('res_model', '=', 'test_populate.customer'),
            ('ref', '=', 'some_customers'),
        ])
        created_ids = model_data.mapped('res_id')
        updated_customers = self.env['test_populate.customer'].browse(created_ids)
        for customer in updated_customers:
            self.assertEqual(customer.notes, "Updated",
                             "Each record in the ref batch should have been updated by the write job")

    def test_write_job_scaling_factor_applied_to_record_count(self):
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Scaled Write Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.customer',
                    'count': 100,
                    'ref': 'scaled_customers',
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 10},
                        'email': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.customer',
                    'type': 'write',
                    'ref': 'scaled_customers',
                    'fields': {
                        'is_vip': {'eval': 'True'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
            'scaling_factor': 5.0,
        })

        create_job = session.job_ids.filtered(lambda j: j.type == 'create' and not j.parent_id)
        write_job = session.job_ids.filtered(lambda j: j.type == 'write' and not j.parent_id)

        self.assertEqual(create_job.record_count, 500)  # 100 * 5.0
        self.assertEqual(write_job.record_count, 500,
                         "Write job record_count should match the scaled create count")

    def test_multiple_create_jobs_same_model_no_ref_write(self):
        self.env['test_populate.customer'].create([
            {'name': 'Pre-existing', 'email': 'pre@test.com'},
        ])
        existing_count = self.env['test_populate.customer'].search_count([])

        blueprint = self.env['populate.blueprint'].create({
            'name': 'Multi Create Then Write Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.customer',
                    'count': 10,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 10},
                        'email': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.customer',
                    'count': 15,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 10},
                        'email': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.customer',
                    'type': 'write',
                    'fields': {
                        'notes': {'eval': '"batch update"', 'null_frac': 0},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
        })

        write_job = session.job_ids.filtered(lambda j: j.type == 'write')
        expected = existing_count + 10 + 15
        self.assertEqual(write_job.record_count, expected,
                         "Write job without ref should sum existing records + all preceding unreferenced creates")


class TestRelationalRefDomain(TransactionCase):
    """Tests for the get_ref_domain() dotted-path (ref.field) feature."""

    def test_write_job_with_relational_ref_targets_corecords(self):
        """
        A write job with ref='some_ref.relation_field' should update
        records reachable via the relational path, not the ref'd records themselves.
        """
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Relational Ref Write Test',
            'definition_json': [
                {
                    'name': 'test_populate.supplier',
                    'ref': 'test_suppliers',
                    'count': 2,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 20},
                        'is_active': {'eval': 'True'},
                    },
                },
                {
                    'name': 'test_populate.product',
                    'count': 4,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 15},
                        'price': {'generator': 'scalar.float', 'start': 10.0, 'end': 100.0},
                        'supplier_id': {
                            'generator': 'relation.one',
                            'ref': 'test_suppliers',
                            'null_frac': '0.0',
                        },
                    },
                },
                {
                    # Write on products reachable via supplier_ids.product_ids
                    'name': 'test_populate.product',
                    'type': 'write',
                    'ref': 'test_suppliers.product_ids',
                    'fields': {
                        'description': {'eval': '"Updated via relational ref"', 'null_frac': '0'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({'blueprint_id': blueprint.id})

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        supplier_model_data = self.env['populate.model.data'].search([
            ('session_id', '=', session.id),
            ('res_model', '=', 'test_populate.supplier'),
        ])
        created_supplier_ids = supplier_model_data.mapped('res_id')
        suppliers = self.env['test_populate.supplier'].browse(created_supplier_ids)

        # Products linked to our suppliers should have been updated
        linked_products = suppliers.mapped('product_ids')
        self.assertTrue(linked_products, "Expected products linked to populated suppliers")
        for product in linked_products:
            self.assertEqual(product.description, "Updated via relational ref")

    def test_write_job_with_multilevel_relational_ref(self):
        """
        Exercises a multi-level relational path across three distinct models:
          'test_warehouses_ml.supplier_ids.product_ids'

        Chain:
          test_populate.warehouse  (ref'd)
            -> .supplier_ids       (one2many -> test_populate.supplier)
            -> .product_ids        (one2many -> test_populate.product)

        The write job targets test_populate.product records reachable via
        the two-hop traversal. Products not linked to any of the ref'd
        warehouses' suppliers must NOT be updated.
        """
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Multilevel Relational Ref Write Test',
            'definition_json': [
                {
                    'name': 'test_populate.warehouse',
                    'ref': 'test_warehouses_ml',
                    'count': 2,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 15},
                    },
                },
                {
                    'name': 'test_populate.supplier',
                    'count': 3,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 20},
                        'warehouse_id': {
                            'generator': 'relation.one',
                            'ref': 'test_warehouses_ml',
                            'null_frac': '0.0',
                        },
                    },
                },
                {
                    'name': 'test_populate.product',
                    'count': 6,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 15},
                        'price': {'generator': 'scalar.float', 'start': 1.0, 'end': 100.0},
                        'supplier_id': {
                            'generator': 'relation.one',
                            'null_frac': '0.0',
                        },
                    },
                },
                {
                    # Two-level path: warehouse -> supplier_ids -> product_ids
                    # Only products whose supplier belongs to one of the ref'd warehouses
                    # should be updated.
                    'name': 'test_populate.product',
                    'type': 'write',
                    'ref': 'test_warehouses_ml.supplier_ids.product_ids',
                    'fields': {
                        'description': {'eval': '"Updated via multi-level ref"', 'null_frac': '0'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({'blueprint_id': blueprint.id})

        with patch.object(self.env.cr, 'commit', lambda: None):
            session.start()

        warehouse_ids = self.env['populate.model.data'].search([
            ('session_id', '=', session.id),
            ('res_model', '=', 'test_populate.warehouse'),
        ]).mapped('res_id')
        warehouses = self.env['test_populate.warehouse'].browse(warehouse_ids)

        reachable_products = warehouses.mapped('supplier_ids.product_ids')
        self.assertTrue(reachable_products, "Expected products reachable via the multi-level path")

        for product in reachable_products:
            self.assertEqual(
                product.description,
                "Updated via multi-level ref",
                f"Product {product.name!r} reachable via warehouse->supplier->product should be updated",
            )

        # Products whose supplier is NOT under any ref'd warehouse must be untouched.
        all_product_ids = self.env['populate.model.data'].search([
            ('session_id', '=', session.id),
            ('res_model', '=', 'test_populate.product'),
        ]).mapped('res_id')
        all_products = self.env['test_populate.product'].browse(all_product_ids)
        unreachable_products = all_products - reachable_products

        for product in unreachable_products:
            self.assertNotEqual(
                product.description,
                "Updated via multi-level ref",
                f"Product {product.name!r} outside the ref chain should NOT be updated",
            )

    def test_write_job_relational_ref_record_count_is_zero_at_creation(self):
        """
        A write job with a dotted ref (ref.relation) cannot know its record_count
        at creation time — it should be stored as 0 (None semantics).
        """
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Relational Ref Zero Count Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.supplier',
                    'ref': 'ref_suppliers',
                    'count': 3,
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 20},
                        'is_active': {'eval': 'True'},
                    },
                },
                {
                    'name': 'test_populate.product',
                    'type': 'write',
                    'ref': 'ref_suppliers.product_ids',
                    'fields': {
                        'description': {'eval': '"rel ref write"', 'null_frac': '0'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({'blueprint_id': blueprint.id})

        write_job = session.job_ids.filtered(
            lambda j: j.type == 'write' and not j.parent_id,
        )
        self.assertEqual(len(write_job), 1)
        self.assertEqual(
            write_job.record_count, 0,
            "Write job with relational ref should have record_count=0 (unknown at creation time)",
        )

    def test_write_job_relational_ref_not_split_into_subjobs(self):
        """
        A write job with record_count=0 (relational ref) must NOT be split into subjobs,
        since the cardinality is unknown.
        """
        blueprint = self.env['populate.blueprint'].create({
            'name': 'Relational Ref No Split Blueprint',
            'definition_json': [
                {
                    'name': 'test_populate.supplier',
                    'ref': 'suppliers_nosplit',
                    'count': 30000,  # Large enough that a known count would trigger a split
                    'fields': {
                        'name': {'generator': 'textual.char', 'length': 20},
                        'is_active': {'eval': 'True'},
                    },
                },
                {
                    'name': 'test_populate.product',
                    'type': 'write',
                    'ref': 'suppliers_nosplit.product_ids',
                    'fields': {
                        'description': {'eval': '"no split"', 'null_frac': '0'},
                    },
                },
            ],
        })

        session = self.env['populate.session'].create({
            'blueprint_id': blueprint.id,
            'worker_count': 3,
        })

        write_job = session.job_ids.filtered(
            lambda j: j.type == 'write' and not j.parent_id,
        )
        self.assertFalse(
            write_job.child_ids,
            "Write job with unknown record_count (relational ref) should not be split into subjobs",
        )
