from typing import Optional, Sequence, TypeVar

from shared.pd_exception import DoesNotExistException, TooManyItemsException

T = TypeVar('T')


def exactly_one(sequence: Sequence[T], noun: str = 'items') -> T:
    if len(sequence) > 1:
        raise TooManyItemsException('Found {n} {noun} when expecting 1 in `{l}`.'.format(n=len(sequence), l=sequence, noun=noun))
    try:
        return sequence[0]
    except IndexError as e:
        raise DoesNotExistException('Did not find an item when expecting one.') from e

def at_most_one(sequence: Sequence[T], noun: str = 'items') -> Optional[T]:
    if len(sequence) > 1:
        raise TooManyItemsException('Found {n} {noun} when expecting at most 1 in `{l}`.'.format(n=len(sequence), l=sequence, noun=noun))
    if len(sequence) == 0:
        return None
    return sequence[0]
