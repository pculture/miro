from dl_daemon import daemon, command

def get(descriptor):
    comm = command.GetConfigCommand(daemon.lastDaemon, descriptor)
    return comm.send(retry = True)
