# NEEDS: make all block functions return the size of their expansion

# NEEDS: we're in a world of hurt on tag ID's. we need to synthesize new
# ones as part of doing a 'for' repeat -- no help for it.
#
# so.... after parsing, unparse the document, rendering the dynamic
# tags as XML. this'll need to be done for each branch of each static
# conditional (or we can transform the static conditionals too.)
# modify the parsed DOM tree, add attributes to represent dynamically
# inserted IDs, then unparse it, transforming our tags back to our
# language and generating new tags to represent the insertion of
# dynamic IDs. THEN, walk the new, parsed tree and the DOM tree in
# parallel, annotating the nodes with information about their relative
# positions.

import lex
import parse
import session
import blockify
import flatten
import computeformals
import retemplate_lib
import sys

sess = session.Session(retemplate_lib.utf8)

f = open("sample", "rt")
tokens = lex.stringToTokens(f.read())
f.close()

print "----- TOKENS"
for t in tokens:
    if type(t) == str:
        print [t]
    else:
        print t

parsed = parse.parse(sess, tokens)

print "----- PARSE TREE"
parse.dumpList(0, parsed)
print "*** Header ***"
print sess.header
print "*** Body ***"
print sess.body

computeformals.computeFormals(parsed)
print "----- TREE WITH FORMALS"
parse.dumpList(0, parsed)

topblocks = blockify.blockify(sess, parsed)
print "----- BLOCKED TREE"
parse.dumpList(0, topblocks)
print "*** Header ***"
print sess.header
print "*** Body ***"
print sess.body


flatten.flatten(sess, topblocks)
print "----- FINAL FLATTENED FILE"
sys.stdout.write(sess.header)
sys.stdout.write(sess.body)
sys.stdout.write(sess.footer)
