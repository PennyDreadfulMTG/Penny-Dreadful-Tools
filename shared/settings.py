import ast
from contextlib import contextmanager
import inspect
import json
import os
from typing import Any, Dict, Optional, TypeVar, Generic, List, Union, Generator
from shared.pd_exception import InvalidArgumentException, InvalidDataException

SETTINGS = {}
CONFIGURABLE_NAMES = []
CONFIG: Dict[str, Any] = {}
NS_CONFIG: Dict[str, Any] = {}

T = TypeVar('T')
U = TypeVar('U')

ADDITIONAL_FILES = []
LOADED_FILES = set()

if os.path.exists('configs'):
    os.mkdir('configs')

@contextmanager
def with_config_file(namespace: Any) -> Generator[None, None, None]:
    filename = os.path.join('configs', f'{namespace}.config.json')
    if filename not in LOADED_FILES:
        LOADED_FILES.add(filename)
        try:
            with open(filename) as f:
                print(f'Loaded {filename}')
                cfg = json.load(f)
                for k, v in cfg.items():
                    NS_CONFIG[f'{filename}_{k}'] = v
        except FileNotFoundError:
            pass
    ADDITIONAL_FILES.append(filename)
    yield
    assert ADDITIONAL_FILES.pop() == filename

class Setting(Generic[T]):
    def __init__(self, key: str, default_value: T, configurable: bool = False, doc: str = None) -> None:
        self.key = key
        self.default_value = default_value
        self.configurable = configurable
        if doc is not None:
            self.__doc__ = doc
        if configurable:
            CONFIGURABLE_NAMES.append(key)
        SETTINGS[key] = self

    def get(self) -> T:
        for cat in ADDITIONAL_FILES:
            key = f'{cat}_{self.key}'
            if key in NS_CONFIG:
                return NS_CONFIG[key]

        key = self.key
        if key in CONFIG:
            return CONFIG[key]

        try:
            cfg = json.load(open('config.json'))
        except FileNotFoundError:
            cfg = {}
        if key in os.environ:
            cfg[key] = os.environ[key]
            print('CONFIG: {0}={1}'.format(key, cfg[key]))
            return cfg[key]
        if key in cfg:
            CONFIG.update(cfg)
            return cfg[key]

        # Lock in the default value if we use it.
        cfg[key] = self.default_value

        if inspect.isfunction(cfg[key]):  # If default value is a function, call it.
            cfg[key] = cfg[key]()

        print('CONFIG: {0}={1}'.format(key, cfg[key]))
        fh = open('config.json', 'w')
        fh.write(json.dumps(cfg, indent=4, sort_keys=True))
        return cfg[key]

    def set(self, value: T) -> T:
        filename = 'config.json'
        if ADDITIONAL_FILES:
            filename = ADDITIONAL_FILES[-1]
            fullkey = f'{filename}_{self.key}'
            NS_CONFIG[fullkey] = value
        else:
            CONFIG[self.key] = value
            fullkey = self.key

        try:
            cfg = json.load(open(filename))
        except FileNotFoundError:
            cfg = {}

        if isinstance(value, set):
            cfg[self.key] = list(value)
        else:
            cfg[self.key] = value

        print('CONFIG: {0}={1}'.format(fullkey, cfg[self.key]))
        fh = open(filename, 'w')
        fh.write(json.dumps(cfg, indent=4, sort_keys=True))
        return value


class BoolSetting(Setting[bool]):
    @property
    def value(self) -> bool:
        val = self.get()
        if val is None:
            raise fail(self.key, val, bool)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            # required so that we can pass bool-values in environment variables
            if val.lower() in ['true', 'yes', '1']:
                val = 'True'
            if val.lower() in ['false', 'no', '0']:
                val = 'False'
            val2 = ast.literal_eval(val)
            if isinstance(val2, bool):
                CONFIG[self.key] = val2
                return CONFIG[self.key]
        raise fail(self.key, val, bool)

    @value.setter
    def value(self, value: bool) -> bool:
        return self.set(value)


class StrSetting(Setting[str]):
    pass


class OptionalStrSetting(Setting[Optional[str]]):
    pass

class ListSetting(Setting[List[U]]):
    pass

def fail(key: str, val: Any, expected_type: type) -> InvalidDataException:
    return InvalidDataException('Expected a {expected_type} for {key}, got `{val}` ({actual_type})'.format(expected_type=expected_type, key=key, val=val, actual_type=type(val)))
