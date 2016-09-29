class Expression:
    def __init__(self, tokens):
        self.__tokens = tokens

    def tokens(self):
        return self.__tokens

    def __str__(self):
        return str(self.tokens())
