import parse

def computeFormals(nodes, soFar=[]):
    for n in nodes:
        if isinstance(n, parse.ForNode):
            soFar = soFar + [n.formal]
        n.formals = soFar
        computeFormals(n.allChildren(), soFar)
            
