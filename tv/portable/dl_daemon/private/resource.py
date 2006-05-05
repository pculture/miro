from dl_daemon import daemon, command

def path(relative_path):
    comm = command.GetResourcePathCommand(daemon.lastDaemon, relative_path)
    return comm.send(retry = True)

def url(relative_path):
    comm = command.GetResourceURLCommand(daemon.lastDaemon, relative_path)
    return comm.send(retry = True)
