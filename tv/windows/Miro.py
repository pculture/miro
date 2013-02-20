# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""Startup the main Miro process or run unittests.
"""

import os
import sys
import logging
import tempfile

def startup(argv):
    # Rewrite the stdout and stderr to catch cases debug being printed via
    # a print or via a write to stderr.  Normally we would use shortAppName
    # but at this point nothing has been bootstrapped yet.  We only want to
    # catch it though if py2exe has fiddled with our file descriptors.
    #
    # The stdout/stderr are redirected again in the Windows-specific
    # setup_logging(). 
    #
    # See bz17793
    redirected = sys.stdout != sys.__stdout__
    if redirected:
        try:
            logfile = os.path.join(tempfile.gettempdir(), 'Miro_console.log')
            sys.stderr = sys.stdout = open(logfile, 'w')
        except EnvironmentError:
            # too bad ... let's silence rather than spew stuff to stop it 
            # writing to a file that it might not have permissions to.  
            # Hopefully, this does not happen often.
            sys.stderr = sys.stdout = open(os.devnull, 'w')

    # Before importing gstreamer, fix os.environ so gstreamer finds its
    # plugins.  Do this early before any code is run to prevent any import
    # of gst missing this!
    from miro.plat import resources
    from miro.plat import config
    GST_PLUGIN_PATH = os.path.join(resources.app_root(), 'gstreamer-0.10')
    os.environ["GST_PLUGIN_PATH"] = GST_PLUGIN_PATH
    os.environ["GST_PLUGIN_SYSTEM_PATH"] = GST_PLUGIN_PATH
    # normally we'd use app.config to get this, but we're starting up
    os.environ["GST_REGISTRY"] = os.path.join(config._get_support_directory(),
                                              'gst_registry.bin')

    theme = None
    # Should have code to figure out the theme.

    from miro.plat import pipeipc
    try:
        pipe_server = pipeipc.Server()
    except pipeipc.PipeExists:
        pipeipc.send_command_line_args()
        return
    pipe_server.start_process()

    from miro.plat import prelogger
    prelogger.install()

    from miro.plat.utils import initialize_locale
    initialize_locale()

    from miro import bootstrap
    bootstrap.bootstrap()

    from miro.plat import commandline
    args = commandline.get_command_line()[1:]

    if '--theme' in args:
        index = args.index('--theme')
        theme = args[index+1]
        del args[index:index+1]

    if '--debug' in args:
        index = args.index('--debug')
        del args[index]
        from miro import app
        app.debugmode = True

    from miro.plat import migrateappname
    migrateappname.migrateSupport('Democracy', 'Miro')

    from miro import commandline
    commandline.set_command_line_args(args)

    # Kick off the application
    from miro import startfrontend
    startfrontend.run_application('widgets', {}, None)
    pipe_server.quit()

def test_startup(argv):
    import sys
    import logging
    logging.basicConfig(level=logging.CRITICAL)

    from miro import app
    app.debugmode = True

    from miro.plat import utils
    utils.initialize_locale()

    from miro import bootstrap
    bootstrap.bootstrap()

    from miro import test
    from miro.plat import resources

    sys.path.append(resources.app_root())
    test.run_tests()

if __name__ == "__main__":
    if "--unittest" in sys.argv:
        sys.argv.remove("--unittest")
        test_startup(sys.argv)
    else:
        startup(sys.argv)

    # sys.exit isn't sufficient--need to really end the process
    from miro.plat.utils import exit_miro
    exit_miro(0)

