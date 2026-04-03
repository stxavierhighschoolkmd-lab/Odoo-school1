from unittest.mock import MagicMock

from odoo.tests import TransactionCase
from odoo.tests.case import TestCase

from odoo.addons.populate.generators import (
    NO_UNIQ_VALUE,
    NO_VALUE,
    Boolean,
    Char,
    Float,
    Generator,
    Integer,
    RelationOne,
    get_fields_vals,
)
from odoo.addons.populate.generators.generator import partition_values
from odoo.addons.populate.utils.distributions import Distribution


class TestGeneratorUnique(TransactionCase):

    def setUp(self):
        super().setUp()
        test_product_model = self.env['test_populate.product']
        self.name_field = test_product_model._fields['name']
        self.stock_field = test_product_model._fields['stock_quantity']

    def test_generator_unique(self):
        generator = Char(field=self.name_field, env=self.env, length=10, unique=True, null_frac=0)

        values = [next(generator) for _ in range(50)]

        self.assertEqual(len(values), len(set(values)))
        self.assertTrue(all(isinstance(val, str) and len(val) == 10 for val in values))

    def test_generator_unique_with_existing_records(self):
        existing_names = ['ExistName01', 'ExistName02', 'ExistName03']
        self.env['test_populate.product'].create([
            {'name': name, 'price': 10.0} for name in existing_names
        ])

        generator = Char(field=self.name_field, env=self.env, length=11, unique=True, null_frac=0)

        values = [next(generator) for _ in range(20)]

        for value in values:
            self.assertNotIn(value, existing_names)

        self.assertEqual(len(values), len(set(values)))

    def test_unique_generator_exhaustion(self):
        generator = Integer(field=self.stock_field, env=self.env, start=1, end=3, unique=True, null_frac=0)

        values = []
        for _ in range(3):
            values.append(next(generator))

        self.assertEqual(len(set(values)), 3)

        self.assertIs(next(generator), NO_UNIQ_VALUE)


class TestGeneratorDepends(TransactionCase):

    def setUp(self):
        super().setUp()
        test_product_model = self.env['test_populate.product']
        self.name_field = test_product_model._fields['name']
        self.price_field = test_product_model._fields['price']
        self.stock_field = test_product_model._fields['stock_quantity']

    def test_generator_depends_basic(self):
        generator = Integer(
            field=self.stock_field,
            env=self.env,
            start=1,
            end=1000,
            depends=['price'],
            null_frac=0,
        )

        value = generator.send({})
        self.assertEqual(value, NO_VALUE)

        value = generator.send({'price': 50.0})
        self.assertIsInstance(value, int)
        self.assertTrue(1 <= value <= 1000)

    def test_generator_depends_multiple_fields(self):
        generator = Char(
            field=self.name_field,
            env=self.env,
            length=10,
            depends=['price', 'category'],
            null_frac=0,
        )

        value = generator.send({})
        self.assertEqual(value, NO_VALUE)

        value = generator.send({'price': 50.0})
        self.assertEqual(value, NO_VALUE)

        value = generator.send({'price': 50.0, 'category': 'electronics'})
        self.assertIsInstance(value, str)
        self.assertEqual(len(value), 10)

    def test_generator_depends_invalid_field(self):
        with self.assertRaises(ValueError) as cm:
            Integer(
                field=self.stock_field,
                env=self.env,
                start=1,
                end=1000,
                depends=['nonexistent_field'],
                null_frac=0,
            )

        self.assertIn("Invalid field dependencies", str(cm.exception))

    def test_generator_depends_with_get_fields_vals(self):
        stock_gen = Integer(
            field=self.stock_field,
            env=self.env,
            start=1,
            end=1000,
            depends=['price'],
            null_frac=0,
        )

        price_gen = Float(
            field=self.price_field,
            env=self.env,
            start=10.0,
            end=100.0,
            null_frac=0,
        )

        generators = {
            'stock_quantity': stock_gen,
            'price': price_gen,
        }

        vals = get_fields_vals(generators)

        self.assertIn('price', vals)
        self.assertIn('stock_quantity', vals)
        self.assertIsInstance(vals['price'], float)
        self.assertIsInstance(vals['stock_quantity'], int)

    def test_generator_depends_circular_dependency_fails(self):
        stock_gen = Integer(
            field=self.stock_field,
            env=self.env,
            start=1,
            end=1000,
            depends=['price'],
            null_frac=0,
        )

        price_gen = Float(
            field=self.price_field,
            env=self.env,
            start=10.0,
            end=100.0,
            depends=['stock_quantity'],
            null_frac=0,
        )

        generators = {
            'stock_quantity': stock_gen,
            'price': price_gen,
        }

        with self.assertRaises(RuntimeError) as cm:
            get_fields_vals(generators)

        self.assertIn("Circular dependency", str(cm.exception))


class TestGeneratorKwargs(TransactionCase):

    def test_get_kwargs(self):
        attrs = {
            'generator': 'textual.char',
            'length': '15',
            'eval': '"static value"',
            'values': "{'a': 3.5, 'b': 1, 'c': 2.1}",
            'domain': "[('active', '=', True)]",
            'unique': 'True',
            'null_frac': '0.3',
            'ref': 'some_reference_model',
            'distribution': 'normal(mean=5, std=8)',
            'unknown_attr': 'should_be_ignored',
        }

        kwargs = Generator.get_kwargs(attrs)
        # partial by default for `get_kwargs`, just make it an instance
        kwargs['distribution'] = kwargs['distribution']()

        expected = {
            'values': {'a': 3.5, 'b': 1, 'c': 2.1},
            'null_frac': 0.3,
            'distribution': Distribution.from_definition('normal(mean=5, std=8)'),
            'unique': True,
        }

        self.assertDictEqual(kwargs, expected)


class TestGeneratorFieldValidation(TransactionCase):

    def setUp(self):
        super().setUp()
        test_product_model = self.env['test_populate.product']
        self.name_field = test_product_model._fields['name']
        self.active_field = test_product_model._fields['active']

    def test_generator_field_type_validation(self):
        boolean_gen = Boolean(field=self.active_field, env=self.env)
        self.assertIsInstance(boolean_gen, Boolean)

        with self.assertRaises(TypeError):
            Boolean(field=self.name_field, env=self.env)


class TestGeneratorInstantiation(TransactionCase):

    def setUp(self):
        super().setUp()
        test_product_model = self.env['test_populate.product']
        self.name_field = test_product_model._fields['name']

    def test_generator_instantiation(self):
        GeneratorChar = Generator.get('textual.char')
        generator = GeneratorChar(field=self.name_field, env=self.env, length=8)

        self.assertIsInstance(generator, Char)
        self.assertEqual(generator.length, 8)


class TestGetFieldsVals(TransactionCase):

    def setUp(self):
        super().setUp()
        test_product_model = self.env['test_populate.product']
        self.name_field = test_product_model._fields['name']
        self.price_field = test_product_model._fields['price']

    def test_get_fields_vals(self):
        name_gen = Char(field=self.name_field, env=self.env, length=10, null_frac=0)
        price_gen = Float(field=self.price_field, env=self.env, start=1.0, end=100.0, null_frac=0)

        generators = {
            'name': name_gen,
            'price': price_gen,
        }

        vals = get_fields_vals(generators)

        self.assertIn('name', vals)
        self.assertIn('price', vals)

        self.assertIsInstance(vals['name'], str)
        self.assertIsInstance(vals['price'], float)


class TestPartitionValues(TestCase):

    def test_partition_values_basic(self):
        values = [0, 1, 2, 3, 4, 5]
        self.assertEqual(partition_values(values, count=2, index=0), [0, 2, 4])
        self.assertEqual(partition_values(values, count=2, index=1), [1, 3, 5])

    def test_partition_values_three_way(self):
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        p0 = partition_values(values, count=3, index=0)
        p1 = partition_values(values, count=3, index=1)
        p2 = partition_values(values, count=3, index=2)

        # All partitions together must cover all values exactly once
        self.assertEqual(sorted(p0 + p1 + p2), values)

        self.assertEqual(p0, [10, 40, 70])
        self.assertEqual(p1, [20, 50, 80])
        self.assertEqual(p2, [30, 60, 90])

    def test_partition_values_single_partition(self):
        values = [1, 2, 3]
        self.assertEqual(partition_values(values, count=1, index=0), values)

    def test_partition_values_more_partitions_than_values(self):
        values = [42]
        self.assertEqual(partition_values(values, count=3, index=0), [42])
        self.assertEqual(partition_values(values, count=3, index=1), [])
        self.assertEqual(partition_values(values, count=3, index=2), [])

    def test_partition_values_empty_sequence(self):
        self.assertEqual(partition_values([], count=3, index=0), [])

    def test_partition_values_no_overlap(self):
        values = list(range(12))
        partitions = [partition_values(values, count=4, index=i) for i in range(4)]
        all_values = [v for part in partitions for v in part]
        self.assertEqual(sorted(all_values), values)
        for i, part in enumerate(partitions):
            for j, other in enumerate(partitions):
                if i != j:
                    self.assertTrue(set(part).isdisjoint(set(other)))


class TestComodelGeneratorPartition(TransactionCase):

    def setUp(self):
        super().setUp()
        self.supplier_field = self.env['test_populate.product']._fields['supplier_id']
        self.suppliers = self.env['test_populate.supplier'].create([
            {'name': f'Supplier {i}', 'country_code': 'US'}
            for i in range(6)
        ])

    def test_partition_false_does_not_partition(self):
        gen = RelationOne(
            field=self.supplier_field,
            env=self.env,
            null_frac=0,
            partition=False,
        )
        self.assertIsNone(gen.partition)
        self.assertEqual(set(gen.comodel_ids), set(self.suppliers.ids))

    def test_partition_true_requires_job(self):
        with self.assertRaises(AssertionError):
            RelationOne(
                field=self.supplier_field,
                env=self.env,
                null_frac=0,
                partition=True,
            )

    def test_partition_true_no_parent_returns_all(self):
        mock_job = MagicMock()
        mock_job.env = self.env
        mock_job.session_id = None
        mock_job.parent_id = None  # no parent -> no partition applied

        gen = RelationOne(
            field=self.supplier_field,
            env=None,
            job=mock_job,
            null_frac=0,
            partition=True,
        )
        self.assertIsNone(gen.partition)
        self.assertEqual(set(gen.comodel_ids), set(self.suppliers.ids))

    def test_partition_true_with_siblings_splits_ids(self):
        """With partition=True and sibling jobs, each job gets a disjoint subset."""
        all_supplier_ids = self.suppliers.ids  # 6 ids

        # Simulate 2 sibling jobs with a common parent
        job_a = MagicMock()
        job_a.id = 1
        job_b = MagicMock()
        job_b.id = 2

        parent = MagicMock()
        parent.child_ids.ids = [job_a.id, job_b.id]

        job_a.env = self.env
        job_a.session_id = None
        job_a.parent_id = parent

        job_b.env = self.env
        job_b.session_id = None
        job_b.parent_id = parent

        gen_a = RelationOne(field=self.supplier_field, env=None, job=job_a, null_frac=0, partition=True)
        gen_b = RelationOne(field=self.supplier_field, env=None, job=job_b, null_frac=0, partition=True)

        ids_a = set(gen_a.comodel_ids)
        ids_b = set(gen_b.comodel_ids)

        self.assertTrue(ids_a.isdisjoint(ids_b))
        self.assertEqual(ids_a | ids_b, set(all_supplier_ids))
