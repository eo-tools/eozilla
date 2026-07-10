#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest import TestCase

import pytest

from gavicore.util.text import TextConverter


class TextConverterTest(TestCase):
    def test_boolean(self):
        c = TextConverter.Boolean()
        self.assert_converter_works(c, "True", True)
        self.assert_converter_works(c, "true", True)
        self.assert_converter_works(c, "1", True)
        self.assert_converter_works(c, "False", False)
        self.assert_converter_works(c, "false", False)
        self.assert_converter_works(c, "0", False)
        with pytest.raises(ValueError, match="value cannot be converted to boolean"):
            c.parse("_")

    def test_integer(self):
        c = TextConverter.Integer()
        self.assert_converter_works(c, " -137 ", -137)
        with pytest.raises(
            ValueError, match=r"invalid literal for int\(\) with base 10: 'ten'"
        ):
            c.parse("ten")

    def test_number(self):
        c = TextConverter.Number()
        self.assert_converter_works(c, " 3.14", 3.14)

    def test_string(self):
        c = TextConverter.String()
        self.assert_converter_works(c, "a@b.com ", "a@b.com ")

    def test_boolean_array(self):
        c = TextConverter.BooleanArray()
        self.assert_converter_works(c, "true, false, true", [True, False, True])
        self.assert_converter_works(c, "0, 1, 1", [False, True, True])
        with pytest.raises(ValueError, match="invalid array item at index 2"):
            c.parse("true, 0, b6")

    def test_integer_array(self):
        c = TextConverter.IntegerArray()
        self.assert_converter_works(c, "78, 3567, 64532", [78, 3567, 64532])
        self.assert_converter_works(c, "0", [0])
        self.assert_converter_works(c, "0,  3    , -434", [0, 3, -434])
        with pytest.raises(ValueError, match="invalid array item at index 1"):
            c.parse("4, b6")

    def test_number_array(self):
        c = TextConverter.NumberArray()
        self.assert_converter_works(c, "0.1, 0.2, -0.042", [0.1, 0.2, -0.042])

    def test_string_array(self):
        c = TextConverter.StringArray()
        self.assert_converter_works(
            c,
            "202505.nc, 202506.nc, 202507.nc",
            ["202505.nc", "202506.nc", "202507.nc"],
            sep=",",
        )
        self.assert_converter_works(
            c,
            "202505.nc\n202506.nc\n202507.nc",
            ["202505.nc", "202506.nc", "202507.nc"],
            sep="\n",
        )
        self.assert_converter_works(
            c,
            "202505.nc 202506.nc 202507.nc",
            ["202505.nc", "202506.nc", "202507.nc"],
            sep=" ",
        )

    def assert_converter_works(
        self, c: TextConverter, text: str, expected_value: Any, sep=","
    ):
        actual_value = c.parse(text, sep=sep)
        self.assertEqual(expected_value, actual_value)
        # Re-convert
        text_2 = c.format(actual_value, sep=sep)
        actual_value_2 = c.parse(text_2, sep=sep)
        self.assertEqual(expected_value, actual_value_2)
