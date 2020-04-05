import os
import re
from typing import Optional

from babel.messages import pofile
from babel.messages.catalog import Catalog, Message


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
    if isinstance(message.string, str):
        warning = has_missing_var(message.id, message.string)
        if warning:
            error(message, catalog, warning)
    else:
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


def has_missing_var(english: str, string: str) -> Optional[str]:
    for m in re.findall(r'\{\w+\}', english):
        if not m in string:
            return 'Variable {m} missing from translation'.format(m=m)
    nums = len(re.findall('%\\(num\\)d', english))
    if len(re.findall('%\\(num\\)d', string)) != nums:
        return 'Missing %(num)d'
    return None

def error(message: Message, catalog: Catalog, warning: str) -> None:
    print('Warning: {lang} {message} failed tests:\n... {str}\n... {warning}'.format(message=message.id, lang=catalog.locale, warning=warning, str=message.string))
    # catalog.delete(message.id)
    catalog.add(message.id, message.string, flags=['fuzzy'])
