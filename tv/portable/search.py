
import item
import re

quotekiller = re.compile(r'(?<!\\)"')
slashkiller = re.compile(r'\\.')

searchObjects = {}

def match (searchString, comparisons):
    if not searchObjects.has_key(searchString):
        searchObjects[searchString] = BooleanSearch(searchString)
    return searchObjects[searchString].match(comparisons)

class BooleanSearch:
    def __init__ (self, string):
        self.string = string
        self.parse_string()

    def parse_string(self):
        inquote = False
        i = 0
        while i < len (self.string) and self.string[i] == ' ':
            i += 1
        laststart = i
        self.rules = []
        while (i < len(self.string)):
            i = laststart
            while (i < len(self.string)):
                if self.string[i] == '"':
                    inquote = not inquote
                if not inquote and self.string[i] == ' ':
                    break
                if self.string[i] == '\\':
                    i += 1
                i += 1
            if inquote:
                self.rules.append(self.process(self.string[laststart:]))
            else:
                self.rules.append(self.process(self.string[laststart:i]))
            while i < len (self.string) and self.string[i] == ' ':
                i += 1
            laststart = i

    def process (self, substring):
        positive = True
        if substring[0] == '-':
            substring = substring[1:]
            positive = False
        substring = quotekiller.sub("", substring)
        substring = slashkiller.sub(lambda x: x.group(0)[1], substring)
        print substring
        return [positive, substring]

    def match (self, comparisons):
        for rule in self.rules:
            matched = False
            for comparison in comparisons:
                if rule[1] in comparison:
                    matched = True
                    break
            if rule[0] != matched:
                return False
        return True

#        r'(([^" ]\"|"([^"]|\")*")*)'

    def as_string(self):
        return self.string
