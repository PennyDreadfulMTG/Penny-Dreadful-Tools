from shared.pd_exception import DoesNotExistException, TooManyItemsException


def exactly_one(l):
    if len(l) > 1:
        raise TooManyItemsException('Found {n} items when expecing 1 in `{l}`.'.format(n=len(l), l=l))
    try:
        return l[0]
    except IndexError:
        raise DoesNotExistException('Did not find an item when expecting one.')

def at_most_one(l):
    if len(l) > 1:
        raise TooManyItemsException('Found {n} items when expecing at most 1 in `{l}`.'.format(n=len(l), l=l))
    elif len(l) == 0:
        return None
    else:
        return l[0]
