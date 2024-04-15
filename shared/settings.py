import ast
import inspect
import json
import os
from contextlib import contextmanager
from typing import Any, Generic, Optional, TypeVar
from collections.abc import Generator

from shared.pd_exception import InvalidDataException

SETTINGS = {}
CONFIGURABLE_NAMES = []
CONFIG: dict[str, Any] = {}
NS_CONFIG: dict[str, Any] = {}

T = TypeVar('T')
U = TypeVar('U')

ADDITIONAL_FILES = []
LOADED_FILES = set()

if not os.path.exists('configs'):
    os.mkdir('configs')

@contextmanager
def with_config_file(namespace: Any) -> Generator[None, None, None]:
    if namespace is None:
        yield
        return

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

def save_cfg(cfg: Any) -> None:
    with open('config.json', 'w') as fh:
        fh.write(json.dumps(cfg, indent=4, sort_keys=True))

class Setting(Generic[T]):
    def __init__(self, key: str, default_value: T, configurable: bool = False, doc: str | None = None) -> None:
        self.key = key
        self.default_value = default_value
        self.configurable = configurable
        if doc is not None:
            self.__doc__ = doc
        if configurable:
            CONFIGURABLE_NAMES.append(key)
        SETTINGS[key] = self

    def get(self) -> T:
        if self.configurable:
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
            if cfg.get(key, None) == os.environ[key]:
                return cfg[key]
            cfg[key] = os.environ[key]
            print(f'CONFIG: {key}={cfg[key]}')
            save_cfg(cfg)
            CONFIG.update({key: cfg[key]})
            return cfg[key]
        if key in cfg:
            CONFIG.update(cfg)
            return cfg[key]

        # Lock in the default value if we use it.
        cfg[key] = self.default_value

        if inspect.isfunction(cfg[key]):  # If default value is a function, call it.
            cfg[key] = cfg[key]()

        print(f'CONFIG: {key}={cfg[key]}')
        save_cfg(cfg)
        return cfg[key]

    def set(self, value: T) -> T:
        filename = 'config.json'
        if ADDITIONAL_FILES and self.configurable:
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

        print(f'CONFIG: {fullkey}={cfg[self.key]}')
        save_cfg(cfg)
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
    @property
    def value(self) -> str:
        val = self.get()
        if val is None:
            raise fail(self.key, val, bool)
        return val

    @value.setter
    def value(self, value: str) -> str:
        return self.set(value)


class OptionalStrSetting(Setting[Optional[str]]):
    pass

class ListSetting(Setting[list[U]]):
    pass

class IntSetting(Setting[int]):
    @property
    def value(self) -> int:
        val = self.get()
        if val is None:
            raise fail(self.key, val, int)
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            val2 = ast.literal_eval(val)
            if isinstance(val2, int):
                CONFIG[self.key] = val2
                return CONFIG[self.key]
        raise fail(self.key, val, int)

    @value.setter
    def value(self, value: int) -> int:
        return self.set(value)

def fail(key: str, val: Any, expected_type: type) -> InvalidDataException:
    return InvalidDataException(f'Expected a {expected_type} for {key}, got `{val}` ({type(val)})')
