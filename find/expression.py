from typing import Union

from find.tokens import Token


class Expression:
    def __init__(self, tokens: list[Union['Expression', Token]]) -> None:
        self.__tokens = tokens

    def tokens(self) -> list[Union['Expression', Token]]:
        return self.__tokens

    def __str__(self) -> str:
        return str(self.tokens())

    def __repr__(self) -> str:
        return str(self)
