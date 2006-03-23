# Democracy download daemon Copyright (c) 2006 Participatory Culture Foundation
# Background process

# These are found in portable/dl_daemon/private
import resource, platformcfg
from dl_daemon import daemon, command

server = daemon.Daemon(server = True)

from dl_daemon import download
download.startBTDownloader()
c = command.ReadyCommand(server)
c.send(block = False, retry = True)
