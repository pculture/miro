import threading

class Template:
    def __init__(self):
        self.lock = threading.RLock()
        self.__children = []

    def fillToStream(self, stream, receiver):
        origStdout = sys.stdout
        self.lock.acquire()
        try:
            self.receiver = receiver
            # NEEDS: this is kinda lame!!
            sys.stdout = stream
            self.__fill()
        finally:
            self.lock.release()
            sys.stdout = origStdout

    def close(self):
        # NEEDS!!
        pass

# NEEDS: emit instances of these in compiled template
# NEEDS: emit indexComputer arguments to other Nodes
# NEEDS: emit calls to setExpansionSize in __fill's (tricky, but not too)
class IndexComputer:
    def __init__(self, id, sizes):
        self.id = id
        self.sizes = sizes

    def setExpansionSize(self, offset, size):
        self.sizes[offset] = size

    def getIndexForOffset(self, offset):
        ret = 0
        for i in range(0, offset):
            ret += self.sizes[i]
        return i

class DynamicNode:
    def __init__(self, parentsChildren, template, indexComputer,
                 indexComputerOffset, *environment):
        self.parentsChildren.append(self)

        self.template = template
        self.indexComputer = indexComputer
        self.indexComputerOffset = indexComputerOffset
        self.environment = environment
        self.obj = self.expression(*environment)

    def close(self):
        for child in self.__children:
            child.close()
        self.obj.stopTracking(self)

class SynchronizeNode (DynamicNode):
    def __init__(self, *args):
        DynamicNode.__init__(*args)
        self.obj.startTracking(self, self.changed)
        self.children = []
        self.body(self.children)

    def changed(self, *junk):
        self.template.lock.acquire()
        try:
            # Make all of the children in the old expansion go away, so
            # that they don't try to generate updates.
            for child in self.children:
                child.close()
            self.children = []

            # NEEDS: Start capturing output to 'buf'
            self.body(self.children)
            # End capturing

            # Call this with lock held -- receiver object is expected to
            # deal with it promptly (by queueing, etc.) without triggering
            # another update
            self.template.receiver.replaceChildren(\
                self.indexComputer.id,
                self.indexComputer.getIndexForOffset(self.indexComputerOffset),
                self.indexComputer.getExpansionSize(self.indexComputerOffset),
                buf)
        finally:
            self.template.lock.release()


class IfNode (DynamicNode):
    def __init__(self, *args):
        DynamicNode.__init__(*args)

        self.children = []
        if self.obj.startTracking(self, self.changed):
            self.body(self.children)
        else:
            self.elseBody(self.children)

    def changed(self, newValue):
        self.template.lock.acquire()
        try:
            for child in self.__children:
                child.close()
            self.children = []

            # NEEDS: Start capturing output to 'buf'
            if newValue:
                self.body(self.children)
            else:
                self.elseBody(self.children)
            # End capturing

            self.template.receiver.replaceChildren(\
                self.indexComputer.id,
                self.indexComputer.getIndexForOffset(self.indexComputerOffset),
                self.indexComputer.getExpansionSize(self.indexComputerOffset),
                buf)
        finally:
            self.template.lock.release()

class ForNode (DynamicNode):
    def __init__(self, *args):
        DynamicNode.__init__(*args)

        self.elementChildren = None
        self.elementSizes = None
        self.elseChildren = None
        self.elseSize = None
        self.totalSize = 0

        self.environment = list(self.environment)
        ptr = len(self.environment)
        self.environment.append(None)

        v = self.obj.startTracking(self, self)
        if len(v) == 0:
            self.elseChildren = []
            self.elseSize = self.elseBody(self.elseChildren)
            self.totalSize = self.elseSize
        else:
            self.elementChildren = []
            self.elementSizes = []
            for x in v:
                self.environment[ptr] = x
                theseKids = []
                thisSize = self.body(theseKids)
                self.elementChildren.append(theseKids)
                self.totalSize += thisSize
                self.elementSizes.append(thisSize)

    def itemAdded(newIndex, value):
        self.template.lock.acquire()
        try:
            # NEEDS: once again we're in quite a pickle.. we need to know
            # the expansion width of each element. they may differ! let's
            # make the body functions return this value.
            pass
        finally:
            self.template.lock.release()

    def itemReplaced(index, value):
        self.template.lock.acquire()
        try:
            # NEEDS
            pass
        finally:
            self.template.lock.release()

    def itemRemoved(index):
        self.template.lock.acquire()
        try:
            # Kill affected children
            for child in self.elementChildren[index]:
                child.close()

            # Resize tracking arrays
            self.elementChildren = \
                self.elementChildren[:index] + \
                self.elementChildren[index+1:]
            oldSize = self.elementSizes[index]
            self.elementSizes = \
                self.elementSizes[:index] + \
                self.elementSizes[index+1:]

            # Send the message
            self.template.receiver.removeChildren(\
                self.indexComputer.id,
                self.indexComputer.getIndexForOffset(self.indexComputerOffset),
                oldSize)

            # Maybe switch to 'else' clause!
            if len(self.elementSizes) == 0:
                self.elementChildren = self.elementSizes = None

                self.elseChildren = []
                # NEEDS: capture to buf
                self.elseSize = self.elseBody(self.elseChildren)
                # NEEDS: end capture
                self.totalSize = self.elseSize

                self.template.receiver.addChildren(\
                    self.indexComputer.id,
                    self.indexComputer.getIndexForOffset(\
                        self.indexComputerOffset),
                    buf)
            else:
                # No, just update our size to account for deletion
                self.totalSize -= oldSize

            # Tell others about our size change
            self.indexComputer.setExpansionSize(self.indexComputerOffset,
                                                self.totalSize)
            # NEEDS: need to update parent size here!! guess we need a
            # parent pointer after all..
        finally:
            self.template.lock.release()

def utf8(x):
    return x.encode('utf8')

def utf8_js(x):
    x = x.replace("\\", "\\\\") # \       -> \\
    x = x.replace("\"", "\\\"") # "       -> \"  
    x = x.replace("'",  "\\'")  # '       -> \'
    x = x.replace("\n", "\\n")  # newline -> \n
    x = x.replace("\r", "\\r")  # CR      -> \r
    return x.encode('utf8')
