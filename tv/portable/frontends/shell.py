import readline
import rlcompleter
import code
import threading

from miro import app
from miro import startup
from miro import messages

def run():
    messages.FrontendMessage.install_handler(MessageHandler())
    startup.startup()
    print 'startup exit'

class MessageHandler(messages.MessageHandler):
    def handle(self, message):
        if isinstance(message, messages.StartupSuccess):
            self.run_shell()
        else:
            print 'got message: ', message

    def run_shell(self):
        print
        print '** starting shell**'
        print
        imported_objects = {}
        for mod in ('database', 'feed', 'item', 'views'):
            imported_objects[mod] = getattr(__import__('miro.%s' % mod), mod)
        readline.set_completer(rlcompleter.Completer(imported_objects).complete)
        readline.parse_and_bind("tab:complete")
        code.interact(local=imported_objects)

        app.controller.shutdown()
