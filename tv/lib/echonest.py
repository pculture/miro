# Miro - an RSS based video player application
# Copyright (C) 2011
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

"""``miro.echonest`` -- Query Echonest"""

from pyechonest import config
from pyechonest import song

from miro import util
from miro import eventloop

# TODO: get a PCF echonest API key
config.ECHO_NEST_API_KEY="ZAHBN7QAMJFJLABY6"

try:
    import simplejson as json
except ImportError:
    import json

class CodegenError(StandardError):
    """ENMFP or echoprint failed to process a file."""

def exec_codegen(codegen_path, media_path, callback, errback):
    """Run an echonest codegen in a worker thread.

    This method should work for both ENMFP and echoprint.

    On success, callback(media_path, echonest_code) will be called.

    On error, errback(media_path, exception) will be called.
    """
    def thread_function():
        stdout = util.call_command(codegen_path, media_path)
        results = json.loads(stdout)
        # not sure why the code generator always returns a 1-element list, but
        # it does
        results = results[0]
        if 'error' in results:
            raise CodegenError(results['error'])
        # NOTE: both codegens return some metadata that we can use, but
        # mutagen can get the same data so let's just pay attention to the
        # code.
        return results['code']

    def thread_callback(code):
        callback(media_path, code)

    def thread_errback(error):
        errback(media_path, error)

    eventloop.call_in_thread(thread_callback, thread_errback, thread_function,
                             'exec echonest codegen')
