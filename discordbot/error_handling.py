import hashlib
import logging
import os
import re
import traceback
from logging.handlers import RotatingFileHandler

from shared import repo

LOG_FILE = os.path.abspath('discordbot.log')
MAX_PUBLIC_ERROR_LENGTH = 200


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if any(getattr(handler, '_discordbot_log', False) for handler in root_logger.handlers):
        return
    handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3)
    handler._discordbot_log = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    root_logger.addHandler(handler)


def error_code(error: Exception) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    locations = '|'.join(f'{frame.filename}:{frame.name}:{frame.lineno}' for frame in frames)
    diagnostic = getattr(error, 'diagnostic', str(error))
    fingerprint = f'{type(error).__module__}.{type(error).__qualname__}|{diagnostic}|{locations}'
    return hashlib.blake2s(fingerprint.encode(), digest_size=4).hexdigest().upper()


def public_message(error: Exception, hint: str | None = None) -> str:
    message = f'Something went wrong. Error code `{error_code(error)}`; ask a mod to look in `{_inline_code(LOG_FILE)}`.'
    hint = hint if hint is not None else _exception_hint(error)
    hint = _inline_code(_one_line(redact(hint)))
    if hint:
        hint_wrapper = ' Hint: ``.'
        available = MAX_PUBLIC_ERROR_LENGTH - len(message) - len(hint_wrapper)
        if available > 0:
            if len(hint) > available:
                hint = hint[: max(available - 1, 0)].rstrip() + '…'
            message += f' Hint: `{hint}`.'
    return message


def log_exception(error: Exception, context: str) -> None:
    formatted = redact(''.join(traceback.format_exception(type(error), error, error.__traceback__)))
    logging.error(
        '%s. Error code %s\n%s',
        context,
        error_code(error),
        formatted,
    )


def redact(text: str) -> str:
    for secret in repo.REDACTED_STRINGS:
        if secret:
            text = text.replace(secret, 'REDACTED')
    return re.sub(r'(https?://)[^/\s@]+@', r'\1REDACTED@', text)


def _one_line(text: str) -> str:
    return ' '.join(text.split())


def _inline_code(text: str) -> str:
    return text.replace('`', "'")


def _exception_hint(error: Exception) -> str:
    detail = str(error).splitlines()[0].strip()
    error_type = type(error).__name__
    return f'{error_type}: {detail}' if detail else error_type
