import os
from string import Template
from distutils.util import change_root
import distutils.command.install_data

from paths import resource_dir, root_dir

class install_data (distutils.command.install_data.install_data):
    """install_data extends to default implementation so that it automatically
    installs app.config from app.config.template.
    """

    def install_app_config(self):
        source = os.path.join(resource_dir, 'app.config.template')
        f = open(source)
        template = Template(f.read())
        f.close()
        svnversion = os.popen('svnversion %s' % root_dir).read().strip()
        built_template = template.substitute(APP_REVISION=svnversion,
                APP_PLATFORM='gtk-x11')
        dest = '/usr/share/democracy/resources/app.config'
        if self.root:
            dest = change_root(self.root, dest)
        self.mkpath(os.path.dirname(dest))
        f = open(dest, 'wt')
        f.write(built_template)
        f.close()
        self.outfiles.append(dest)

    def run(self):
        distutils.command.install_data.install_data.run(self)
        self.install_app_config()
