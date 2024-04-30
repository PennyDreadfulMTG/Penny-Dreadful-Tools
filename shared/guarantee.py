from collections.abc import Sequence
from typing import TypeVar

from shared.pd_exception import DoesNotExistException, TooManyItemsException

T = TypeVar('T')


def exactly_one(sequence: Sequence[T], noun: str = 'items') -> T:
    if len(sequence) > 1:
        raise TooManyItemsException(f'Found {len(sequence)} {noun} when expecting 1 in `{sequence}`.')
    try:
        return sequence[0]
    except IndexError as e:
        raise DoesNotExistException('Did not find an item when expecting one.') from e

def at_most_one(sequence: Sequence[T], noun: str = 'items') -> T | None:
    if len(sequence) > 1:
        raise TooManyItemsException(f'Found {len(sequence)} {noun} when expecting at most 1 in `{sequence}`.')
    if len(sequence) == 0:
        return None
    return sequence[0]
