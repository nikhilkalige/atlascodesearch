import os.path
import shutil
import time

from AtlasCodeSearch.tests import CommandTestCase


class CindexCommandTest(CommandTestCase):

    def test_cindex_exists(self):
        self.assertIsNotNone(shutil.which('cindex'))

    def test_cindex(self):
        self.window.run_command('cindex', {'index_project': True})
        max_iters = 10
        while (max_iters > 0 and
               (self.view.get_status('AtlasCodeSearch') != '' or
                not os.path.isfile(self.index))):
            time.sleep(0.1)
            max_iters -= 1
        self.assertEquals('', self.view.get_status('AtlasCodeSearch'))
        self.assertTrue(os.path.isfile(self.index))
