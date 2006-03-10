import re

tagPattern = re.compile(r"<%(.*?)%>", re.DOTALL)
tagContentsPattern = re.compile(r"^\s*(\S+)\s*(.*)", re.DOTALL)

def stringToTokens(text):
    parts = tagPattern.split(text)
    #for p in parts:
    #    print "PART: %s" % [p]

    tokens = []
    if len(parts) % 2 != 1:
        raise RuntimeError, \
            "Inconceivable! The lexer array isn't the right length."

    tokens.append(parts[0])

    for i in range(0, (len(parts)-1)/2):
        contents = parts[i*2+1]
        match = tagContentsPattern.match(contents)
        if not match:
            raise ValueError, "Bad tag: '<\%%s\%>'" % contents

        tokens.append((match.group(1), match.group(2)))
        tokens.append(parts[i*2 + 2])

    return tokens
