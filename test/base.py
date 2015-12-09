import sys
from unittest import TestCase

from mock import Mock, patch


class PatchingTestCase(TestCase):

    patch_list = ()

    def setUp(self):
        self.patches = []
        for name in self.patch_list:
            p = patch(name)
            self.patches.append(p)
            setattr(self, name.split(".")[-1], p.start())

    def tearDown(self):
        for p in self.patches:
            p.stop()


def mock_imports(module_names):
    for name in module_names:
        sys.modules[name] = Mock()
