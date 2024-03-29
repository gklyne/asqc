#!/usr/bin/env python

"""
Context manager for redirecting stdout to a supplied file or stream
"""

import sys

class SwitchStdout:
    """
    Context handler class that swiches standard output to a named file or supplied stream.
    
    See also http://code.activestate.com/recipes/577564-context-manager-for-low-level-redirection-of-stdou/
    I didn't use this because I wanted to be able to catch output to a StringIO stream for testing.
    """
    
    def __init__(self, fileorstr):
        self.fileorstr = fileorstr
        self.opened = False
        return
    
    def __enter__(self):
        if isinstance(self.fileorstr,basestring):
            self.outstr = open(self.fileorstr, "w")
            self.opened = True
        else:
            self.outstr = self.fileorstr
        self.savestdout = sys.stdout
        sys.stdout = self.outstr
        return 

    def __exit__(self, exctype, excval, exctraceback):
        if self.opened: self.outstr.close()
        sys.stdout = self.savestdout
        return False

if __name__ == "__main__":
    import StringIO
    outstr = StringIO.StringIO()
    with SwitchStdout(outstr) as mystdout:
        print( "Hello, " )
        print( "world", file=mystdout )
    outtxt = outstr.getvalue()
    print( repr(outtxt) )
    assert  outtxt == "Hello, \nworld\n"
    outstr.close()

# End.
