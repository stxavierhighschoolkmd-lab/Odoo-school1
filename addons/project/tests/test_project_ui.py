# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.group_user').sudo().implied_ids |= cls.env.ref('project.group_project_milestone')

    def test_01_project_tour(self):
        self.start_tour("/odoo", 'project_tour', login="admin")

    def test_project_task_history(self):
        """This tour will check that the history works properly."""
        stage = self.env['project.task.type'].create({'name': 'To Do'})
        _dummy, project2 = self.env['project.project'].create([{
            'name': 'Without tasks project',
            'type_ids': stage.ids,
        }, {
            'name': 'Test History Project',
            'type_ids': stage.ids,
        }])

        self.env['project.task'].create({
            'name': 'Test History Task',
            'stage_id': stage.id,
            'project_id': project2.id,
        })

        self.start_tour('/odoo?debug=1', 'project_task_history_tour', login='admin')

    def test_project_task_last_history_steps(self):
        """This tour will check that the history works properly."""
        stage = self.env['project.task.type'].create({'name': 'To Do'})
        project = self.env['project.project'].create([{
            'name': 'Test History Project',
            'type_ids': stage.ids,
        }])

        self.env['project.task'].create({
            'name': 'Test History Task',
            'stage_id': stage.id,
            'project_id': project.id,
        })

        self.start_tour('/odoo', 'project_task_last_history_steps_tour', login='admin')

    def test_project_private_task_tour(self):
        """Tour verifying that a Private task (To-Do with no project) opened in the
        Project app retains its "Private" placeholder and is not treated as required.
        """
        self.env['project.task'].create({
            'name': 'Private Task Test',
            'project_id': False,
            'user_ids': [self.env.ref('base.user_admin').id],
        })
        self.start_tour('/odoo/my-tasks', 'project_private_task_tour', login='admin')
