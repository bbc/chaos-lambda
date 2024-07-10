import contextlib
import sys
from unittest import TestCase
from unittest.mock import Mock, patch


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


@contextlib.contextmanager
def mocked_imports(module_names):
    old = {}
    mocks = {}
    for name in module_names:
        old[name] = sys.modules.get(name, None)
        sys.modules[name] = mocks[name] = Mock()
    yield mocks
    for name, module in old.items():
        if module is None:
            del sys.modules[name]
        else:
            sys.modules[name] = module
