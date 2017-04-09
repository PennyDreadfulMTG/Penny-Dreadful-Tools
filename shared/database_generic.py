class GenericDatabase:

    def execute(self, sql, args=None):
        raise NotImplementedError()

    def value(self, sql, args=None, default=None, fail_on_missing=False):
        raise NotImplementedError()

    def values(self, sql, args=None):
        rs = self.execute(sql, args)
        return [list(row.values())[0] for row in rs]

    def insert(self, sql, args=None):
        self.execute(sql, args)
        return self.value('SELECT last_insert_rowid()')
