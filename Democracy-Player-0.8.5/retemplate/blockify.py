from parse import *

class BlockNode (Node):
    def __init__(self, name):
        self.name = name
        self.children = []
        self.contents = ""
        Node.__init__(self)

    def addChild(self, n):
        self.children.append(n)

    def write(self, s):
        self.contents += s

    def dump(self, i):
        if len(self.children) == 0:
            print "%sBlock %s%s" % (" " * i, self.name, self.formals)
        else:
            print "%sBlock %s%s; referencing:" % (" " * i, self.name,
                                                  self.formals)
            for child in self.children:
                child.dump(i + 4)

    def allChildren(self):
        return self.children

def blockify(sess, nodes, formals=[]):
    out = []
    funcSoFar = []

    def spillFunc(out=out, funcSoFar=funcSoFar):
        if len(funcSoFar) != 0:
            out.append(genBlock(sess, funcSoFar, formals))
            del funcSoFar[:]

    for n in nodes:
        if isinstance(n, ConsolidatableNode):
            funcSoFar.append(n)
        else:
            spillFunc()
            blockifyReactiveNode(sess, n)
            out.append(n)

    spillFunc()
    return out

def blockifyReactiveNode(sess, n):
    if hasattr(n, 'body'):
        n.body = blockify(sess, n.body, n.formals)
    if hasattr(n, 'elseBody') and n.elseBody:
        n.elseBody = blockify(sess, n.elseBody, n.formals)

def genBlock(sess, nodes, formals):
    newNode = BlockNode(sess.nextFuncName())

    newNode.write("def %s(%s):\n" % \
                  (newNode.name,
                   ', '.join(['__parentsChildren', 'self'] + formals)))
    children = doGenBlock(sess, nodes, 4, newNode, formals)
    newNode.write("\n")
    return newNode

def doGenBlock(sess, nodes, indent, blockNode, formals):
    textSoFar = [""]
    needsPass = [True]

    def spillText(textSoFar=textSoFar, needsPass=needsPass):
        if len(textSoFar[0]) == 0:
            return
        blockNode.write("%sprint %s\n" % (" " * indent, repr(textSoFar[0])))
        textSoFar[0] = ""
        needsPass[0] = False

    for n in nodes:
        if isinstance(n, LiteralNode):
            textSoFar[0] += sess.encodeAndQuote(n.text)
            continue
        spillText()
        needsPass[0] = False

        if isinstance(n, EvaluateNode):
            blockNode.write("%sprint retemplate_lib.%s(%s)\n" % \
                            (" " * indent, 
                             sess.encodeAndQuoteName(),
                             n.expr))
            continue

        if isinstance(n, StaticNode):
            def f(nodes, indent, sess=sess, blockNode=blockNode,
                  formals=formals):
                doGenBlock(sess, nodes, indent, blockNode, formals)
            n.generate(blockNode, f, indent)
            continue

        if isinstance(n, ReactiveNode):
            blockNode.write("%s%s(%s)\n" % \
                            (" " * indent, 
                             n.getName(sess),
                             ', '.join(['__parentsChildren'] + formals)))
            blockNode.addChild(n)
            blockifyReactiveNode(sess, n)
            continue

        raise RuntimeError, "Bad node %s in doGenBlock" % n

    spillText()
    if needsPass[0]:
        # shoudn't happen?
        blockNode.write("%spass\n" % (" " * indent, ))
