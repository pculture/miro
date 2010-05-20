from miro.plat.frontends.widgets.sparkleupdater import _get_minimum_system_version
from miro.plat.frontends.widgets.sparkleupdater import _test_host_version
from miro.plat.frontends.widgets.sparkleupdater import _get_host_version
from miro.test.framework import MiroTestCase

class SparkleUpdaterTest(MiroTestCase):

    def test_minimum_version_parsing(self):
        info = dict()
        self.assertEqual(_get_minimum_system_version(info), [0, 0, 0])
        info['minimumsystemversion'] = "10.6"
        self.assertEqual(_get_minimum_system_version(info), [10, 6, 0])
        info['minimumsystemversion'] = "10.6.3"
        self.assertEqual(_get_minimum_system_version(info), [10, 6, 3])

    def test_version_comparison(self):
        self.assertFalse(_test_host_version([10, 4, 0], [10, 5, 0]))
        self.assertFalse(_test_host_version([10, 4, 4], [10, 5, 0]))
        self.assertFalse(_test_host_version([10, 4, 0], [10, 5, 1]))
        self.assertFalse(_test_host_version([10, 4, 4], [10, 5, 1]))
        self.assertFalse(_test_host_version([10, 4, 4, 0], [10, 5, 1]))
        self.assertTrue(_test_host_version([10, 6, 0], [10, 5, 0]))
        self.assertTrue(_test_host_version([10, 6, 0], [10, 5, 5]))
        self.assertTrue(_test_host_version([10, 6, 3], [10, 5, 0]))
        self.assertTrue(_test_host_version([10, 6, 3], [10, 5, 5]))
        self.assertTrue(_test_host_version([10, 6, 3], [10, 6, 3]))
        self.assertTrue(_test_host_version([10, 6, 3, 0], [10, 6, 3]))
