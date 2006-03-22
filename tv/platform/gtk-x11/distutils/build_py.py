from glob import glob
import os
import distutils.command.build_py

from paths import portable_dir, platform_dir

class build_py (distutils.command.build_py.build_py):
    """build_py extends the default build_py implementation so that the
    platform and portable directories get merged into the democracy
    package.
    """

    def find_democracy_modules(self):
        """Returns a list of modules to go in the democracy directory.  Each
        item has the form (package, module, path).  The trick here is merging
        the contents of the platform/gtk-x11 and portable directories.
        """
        files = glob(os.path.join(portable_dir, '*.py'))
        files.extend(glob(os.path.join(platform_dir, '*.py')))
        rv = []
        for f in files:
            if os.path.samefile(f, __file__):
                continue
            module = os.path.splitext(os.path.basename(f))[0]
            rv.append(('democracy', module, f))
        return rv

    def find_all_modules (self):
        """Extend build_py's module list to include the democracy modules."""
        modules = distutils.command.build_py.build_py.find_all_modules(self)
        modules.extend(self.find_democracy_modules())
        return modules

    def run(self):
        """Do the build work.  In addition to the default implementation, we
        also build the democracy package from the platform and portable code
        and install the resources as package data.  
        """

        for (package, module, module_file) in self.find_democracy_modules():
            assert package == 'democracy'
            self.build_module(module, module_file, package)
        return distutils.command.build_py.build_py.run(self)
