#!/usr/bin/env python

"""
Context manager for redirecting stdin to a supplied file or stream
"""

import sys

class SwitchStdin:
    """
    Context handler class that swiches standard input to a named file or supplied stream.
    """
    
    def __init__(self, fileorstr):
        self.fileorstr = fileorstr
        self.opened = False
        return
    
    def __enter__(self):
        if isinstance(self.fileorstr,basestring):
            self.inpstr = open(self.fileorstr, "r")
            self.opened = True
        else:
            self.inpstr = self.fileorstr
        self.savestdin = sys.stdin
        sys.stdin = self.inpstr
        return self.inpstr

    def __exit__(self, exctype, excval, exctraceback):
        if self.opened: self.inpstr.close()
        sys.stdin = self.savestdin
        return False

if __name__ == "__main__":
    import StringIO
    inpstr = StringIO.StringIO("Hello world")
    with SwitchStdin(inpstr) as mystdin:
        inptxt = mystdin.read()
    print repr(inptxt)
    assert inptxt == "Hello world"
    inpstr.close()

# End.
