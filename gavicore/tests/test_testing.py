#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from unittest import TestCase

import pytest

from gavicore.models import Schema
from gavicore.util.testing import BaseModelMixin, set_env_cm


class TestingTest(BaseModelMixin, TestCase):
    def test_assert_base_model_equal(self):
        self.assertBaseModelEqual(Schema(type="integer"), Schema(type="integer"))
        with pytest.raises(AssertionError):
            self.assertBaseModelEqual(Schema(type="integer"), Schema(type="string"))

    def test_set_env_cm(self):
        old_env = dict(os.environ)
        with set_env_cm(EOZILLA_SERVICE="abc", EOZILLA_USER_NAME="xyz"):
            self.assertEqual("abc", os.environ.get("EOZILLA_SERVICE"))
            self.assertEqual("xyz", os.environ.get("EOZILLA_USER_NAME"))
            self.assertNotEqual(old_env, os.environ)
            with set_env_cm(EOZILLA_SERVICE=None, EOZILLA_USER_NAME=None):
                self.assertEqual(None, os.environ.get("EOZILLA_SERVICE"))
                self.assertEqual(None, os.environ.get("EOZILLA_USER_NAME"))
            self.assertEqual("abc", os.environ.get("EOZILLA_SERVICE"))
            self.assertEqual("xyz", os.environ.get("EOZILLA_USER_NAME"))
            self.assertNotEqual(old_env, os.environ)
        self.assertEqual(old_env, os.environ)
