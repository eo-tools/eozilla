#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import unittest

import pytest

from s2gos_common.util.dynimp import import_value

my_nice_number = 137
my_nice_string = "137"


class ImportAttributeTest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(
            137,
            import_value(
                "tests.util.test_dynimp:my_nice_number", type=int, name="nice number"
            ),
        )

    def test_invalid_ref(self):
        self.assert_fails(
            "hello.num",
            r"The nice number reference must be passed in the form "
            r"'path\.to\.module\:attr', but got 'hello\.num'\.",
        )

    def test_invalid_module(self):
        self.assert_fails(
            "hel.lo:num",
            r"Cannot import module 'hel.lo'\.",
        )

    def test_invalid_attrib(self):
        self.assert_fails(
            "tests.util.test_dynimp:num",
            r"Module 'tests\.util\.test_dynimp' "
            r"has no attribute 'num'\.",
        )

    def test_invalid_type(self):
        self.assert_fails(
            "tests.util.test_dynimp:my_nice_string",
            r"The reference 'tests\.util\.test_dynimp:my_nice_string' "
            r"should refer to a nice number of type int, but got type str\.",
            exc=TypeError,
        )

    # noinspection PyMethodMayBeStatic
    def assert_fails(
        self,
        value: str | None,
        match: str,
        exc: type[Exception] = ValueError,
    ):
        with pytest.raises(exc, match=match):
            import_value(value, type=int, name="nice number")
