import logging
from collections.abc import Callable

import sentry_sdk
from pyparsing import Any
from sentry_sdk import crons
from sentry_sdk.integrations.flask import FlaskIntegration

from shared import configuration


def sentry_filter(event, hint):  # type: ignore
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        if isinstance(exc_value, OSError):
            return None
    return event


def init() -> None:
    sentry_token = configuration.get_optional_str('sentry_token')
    if sentry_token:
        try:
            sentry_sdk.init(
                dsn=sentry_token,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.001,
                before_send=sentry_filter,
            )
        except Exception as c:
            logging.error(c)

def monitor(task_name: str) -> Callable[..., Any]:
    return crons.monitor(configuration.get_optional_str('sentry_monitorslug_' + task_name))
