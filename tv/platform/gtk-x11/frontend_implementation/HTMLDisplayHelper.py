# Decorator to make using execAfterLoad easier
def deferUntilAfterLoad(func):
    def runFunc(*args, **kwargs):
        func(*args, **kwargs)
    def schedFunc(self, *args, **kwargs):
        rf = lambda: runFunc(self, *args, **kwargs)
        self.execAfterLoad(rf)
    return schedFunc
