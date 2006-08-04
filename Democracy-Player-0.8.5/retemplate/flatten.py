import blockify
import parse

def flatten(sess, nodes):
    sess.writeToBody("    def __fill(self):\n")
    sess.writeToBody(genFillFunc(sess, nodes))
    sess.writeToBody("\n")
    sess.writeToHeader("\nimport retemplate_lib\n")
    sess.writeToHeader("class Template(retemplate_lib.Template):\n")
    dumpBlockBodies(sess, nodes)

def genFillFunc(sess, nodes):
    out = ""

    for n in nodes:
        if isinstance(n, blockify.BlockNode):
            out = out + "        %s(*self.environment)\n" % (n.name,)
            for child in n.children:
                flattenNode(sess, child)
        else:
            name = flattenNode(sess, n)
            out = out + "        %s(self)\n" % (name,)

    return out

def flattenNode(sess, node):
    body = genFillFunc(sess, node.body)
    bodyName = sess.nextFuncName()
    if node.elseBody:
        elseBody = genFillFunc(sess, node.elseBody)
        elseName = sess.nextFuncName()
    else:
        elseBody = elseName = None

    name = node.getName(sess)
    sess.writeToFooter("class %s(%s):\n" % (name, node.runtimeClass))
    sess.writeToFooter("    def expression(__self)\n")
    sess.writeToFooter("        self = __self.parent\n")
    sess.writeToFooter("        return %s\n" % node.expr)
    sess.writeToFooter("    def body(self, __parentsChildren)\n")
    sess.writeToFooter("        self = self.template\n")
    sess.writeToFooter(body)
    sess.writeToFooter("    def elseBody(self, __parentsChildren)\n")
    if elseBody:
        sess.writeToFooter("        self = self.template\n")
        sess.writeToFooter(elseBody)
    else:
        sess.writeToFooter("        pass\n")
    sess.writeToFooter("\n")

    return name

def dumpBlockBodies(sess, nodes):
    if nodes == None:
        return

    for n in nodes:
        if isinstance(n, blockify.BlockNode):
            sess.writeToFooter(n.contents)
            dumpBlockBodies(sess, n.children)
        elif isinstance(n, parse.ReactiveNode):
            dumpBlockBodies(sess, n.body)
            dumpBlockBodies(sess, n.elseBody)
        elif isinstance(n, parse.ConsolidatableNode):
            pass
        else:
            raise RuntimeError, "Bad node %s in dumpBlockBodies" % n
