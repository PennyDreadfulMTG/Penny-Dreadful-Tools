from typing import List, Union

from find.tokens import Token


class Expression:
    def __init__(self, tokens: List[Union['Expression', Token]]) -> None:
        self.__tokens = tokens

    def tokens(self) -> List[Union['Expression', Token]]:
        return self.__tokens

    def __str__(self) -> str:
        return str(self.tokens())
