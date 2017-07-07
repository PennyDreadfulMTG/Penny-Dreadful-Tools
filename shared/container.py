from munch import Munch

# Slight variation on Munch that will put keys containing periods into a nested structure.
#
#     Container({'x.y': 7}) -> {'x': {'y': 7}}
#
# This is useful for giving depth to an object selected in a flat fashion out of the database.
# This in turn is useful for looping over similar subsets of the data in Mustache templates.
class Container(Munch):
    def __init__(self, args=None):
        if args is None:
            args = {}
        new_args = {}
        for k, v in args.items():
            if '.' in k:
                k1, k2 = k.split('.')
                new_args[k1] = new_args.get(k1, Container())
                new_args[k1][k2] = v
            else:
                new_args[k] = v
        print(new_args)
        super().__init__(new_args)
