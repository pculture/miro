# Democracy download daemon Copyright (c) 2006 Participatory Culture Foundation
# Background process

# These are found in portable/dl_daemon/private
import resource, platformcfg
from dl_daemon import daemon, command

def shutdownDownloader():
    from dl_daemon import download
    return download.shutDown()

server = daemon.Daemon(server = True, onShutdown = shutdownDownloader)
server.createStreamEvent.wait()

from dl_daemon import download
download.startBTDownloader()
c = command.ReadyCommand(server)
c.send(block = False, retry = True)
