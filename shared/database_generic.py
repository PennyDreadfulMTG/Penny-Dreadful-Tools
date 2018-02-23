from typing import Any, List

from shared.pd_exception import DatabaseException


class GenericDatabase:

    def execute(self, sql: str, args: Any = None) -> List[Any]:
        raise NotImplementedError()

    def value(self, sql: str, args: Any = None, default: Any = None, fail_on_missing: bool = False) -> Any:
        try:
            return self.values(sql, args)[0]
        except IndexError:
            if fail_on_missing:
                raise DatabaseException('Failed to get a value from `{sql}`'.format(sql=sql))
            else:
                return default

    def values(self, sql: str, args: Any = None) -> List[Any]:
        rs = self.execute(sql, args)
        return [list(row.values())[0] for row in rs]

    def insert(self, sql: str, args: Any = None) -> int:
        raise NotImplementedError()

    # pylint: disable=no-self-use
    def is_mysql(self) -> bool:
        return False

    # pylint: disable=no-self-use
    def is_sqlite(self) -> bool:
        return False

    # pylint: disable=no-self-use
    def supports_lock(self) -> bool:
        return False
