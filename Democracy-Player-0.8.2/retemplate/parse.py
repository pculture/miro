import re
import string

forSplitPattern = re.compile(r"^\s*(\S+)\s*in\s*(.*)$")

###############################################################################
### Node classes                                                            ###
###############################################################################

def dumpList(i, x):
    for y in x:
        y.dump(i)

class Node:
    def __init__(self):
        self.formals = []

    def addFormal(self, f):
        raise ValueError, "Error: Declaration of variable '%s' would shadow " \
            "earlier definition" % f
        self.formals.append(f)

    def allChildren(self):
        raise NotImplementedError

class ConsolidatableNode (Node):
    def __init__(self):
        Node.__init__(self)

class LiteralNode (ConsolidatableNode):
    def __init__(self, text):
        self.text = text
        ConsolidatableNode.__init__(self)

    def dump(self, i):
        print "%sLiteral %s" % (" " * i, [self.text])

    def allChildren(self):
        return []

class EvaluateNode (ConsolidatableNode):
    def __init__(self, expr):
        self.expr = expr
        ConsolidatableNode.__init__(self)

    def dump(self, i):
        print "%sEval    %s (with %s)" % (" " * i, [self.expr], self.formals)

    def allChildren(self):
        return []

class StaticNode (ConsolidatableNode):
    def __init__(self, type, expr, body, elseBody):
        self.type = type
        self.expr = expr
        self.body = body
        self.elseBody = elseBody
        ConsolidatableNode.__init__(self)

    def dump(self, i):
        print "%sStatic-%s '%s'%s:" % (" " * i, self.type, self.expr,
                                       self.formals)
        dumpList(i + 4, self.body)
        if self.elseBody:
            print "%sElse:" % (" " * i)
            dumpList(i + 4, self.elseBody)

    def allChildren(self):
        kids = self.body
        if self.elseBody:
            kids = kids + self.elseBody
        return kids

class StaticIfNode (StaticNode):
    def __init__(self, expr, body, elseBody):
        StaticNode.__init__(self, 'if', expr, body, elseBody)

    def generate(self, blockNode, subGenerateFunc, indent):
        blockNode.write("%sif %s:\n" % (" " * indent, self.expr))
        subGenerateFunc(self.body, indent + 4)
        if self.elseBody:
            blockNode.write("%selse:\n" % (" " * indent, ))
            subGenerateFunc(self.elseBody, indent + 4)

class StaticForNode (StaticNode):
    def __init__(self, expr, body, elseBody):
        match = forSplitPattern.match(expr)
        if not match:
            raise ValueError, "Bad syntax '%s' in 'for' tag" % expr
        self.formal = match.group(1)
        self.iterable = match.group(2)
        StaticNode.__init__(self, 'for', expr, body, elseBody)

    def generate(self, blockNode, subGenerateFunc, indent):
        iterable = self.iterable
        if self.elseBody:
            iterable = "___iterable"
            blockNode.write("%s___iterable = %s\n" % \
                            (" " * indent, self.iterable))
            blockNode.write("%sif len(___iterable) == 0:\n" % (" " * indent))
            subGenerateFunc(self.elseBody, indent + 4)
            blockNode.write("%selse:\n" % (" " * indent))
            indent += 4
        blockNode.write("%sfor %s in %s:\n" % (" " * indent,
                                                self.formal,
                                                iterable))
        subGenerateFunc(self.body, indent + 4)

class ReactiveNode (Node):
    def __init__(self, runtimeClass, expr, body, elseBody=None):
        self.name = None
        self.runtimeClass = runtimeClass
        self.expr = expr
        self.body = body
        self.elseBody = elseBody
        Node.__init__(self)

    def getName(self, sess):
        if self.name is None:
            self.name = sess.nextClassName()
        return self.name

    def allChildren(self):
        kids = self.body
        if self.elseBody:
            kids = kids + self.elseBody
        return kids

class ForNode (ReactiveNode):
    def __init__(self, formal, expr, body, elseBody):
        ReactiveNode.__init__(self, "retemplate_lib.ForNode", \
                              expr, body, elseBody)
        self.formal = formal
        
    def dump(self, i):
        print "%sFOR {%s} IN {%s} GIVEN %s:" % (" " * i, self.formal,
                                                self.expr,
                                                self.formals)
        dumpList(i + 4, self.body)
        if self.elseBody:
            print "%sELSE:" % (" " * i)
            dumpList(i + 4, self.elseBody)

class IfNode (ReactiveNode):
    def __init__(self, expr, body, elseBody):
        ReactiveNode.__init__(self, "retemplate_lib.IfNode", \
                              expr, body, elseBody)
    def dump(self, i):
        print "%sIF {%s} GIVEN %s:" % (" " * i, self.expr, self.formals)
        dumpList(i + 4, self.body)
        if self.elseBody:
            print "%sELSE:" % (" " * i)
            dumpList(i + 4, self.elseBody)

class SynchronizeNode (ReactiveNode):
    def __init__(self, expr, body):
        ReactiveNode.__init__(self, "retemplate_lib.SynchronizeNode", \
                              expr, body)
    def dump(self, i):
        print "%sSYNCHRONIZE GIVEN %s:" % (" " * i, self.expr, self.formals)
        dumpList(i + 4, self.body)

###############################################################################
### Very simple parser                                                      ###
###############################################################################

def parseCommand(parser, command, expression):
    if command == '=':
        return EvaluateNode(expression)

    if command == 'header':
        parser.writeToHeader(expression + "\n")
        return None

    if command == 'def':
        global classBody
        lines = expression.split('\n')
        allIndented = string.join(["     " + line for line in lines], '\n')
        parser.writeToBody("    def " + allIndented[5:] + '\n')
        return None

    def readDualBody():
        elseBody = None
        (body, end) = parseBody(parser, ['else', 'end'])
        if end == 'else':
            (elseBody, end) = parseBody(parser, ['end'])
        return (body, elseBody)

    if command == 'if':
        (body, elseBody) = readDualBody()
        return StaticIfNode(expression, body, elseBody)

    if command == 'for':
        (body, elseBody) = readDualBody()
        return StaticForNode(expression, body, elseBody)

    if command == 'reif':
        (body, elseBody) = readDualBody()
        return IfNode(expression, body, elseBody)

    if command == 'refor':
        match = forSplitPattern.match(expression)
        if not match:
            raise ValueError, "Bad 'for' syntax: '%s'" % expression
        (body, elseBody) = readDualBody()
        return ForNode(match.group(1), match.group(2), body, elseBody)

    if command == 'synchronize':
        (body, end) = parseBody(['end'])
        return SynchronizeNode(expression, body)
    
    raise ValueError, "Unexpected tag '%s'" % command

def parseBody(parser, endTags=None):
    out = []

    while True:
        t = parser.next()

        if t == None:
            if endTags == None:
                return out # end of file
            else:
                raise ValueError, "Got end of file; expected one of: %s" % \
                    endTags

        if type(t) == str:
            out.append(LiteralNode(t))
        else:
            (command, expression) = t
            if endTags and command in endTags: 
                return (out, command)
            this = parseCommand(parser, command, expression)
            if this:
                out.append(this)

###############################################################################
### Parser driver                                                           ###
###############################################################################

class Parser:
    def __init__(self, session, tokens):
        self.session = session
        self.tokens = tokens
        self.index = 0
        self.packageHeader = ""
        self.classBody = ""

    def next(self):
        try:
            self.index += 1
            return self.tokens[self.index-1]
        except IndexError:
            return None
        
    def writeToHeader(self, s):
        self.session.writeToHeader(s)

    def writeToBody(self, s):
        self.session.writeToBody(s)

    def run(self):
        return parseBody(self)

def parse(sess, tokens):
    return Parser(sess, tokens).run()
