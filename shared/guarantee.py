from typing import Optional, Sequence, TypeVar

from shared.pd_exception import DoesNotExistException, TooManyItemsException

T = TypeVar('T')


def exactly_one(l: Sequence[T], noun: str = 'items') -> T:
    if len(l) > 1:
        raise TooManyItemsException('Found {n} {noun} when expecting 1 in `{l}`.'.format(n=len(l), l=l, noun=noun))
    try:
        return l[0]
    except IndexError as e:
        raise DoesNotExistException('Did not find an item when expecting one.') from e

def at_most_one(l: Sequence[T], noun: str = 'items') -> Optional[T]:
    if len(l) > 1:
        raise TooManyItemsException('Found {n} {noun} when expecting at most 1 in `{l}`.'.format(n=len(l), l=l, noun=noun))
    if len(l) == 0:
        return None
    return l[0]
