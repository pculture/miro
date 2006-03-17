# Democracy download daemon Copyright (c) 2006 Participatory Culture Foundation
# Background process

# Currently, this must be run with a command like the following
#
# PYTHONPATH=".;dl_daemon/private" python dl_daemon/run.py

import resource, platformcfg
from dl_daemon import daemon

server = daemon.Daemon(server = True)

from dl_daemon import download
download.startBTDownloader()
