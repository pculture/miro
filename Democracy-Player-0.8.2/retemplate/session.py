class Session:
    def __init__(self, encodeAndQuoteFunc):
        self.header = ""
        self.body = ""
        self.footer = ""
        self.funcCounter = 0
        self.classCounter = 0
        self.encodeAndQuoteFunc = encodeAndQuoteFunc

    def writeToHeader(self, s):
        self.header += s

    def writeToBody(self, s):
        self.body += s

    def writeToFooter(self, s):
        self.footer += s

    def encodeAndQuote(self, s):
        return self.encodeAndQuoteFunc(s)

    def encodeAndQuoteName(self):
        return self.encodeAndQuoteFunc.__name__

    def nextFuncName(self):
        self.funcCounter += 1
        return "_f%d" % (self.funcCounter, )

    def nextClassName(self):
        self.classCounter += 1
        return "_c%d" % (self.classCounter, )
