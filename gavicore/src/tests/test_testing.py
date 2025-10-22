#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from unittest import TestCase

import pytest

from s2gos_common.models import Schema
from s2gos_common.util.testing import BaseModelMixin, set_env_cm


class TestingTest(BaseModelMixin, TestCase):
    def test_assert_base_model_equal(self):
        self.assertBaseModelEqual(Schema(type="integer"), Schema(type="integer"))
        with pytest.raises(AssertionError):
            self.assertBaseModelEqual(Schema(type="integer"), Schema(type="string"))

    def test_set_env_cm(self):
        old_env = dict(os.environ)
        with set_env_cm(S2GOS_SERVICE="abc", S2GOS_USER_NAME="xyz"):
            self.assertEqual("abc", os.environ.get("S2GOS_SERVICE"))
            self.assertEqual("xyz", os.environ.get("S2GOS_USER_NAME"))
            self.assertNotEqual(old_env, os.environ)
            with set_env_cm(S2GOS_SERVICE=None, S2GOS_USER_NAME=None):
                self.assertEqual(None, os.environ.get("S2GOS_SERVICE"))
                self.assertEqual(None, os.environ.get("S2GOS_USER_NAME"))
            self.assertEqual("abc", os.environ.get("S2GOS_SERVICE"))
            self.assertEqual("xyz", os.environ.get("S2GOS_USER_NAME"))
            self.assertNotEqual(old_env, os.environ)
        self.assertEqual(old_env, os.environ)
