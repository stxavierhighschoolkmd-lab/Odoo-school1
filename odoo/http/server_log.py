import functools
import logging
import pprint
import threading
import typing
from http import HTTPStatus

from odoo.netsvc import (
    BOLD_SEQ,
    COLOR_PATTERN,
    CYAN,
    DEFAULT,
    GREEN,
    MAGENTA,
    RED,
    RESET_SEQ,
    YELLOW,
    ColoredFormatter,
)
from odoo.tools import real_time

from .requestlib import DEFAULT_MAX_CONTENT_LENGTH, MAX_FORM_SIZE

__all__ = (
    'http_log',
    'setup_perf_meters',
)

_HTTP_FORMAT = '%(remote_addr)s %(http_request_line)s %(http_response_status)s %(http_response_body)s %(query_count)s %(query_time)s %(remaining_time)s %(cursor_mode)s'
_HTTP_FORMAT_HEADERS = _HTTP_FORMAT + "\n%(http_headers)s"


def setup_perf_meters():
    """ Reset various thread-local meters. """
    t0 = real_time()
    current_thread = threading.current_thread()
    current_thread.query_count = 0
    current_thread.query_time = 0
    current_thread.perf_t0 = t0
    current_thread.cursor_mode = None
    current_thread.rpc_model_method = None


def http_log(level, msg, *args, extra={}, **kwargs):
    """
    Emit a message on the ``odoo.http.server`` logger.

    The ``extra`` are modified to include the http informations (client
    ip address, request line, response status code and response body
    length) and the perf meters (query count, query time, remaining
    time, cursor mode).
    """
    if not _logger.isEnabledFor(level):
        return

    extra = _HTTP_EXTRA | _perf_meters() | extra

    extra_log = extra.copy()  # keep "extra" color free
    if _has_color():
        extra_log['query_count'] = _colorize_query_count(extra_log['query_count'])
        extra_log['query_time'] = _colorize_query_time(extra_log['query_time'])
        extra_log['remaining_time'] = _colorize_remaining_time(extra_log['remaining_time'])
        if extra_log['http_response_status'] != '-':
            extra_log['http_request_line'] = _colorize_request_line(
                extra_log['http_request_line'], extra_log['http_response_status'])
        if extra_log['cursor_mode'] != '-':
            extra_log['cursor_mode'] = _colorize_cursor_mode(extra_log['cursor_mode'])
        extra_log['http_response_body'] = _colorize_body_length(extra_log['http_response_body'])
    else:
        extra_log['query_time'] = round(extra_log['query_time'], 3)
        extra_log['remaining_time'] = round(extra_log['remaining_time'], 3)

    if extra_log.get('http_headers') and _logger_headers.isEnabledFor(logging.DEBUG):
        extra_log['http_headers'] = pprint.pformat(list(extra_log['http_headers']))
        msg += _HTTP_FORMAT_HEADERS % extra_log
    else:
        msg += _HTTP_FORMAT % extra_log

    _logger.log(level, msg, *args, extra=extra, **kwargs)


_HTTP_EXTRA = {
    'remote_addr': '-',
    'http_request_line': '"- - -"',
    'http_response_status': '-',
    'http_response_body': '-',
}


def _perf_meters():
    current_thread = threading.current_thread()
    now = real_time()
    return {
        'query_count': current_thread.query_count,
        'query_time': current_thread.query_time,
        'remaining_time': now - current_thread.perf_t0 - current_thread.query_time,
        'cursor_mode': current_thread.cursor_mode or '-',
    }


def _colorize_request_line(request_line: str, status: int) -> str:
    """
    Return ``request_line`` as a colored string depending on ``status``.
    """
    if status == 200:
        return request_line
    status = HTTPStatus(status)
    if status == HTTPStatus.NOT_MODIFIED:
        return COLOR_PATTERN % (30 + CYAN, 40 + DEFAULT, request_line)
    if status == HTTPStatus.NOT_FOUND:
        return COLOR_PATTERN % (30 + YELLOW, 40 + DEFAULT, request_line)
    if status.is_informational or status.is_success:
        return f'{BOLD_SEQ}{request_line}{RESET_SEQ}'
    if status.is_redirection:
        return COLOR_PATTERN % (30 + GREEN, 40 + DEFAULT, request_line)
    if status.is_client_error:
        return BOLD_SEQ + COLOR_PATTERN % (30 + RED, 40 + DEFAULT, request_line)
    # status.is_server_error, and bad status codes
    return BOLD_SEQ + COLOR_PATTERN % (30 + MAGENTA, 40 + DEFAULT, request_line)


def _colorize_range(value: float, format: str, low: float, high: float) -> str:
    """
    Return ``value`` as a colored string:

    * ``high < value``: red
    * ``low < value < high``: yellow
    * ``value < low``: no color
    """
    if value > high:
        return COLOR_PATTERN % (30 + RED, 40 + DEFAULT, format % value)
    if value > low:
        return COLOR_PATTERN % (30 + YELLOW, 40 + DEFAULT, format % value)
    return format % value


_colorize_query_count = functools.partial(_colorize_range, format='%d', low=100, high=1000)
_colorize_query_time = functools.partial(_colorize_range, format='%.3f', low=.1, high=3)
_colorize_remaining_time = functools.partial(_colorize_range, format='%.3f', low=1, high=5)


def _colorize_body_length(body_length: int | typing.Literal['-', 'stream']) -> str:
    """
    Return ``body_length`` as a colored string.

    It is colored in red when the length is higher than the maximum body
    length we accept (128 MiB). It is colored in yellow when we don't
    know the length (stream) or when the length is higher than the
    largest form we accept (10 MiB). Otherwise the length is returned
    with no color.
    """
    if body_length == '-':
        return body_length
    if body_length == 'stream':
        return COLOR_PATTERN % (30 + YELLOW, 40 + DEFAULT, body_length)
    return _colorize_range(int(body_length), '%s', low=MAX_FORM_SIZE, high=DEFAULT_MAX_CONTENT_LENGTH)


def _colorize_cursor_mode(cursor_mode: typing.Literal['ro', 'rw', 'ro->rw']) -> str:
    """
    Return ``cursor_mode`` as a colored string.

    * Requests read-only: green.
    * Requests read/write: yellow.
    * Requests that were attempted with a read-only cursor, but failed
      and had to be repeated using a read/write one: red.
    """
    cursor_mode_color = (
             RED    if cursor_mode == 'ro->rw'  # noqa: E272
        else YELLOW if cursor_mode == 'rw'
        else GREEN
    )
    return COLOR_PATTERN % (30 + cursor_mode_color, 40 + DEFAULT, cursor_mode)


@functools.cache
def _has_color():
    """ Determine if the root logger supports colors. """
    return any(
        isinstance(handler.formatter, ColoredFormatter)
        for handler
        in logging.root.handlers
    )


_logger = logging.getLogger('odoo.http.server')
_logger_headers = _logger.getChild('headers')
_logger_headers.setLevel(logging.WARNING)  # disabled by default
