import os
import re

from babel.messages import pofile
from babel.messages.catalog import Catalog, Message

from shared.pd_exception import InvalidDataException


def ad_hoc() -> None:
    for directory, _, files in os.walk(os.path.join('shared_web', 'translations')):
        for path in [os.path.join(directory, f) for f in files if os.path.splitext(f)[1] == '.po']:
            print(path)
            validate_pofile(path)


def validate_pofile(path: str) -> None:
    with open(path, mode='rb+') as f:
        catalog = pofile.read_po(f)
        messages = list(catalog)
        for message in messages:
            if message.id and message.string:
                validate_string(message, catalog)
        f.seek(0)
        f.truncate()
        pofile.write_po(f, catalog)


def validate_string(message: Message, catalog: Catalog) -> None:
    if not isinstance(message.id, (str, tuple)):
        raise InvalidDataException(f'Unexpected id type: {repr(message.id)}')

    if isinstance(message.string, str):
        warning = has_missing_var(message.id, message.string)
        if warning:
            error(message, catalog, warning)
    elif isinstance(message.string, list):
        for x in range(len(message.string)):
            s = message.string[x]
            try:
                warning = has_missing_var(message.id[x], s)
            except IndexError:
                # The russian translation has multiple variations of plural
                warning = has_missing_var(message.id[-1], s)
            if warning:
                error(message, catalog, warning)
                return
    else:
        raise InvalidDataException(f'Unexpected string type: {repr(message.string)}')


def has_missing_var(english: str | tuple, string: str) -> str | None:
    if isinstance(english, tuple):
        return None
    for m in re.findall(r'\{\w+\}', english):
        if m not in string:
            return f'Variable {m} missing from translation'
    nums = len(re.findall('%\\(num\\)d', english))
    if len(re.findall('%\\(num\\)d', string)) != nums:
        return 'Missing %(num)d'
    return None


def error(message: Message, catalog: Catalog, warning: str) -> None:
    print(f'Warning: {catalog.locale} {message.id} failed tests:\n... {message.string}\n... {warning}')
    # catalog.delete(message.id)
    catalog.add(message.id, message.string, flags=['fuzzy'])
