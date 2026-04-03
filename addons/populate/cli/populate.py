from __future__ import annotations

import logging
import optparse
import os
import sys
import time
from typing import TYPE_CHECKING

from odoo import api
from odoo.cli import Command
from odoo.modules import initialize_sys_path
from odoo.modules.registry import Registry
from odoo.tools import config

if TYPE_CHECKING:
    from ..models.blueprint import Blueprint
    from ..models.session import Session

_logger = logging.getLogger(__name__)


class Populate(Command):
    """Populate an Odoo database with synthetic data using blueprints."""

    def run(self, cmdargs):
        self._setup_options()
        config.parse_config(cmdargs + ['--no-http'], setup_logging=True)

        dbname = self._require_single_db()

        _logger.info("Connecting to database '%s'...", dbname)
        initialize_sys_path()
        with Registry(dbname).cursor() as cr:
            env = api.Environment(cr, api.SUPERUSER_ID, {})
            session = self._create(env) if config['resuming'] is None else self._resume(env)
            self._execute(session)

    def _setup_options(self):
        parser = config.parser
        parser.prog = self.prog
        group = optparse.OptionGroup(parser, "Populate Configuration")
        group.add_option(
            '--blueprint', '-b', dest='blueprint',
            help="Full xmlid of the Blueprint to execute, or its name.",
        )
        group.add_option(
            '--seed', dest='seed', type='int', my_default=None,
            help="Seed for the random number generator.",
        )
        group.add_option(
            '--scale', dest='scale', type='float', my_default=1,
            help="Factor by which 'counts' in the blueprint should be scaled.",
        )
        group.add_option(
            '--jobs', '-j', dest='job_runners', type='string', my_default='1',
            help="Number of parallel processes to be used for the populate.\n"
                 "Use 'auto' to use all hardware threads.",
        )
        group.add_option(
            '--resume', dest='resuming', type='int', nargs='?', const=0, my_default=None,
            help="Resume from a previous session.\n"
                 "Use without argument to resume the last session, or provide a session ID.",
        )
        parser.add_option_group(group)
        config._load_default_options()

    @staticmethod
    def _require_single_db() -> str:
        dbnames = config['db_name']
        if not dbnames:
            sys.exit("Error: Database name is required. Use -d/--database option.")
        if len(dbnames) > 1:
            sys.exit("Error: Multiple databases specified. Please provide a single database.")
        return dbnames[0]

    @staticmethod
    def _resolve_blueprint(env: api.Environment) -> Blueprint:
        name = config['blueprint']
        if not name:
            sys.exit("Error: Blueprint is required. Use -b/--blueprint option.")

        blueprint = env.ref(name, raise_if_not_found=False)
        if not blueprint:
            blueprint = env['populate.blueprint'].search([('name', '=', name)])

        if not blueprint:
            sys.exit(
                f"Error: Blueprint '{name}' was not found in the database. "
                f"Please double check the name, and make sure the relevant module is installed."  # noqa: COM812
            )
        if len(blueprint) > 1:
            sys.exit(
                f"Error: Multiple blueprints found with name '{name}'. "
                f"Please specify the fully qualified xmlid."  # noqa: COM812
            )
        return blueprint

    @staticmethod
    def _create(env: api.Environment) -> Session:
        blueprint = Populate._resolve_blueprint(env)
        worker_count = (
            os.cpu_count()
            if config['job_runners'] == 'auto'
            else int(config['job_runners'])
        )
        vals = {
            'blueprint_id': blueprint.id,
            'worker_count': worker_count,
            'scaling_factor': config['scale'],
        }
        if (seed := config['seed']) is not None:
            vals['seed'] = seed

        session = env['populate.session'].create(vals)

        _logger.info("Created populate session %d", session.id)
        # Commit the newly created session,
        # so it can be resumed or used in multiprocess mode.
        session.env.cr.commit()
        return session

    @staticmethod
    def _resume(env: api.Environment) -> Session:
        session_id = config['resuming']
        if session_id:
            session = env['populate.session'].browse(session_id)
        else:
            session = env['populate.session'].search(
                domain=[('job_ids.is_done', '=', False)],
                order='id desc',
                limit=1,
            )

        if not session.exists():
            sys.exit("Error: No session found to resume.")

        _logger.info("Resuming populate session %d", session.id)
        return session

    @staticmethod
    def _execute(session: Session):
        time_start = time.time()
        try:
            session.start()
        except KeyboardInterrupt:
            session.env.cr.rollback()
            _logger.info("Interrupted populate session %d. Resume later with `--resume`.", session.id)
            sys.exit(1)
        except Exception:
            session.env.cr.rollback()
            _logger.exception("Failed to execute blueprint '%s'", session.blueprint_id.name)
            sys.exit(1)

        duration = Populate._format_duration(time.time() - time_start)
        _logger.info("Blueprint '%s' executed successfully in %s", session.blueprint_id.name, duration)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m {secs:.3f}s"

        if minutes > 0:
            return f"{int(minutes)}m {secs:.3f}s"

        return f"{secs:.3f}s"
