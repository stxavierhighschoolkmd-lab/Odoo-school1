from __future__ import annotations

import logging
import math
import multiprocessing as mp
import os
import secrets
import signal
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import TYPE_CHECKING, Self

import psycopg2
from psycopg2.errors import (
    CheckViolation,
    ExclusionViolation,
    NotNullViolation,
    UniqueViolation,
)

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import ConcurrencyError, LockError, UserError, ValidationError
from odoo.http.retrying import retrying
from odoo.modules import initialize_sys_path
from odoo.modules.registry import Registry
from odoo.netsvc import init_logger
from odoo.tools import config, mute_logger, str2bool

from ..utils.seed import derive_seed_from

if TYPE_CHECKING:
    from .job import Job

PG_EXCEPTIONS_TO_RETRY = (
    CheckViolation,
    ExclusionViolation,
    NotNullViolation,
    UniqueViolation,
)

_logger = logging.getLogger(__name__)


def has_platform_enabled_multiprocessing() -> bool:
    """Checks if the platform has allowed multiprocessing for the `populate` feature."""
    # opt-in by default, easier user onboarding.
    return str2bool(os.getenv('ODOO_POPULATE_MULTIPROCESS_ENABLE', 'True'))


class Session(models.Model):
    """
    Single execution run of a blueprint.

    A session owns the full set of ``populate.job`` records produced
    from its blueprint and tracks their completion state.
    Interrupted sessions can be resumed — only pending jobs are re-executed.
    """
    _name = 'populate.session'
    _description = 'Data Population Session'

    seed = fields.Integer("Seed", default=lambda _: secrets.randbits(31) - 1)
    scaling_factor = fields.Float("Scaling Factor")
    worker_count = fields.Integer("Number of parallel workers that will run jobs at the same time", default=1)
    blueprint_id = fields.Many2one('populate.blueprint', required=True)
    job_ids = fields.One2many('populate.job', inverse_name='session_id', domain=[('parent_id', '=', False)])

    @api.constrains('job_ids')
    def _check_has_jobs(self):
        for session in self:
            if not session.job_ids:
                raise ValidationError(self.env._("A created session should have jobs associated from a blueprint."))

    @property
    def is_done(self) -> bool:
        self.ensure_one()
        return self.job_ids and all(self.job_ids.mapped('is_done'))

    @property
    def is_parallel(self) -> bool:
        self.ensure_one()
        return self.worker_count > 1

    @property
    def pending_jobs(self):
        self.ensure_one()
        return self.job_ids.filtered(lambda job: not job.is_done)

    @property
    def progress(self) -> float:
        """Get the progress of the session as value between [0, 1]"""
        self.ensure_one()
        return sum(job.progress for job in self.job_ids) / len(self.job_ids)

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        assert not sessions.job_ids

        for session in sessions:
            session.instantiate()

        return sessions

    @api.private
    def instantiate(self):
        """Create new jobs to be run from the session's blueprint."""
        self.ensure_one()
        assert self.blueprint_id

        if self.job_ids:
            return  # Session already has jobs -> do nothing

        scaling_factor = self.scaling_factor or 1
        vals_list = []
        write_target_counts = defaultdict(lambda: defaultdict(int))  # {ref | None: {model_name: count}}
        for index, model in enumerate(self.blueprint_id.definition):
            model_name = model['name']
            ref, _, ref_relation = (part or None for part in model.get('ref', '').partition('.'))
            vals = {
                'model_name': model_name,
                'instructions': model['fields'],
                'session_id': self.id,
                'seed': derive_seed_from(self.seed, index),
            }
            if 'count' in model:
                factor = scaling_factor if model.get('scale', True) else 1
                vals['record_count'] = math.floor(model['count'] * factor)

            vals.update(**{k: v for k, v in model.items() if k in ('type', 'ref', 'parallel', 'context')})

            defaults = self.env['populate.job'].default_get(['type', 'record_count'])
            is_create = vals.get('type', defaults['type']) == 'create'

            if is_create:
                write_target_counts[ref][model_name] += vals.get('record_count', defaults['record_count'])
            else:
                # Compute write job record_count:
                # - with 'ref': count from the matching 'create' job
                # - without 'ref': existing DB records + all preceding 'create' jobs for this model
                if ref:
                    assert ref in write_target_counts, f"Create 'refs' should be present before its' writes, missing: {ref}"
                    if ref_relation:
                        # The count of the corecords is unknown at creation time.
                        vals['record_count'] = None
                    else:
                        vals['record_count'] = write_target_counts[ref][model_name]
                else:
                    existing = self.env[model_name].with_context(active_test=False).search_count([])
                    from_creates = write_target_counts[None][model_name]
                    total = existing + from_creates
                    if total > 0:
                        vals['record_count'] = total

            vals_list.append(vals)

        jobs = self.env['populate.job'].create(vals_list)
        jobs.create_subjobs()

    @api.private
    def start(self):
        # We do not allow starting multiple sessions at once
        self.ensure_one()
        if self.is_done:
            raise UserError(self.env._(
                "The session %(session_id)s is already done. Create a new session.",
                session_id=self.id,
            ))

        try:
            # Prevent concurrent execution of the same session
            self.lock_for_update()

            assert self.job_ids, "A created session should have jobs instantiated"

            if self.is_parallel:
                if not has_platform_enabled_multiprocessing():
                    raise RuntimeError(self.env._(
                        "The multiprocessing feature of the populate module has been disabled at the platform level.",
                    ))
                executor = ParallelExecutor(self)
            else:
                executor = SequentialExecutor(self)

            with executor:
                executor.execute(self.pending_jobs)

        except LockError as exc:
            raise UserError(self.env._("Session %(session_id)s is already running.", session_id=self.id)) from exc


class JobExecutor(ABC):
    """
    Abstract base class for job execution strategies.

    Selects the appropriate concrete executor based on the session configuration.
    Use as a context manager to get a ready-to-use executor::

        with JobExecutor.from_session(session) as executor:
            executor.execute(session.pending_jobs)
    """

    def __init__(self, session: Session) -> Self:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    @abstractmethod
    def execute(self, jobs: Job):
        """Execute a collection of jobs following the JobExecutor's strategy"""
        ...

    @staticmethod
    def _execute_with_retry(job: Job):
        """
        Execute a single job, with a retry mechanism on extended retrying conditions.

        For the SequentialExecutor, retrying is necessary for potential complex multi-field constraints
        that cannot be avoided with parameters in a blueprint.
        For the ParallelExecutor, retrying is a must for multi-worker serialization issues,
        in addition to the above-mentioned issues.
        """
        seed = job.seed
        retry_count = 0

        def execute_job():
            """
            Small wrapper to retry on additional database exceptions.

            Usually these exceptions are due to a user error,
            but in the context of populating data,
            they're due to randomness, so we want to retry on them
            instead of failing the populate session.
            """
            nonlocal seed, retry_count
            try:
                job.execute(seed=seed)
            except PG_EXCEPTIONS_TO_RETRY as exc:
                # Re-roll the seed in case of a violation
                # to avoid re-generating the same values,
                # leading to the same violation.
                seed = derive_seed_from(seed, retry_count)
                retry_count += 1

                error = psycopg2.errorcodes.lookup(exc.pgcode)

                msg = None
                if isinstance(exc, CheckViolation | ExclusionViolation):
                    msg = job.env._("Adapt the generator parameter to generate values within the constraint")
                if isinstance(exc, NotNullViolation):
                    msg = job.env._("The field is implicitly required, consider adding `null_frac=0`")
                if isinstance(exc, UniqueViolation):
                    msg = job.env._("Consider using a generator (or combination of) that produces more varied values")

                raise ConcurrencyError(f"{error} ({msg})" if msg else error) from exc

        retrying(execute_job, job.env)


class SequentialExecutor(JobExecutor):
    """
    Executes jobs one at a time in the current process.

    Jobs are run sequentially in the order they are provided.
    """

    def execute(self, jobs: Job):
        for job in jobs:
            self._execute_with_retry(job)


class ParallelExecutor(JobExecutor):
    """
    Executes jobs using a pool of worker sub-processes via ``ProcessPoolExecutor``.

    Parallel execution is only applied to jobs that have child subjobs *and* have
    ``parallel=True``; all other jobs fall back to in-process sequential execution.
    """

    def __init__(self, session: Session):
        super().__init__(session)
        self.dbname = session.env.cr.dbname
        assert session.worker_count > 1
        self.worker_count = session.worker_count
        self.pool: ProcessPoolExecutor | None = None
        self._config = dict(config.options)

    def __getstate__(self):
        state = self.__dict__.copy()
        # `ProcessPoolExecutor` cannot be pickled
        # due to an internal thread.lock.
        # A worker doesn't need the pool anyway.
        state['pool'] = None
        return state

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.stop()

    def _worker_init(self):
        # Only 'spawn' is supported. With 'fork', the child inherits the
        # parent's PostgreSQL connection pools (shared socket fds), and
        # psycopg2 offers no way to cleanly detach without sending a
        # termination message that would corrupt the parent's connections.
        assert mp.get_start_method() == 'spawn'

        # SIGINT is handled by the parent process; subprocesses should exit immediately.
        # Use os._exit() instead of sys.exit() to avoid raising SystemExit,
        # which ProcessPoolExecutor's internals would catch, allowing the worker
        # to continue processing queued tasks. We want to prevent this since
        # abruptly terminated jobs can be resumed later anyway.
        signal.signal(signal.SIGINT, lambda *_: os._exit(0))

        # Initialize addons path to ensure all installed modules
        # are discovered when loading the Registry.
        config.options.update(self._config)
        initialize_sys_path()
        init_logger()

        with mute_logger('odoo.registry', 'odoo.modules.loading'):
            Registry(self.dbname)

        _logger.info("Worker (%s) alive", os.getpid())

    def _worker_execute(self, job_id: int, context: dict):
        registry = Registry(self.dbname)
        with registry.cursor() as cr:
            uid = context.setdefault('uid', SUPERUSER_ID)
            env = api.Environment(cr, uid, context)
            job = env['populate.job'].browse(job_id)

            assert job.exists()

            if job.context:
                job = job.with_context(job.context)

            self._execute_with_retry(job)

    def start(self):
        _logger.info(
            "Creating worker pool with %d processes for database '%s'",
            self.worker_count,
            self.dbname,
        )
        self.pool = ProcessPoolExecutor(
            max_workers=self.worker_count,
            initializer=self._worker_init,
            mp_context=mp.get_context('spawn'),
        )
        # Eagerly spawn all workers at the beginning.
        # By default, they are lazily created only on the first jobs submitted.
        # There is no API exposed for this, so we submit dummy jobs.
        list(self.pool.map(bool, range(self.worker_count)))

    def stop(self):
        if self.pool:
            _logger.info("Shutting down worker pool...")
            self.pool.shutdown(wait=True, cancel_futures=True)

    def execute(self, jobs: Job):
        for job in jobs:
            if job.child_ids and job.parallel:
                with job.execution_scope():
                    context = dict(job.env.context)
                    futures = {
                        self.pool.submit(
                            self._worker_execute, subjob.id, context,
                        ): subjob
                        for subjob in job.pending_subjobs
                    }

                    failures = []
                    for future in as_completed(futures):
                        subjob = futures[future]
                        try:
                            future.result()
                        except KeyboardInterrupt:
                            raise  # Will be caught at CLI level
                        except Exception as exc:  # noqa: BLE001
                            exc.add_note(job.env._("in Job %s", subjob.parent_path[:-1]))
                            failures.append((subjob, exc))

                    if failures:
                        raise ExceptionGroup(
                            job.env._("%(count)s parallel job(s) failed", count=len(failures)),
                            [exc for _, exc in failures],
                        )
            else:
                self._execute_with_retry(job)
