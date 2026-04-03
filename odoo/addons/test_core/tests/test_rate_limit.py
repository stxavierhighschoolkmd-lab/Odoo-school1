# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestRateLimit(TransactionCase):
    """Test the core rate limiting mechanism provided by `rate.limit.log`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.RateLimitLog = cls.env['test.rate.limit.log'].sudo()

    def test_check_rate_limit_allows_and_blocks(self):
        """Should enforce limits per (scope, key) and not affect other keys or scopes."""
        self.assertTrue(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
        self.assertTrue(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
        self.assertFalse(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
        self.assertTrue(self.RateLimitLog._check_rate_limit(scope='login', key='user_2'))
        self.assertTrue(self.RateLimitLog._check_rate_limit(scope='signup', key='user_1'))

    def test_check_rate_limit_no_log_on_block(self):
        """Should not create a new log entry when a request is rate limited."""
        self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
        self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
        count_before = self.RateLimitLog.search_count([('scope', '=', 'login')])
        self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
        count_after = self.RateLimitLog.search_count([('scope', '=', 'login')])
        self.assertEqual(count_before, count_after)

    def test_check_rate_limit_creates_log_on_allow(self):
        """Should create a new log entry when a request is allowed."""
        count_before = self.RateLimitLog.search_count([])
        self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
        count_after = self.RateLimitLog.search_count([])
        self.assertEqual(count_after, count_before + 1)

    def test_check_rate_limit_missing_field_raises(self):
        """Should raise an error when required rule fields are missing."""
        with self.assertRaises(AssertionError):
            self.RateLimitLog._check_rate_limit(scope='login')

    def test_purge_rate_limit_logs_behavior(self):
        """Should remove matching entries, reset limits, and keep other records intact."""
        self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
        self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
        self.RateLimitLog._check_rate_limit(scope='login', key='user_2')
        self.assertFalse(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
        self.RateLimitLog._purge_rate_limit_logs(scope='login', key='user_1')
        self.assertTrue(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
        self.assertEqual(self.RateLimitLog.search_count([
            ('scope', '=', 'login'), ('key', '=', 'user_2'),
        ]), 1)

    def test_check_rate_limit_interval_expiry(self):
        """Should ignore records outside the interval window and only count recent ones."""
        INTERVAL = 3600
        old_date = datetime.now() - timedelta(seconds=INTERVAL + 1)
        with (
            freeze_time(old_date),
            patch.object(self.env.cr, "_now", old_date),
        ):
            self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
            self.RateLimitLog._check_rate_limit(scope='login', key='user_1')
        self.assertTrue(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
        self.assertTrue(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
        self.assertFalse(self.RateLimitLog._check_rate_limit(scope='login', key='user_1'))
