import logging
from enum import Enum

_logger = logging.getLogger(__name__)


class MailDataTarget(Enum):
    ALL = "all"
    LOGGED_IN = "logged_in"
    INTERNAL = "internal"


class MailDataRegistry(dict):
    def __init__(self):
        super().__init__()
        for target in MailDataTarget:
            self[target] = {}

    def add(self, name, func_name, target=MailDataTarget.ALL):
        if target not in MailDataTarget:
            raise ValueError(
                f"Invalid target {target} for mail data handler {name} with function {func_name}"
            )
        if name in self[target] and self[target][name] != func_name:
            raise ValueError(
                f"Mail data handler {name} already registered for target {target}"
                f"with a different function: {self[target][name]} vs {func_name}"
            )
        self[target][name] = func_name

    def _execute(self, controller, name, store, params):
        if not any(name in self[target] for target in MailDataTarget):
            _logger.warning("No mail data handler registered for %s", name)
            return
        handlers = []
        user = controller.env.user
        if name in self[MailDataTarget.ALL]:
            handlers.append(self[MailDataTarget.ALL][name])
        if not user._is_public() and name in self[MailDataTarget.LOGGED_IN]:
            handlers.append(self[MailDataTarget.LOGGED_IN][name])
        if user._is_internal() and name in self[MailDataTarget.INTERNAL]:
            handlers.append(self[MailDataTarget.INTERNAL][name])
        for handler_name in handlers:
            handler = getattr(controller, handler_name)
            if params is None:
                handler(store)
            elif isinstance(params, dict):
                handler(store, **params)
            elif isinstance(params, list):
                handler(store, *params)
            else:
                handler(store, params)

    def execute_for_user(self, controller, store, fetch_params):
        for fetch_param in fetch_params:
            name, params, data_id = (
                (fetch_param, None, None)
                if isinstance(fetch_param, str)
                else (fetch_param + [None, None])[:3]
            )
            store.data_id = data_id
            self._execute(controller, name, store, params)


mail_data_registry = MailDataRegistry()


def mail_data_handler(name=None, target: MailDataTarget = MailDataTarget.INTERNAL):

    def mail_data_handler__decorator(func):
        if name:
            mail_data_registry.add(name, func.__name__, target=target)
        return func

    return mail_data_handler__decorator
