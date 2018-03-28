from .container import Container

class LazyContainer(Container):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.__parents = []

    def lazy_update(self, obj):
        self.__parents.append(obj)

    def __getattr__(self, k):
        try:
            return super().__getattr__(k)
        except AttributeError:
            return self.fill(k)

    def __getitem__(self, k):
        try:
            return super().__getitem__(k)
        except KeyError:
            return self.fill(k)

    def fill(self, k):
        for p in self.__parents:
            try:
                self[k] = p[k]
                break
            except KeyError:
                continue
        else:
            raise AttributeError(k)
        return self[k]
