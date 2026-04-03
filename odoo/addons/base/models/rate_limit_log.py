# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models


class RateLimitLog(models.AbstractModel):
    _name = 'rate.limit.log'
    _description = 'Rate Limit Log'

    def _get_rate_limit_rules(self):
        """
        Return rate limit rules for this model.

        Override this method in concrete models to define the rate limit
        behavior.

        Performance note:
        Models implementing rate limits should create a composite index for each
        rule using the rule fields together with ``create_date``.

        :returns: A list of dictionaries defining rate limit rules.
        :rtype: list[dict]

        Each rule dictionary contains:

        - ``fields``: List of field names forming the compound key.
        - ``limit``: Maximum allowed count within the interval.
        - ``interval``: Time window in seconds.

        Example::

            [
                {'fields': ['ip'], 'limit': 5, 'interval': 3600},
                {'fields': ['email'], 'limit': 3, 'interval': 3600},
            ]

        """
        raise NotImplementedError()

    @api.model
    def _check_rate_limit(self, **field_values):
        """
        Check rate limits and log the attempt if allowed.

        For each rule returned by ``_get_rate_limit_rules()``, this method
        counts existing log entries matching the rule fields within the
        configured time window. If any rule limit is exceeded, the method
        returns ``False`` and no log entry is created. Otherwise, a new log
        entry is created and the method returns ``True``.

        :param dict field_values: Field name and value pairs used to check and log.
        :returns: ``True`` if the action is allowed, ``False`` if rate limited.
        :rtype: bool

        """
        rules = self._get_rate_limit_rules()
        for rule in rules:
            domain = [
                ('create_date', '>=', fields.Datetime.now() - timedelta(seconds=rule['interval'])),
            ]
            for field_name in rule['fields']:
                assert field_name in field_values, f"Missing '{field_name}' required by the rate limit rule"
                domain.append((field_name, '=', field_values[field_name]))
            if self.search_count(domain) >= rule['limit']:
                return False
        self.create(field_values)
        return True

    @api.model
    def _purge_rate_limit_logs(self, **field_values):
        """
        Delete all rate limit log entries matching the given field values.

        This is used to reset rate limits after a successful action (for example,
        a successful TOTP verification clears the ``code_check`` counter).

        :param dict field_values: Field name and value pairs to match for deletion.
        :returns: None
        :rtype: None

        """
        domain = [(key, '=', value) for key, value in field_values.items()]
        self.search(domain).unlink()
