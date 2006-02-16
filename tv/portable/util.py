import re

# Perform escapes needed for Javascript string contents.
def quoteJS(x):
    x = re.compile("\\\\").sub("\\\\", x)  #       \ -> \\
    x = re.compile("\"").  sub("\\\"", x)  #       " -> \"
    x = re.compile("'").   sub("\\'", x)   #       ' -> \'
    x = re.compile("\n").  sub("\\\\n", x) # newline -> \n
    x = re.compile("\r").  sub("\\\\r", x) #      CR -> \r
    return x
