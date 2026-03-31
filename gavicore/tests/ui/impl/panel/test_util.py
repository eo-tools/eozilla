#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from gavicore.ui.impl.panel.util import ArrayTextConverter


class ArrayTextConverterTest(TestCase):
    def test_boolean(self):
        c = ArrayTextConverter.Boolean()
        self.assert_parse_array(c, "true, false, true", [True, False, True])
        self.assert_parse_array(c, "0, 1, 1", [False, True, True])
        self.assert_format_array(
            c,
            [False, False, True],
            "false, false, true",
        )
        with pytest.raises(ValueError, match="invalid array item at index 2"):
            c.parse_array("true, 0, b6")

    def test_integer(self):
        c = ArrayTextConverter.Integer()
        self.assert_parse_array(c, "78, 3567, 64532", [78, 3567, 64532])
        self.assert_format_array(
            c,
            [0, 3, -434],
            "0, 3, -434",
        )
        with pytest.raises(ValueError, match="invalid array item at index 1"):
            c.parse_array("4, b6")

    def test_number(self):
        c = ArrayTextConverter.Number()
        self.assert_parse_array(c, "0.1, 0.2, -0.042", [0.1, 0.2, -0.042])
        self.assert_format_array(
            c,
            [943.5, -0.5590, 0.333],
            "943.5, -0.559, 0.333",
        )

    def test_string(self):
        c = ArrayTextConverter.String()
        self.assert_parse_array(
            c,
            "202505.nc, 202506.nc, 202507.nc",
            ["202505.nc", "202506.nc", "202507.nc"],
            sep=",",
        )
        self.assert_format_array(
            c,
            ["202505.nc", "202506.nc", "202507.nc"],
            "202505.nc, 202506.nc, 202507.nc",
            sep=",",
        )
        self.assert_parse_array(
            c,
            "202505.nc\n202506.nc\n202507.nc",
            ["202505.nc", "202506.nc", "202507.nc"],
            sep="\n",
        )
        self.assert_format_array(
            c,
            ["202505.nc", "202506.nc", "202507.nc"],
            "202505.nc\n202506.nc\n202507.nc",
            sep="\n",
        )
        self.assert_parse_array(
            c,
            "202505.nc 202506.nc 202507.nc",
            ["202505.nc", "202506.nc", "202507.nc"],
            sep=" ",
        )
        self.assert_format_array(
            c,
            ["202505.nc", "202506.nc", "202507.nc"],
            "202505.nc 202506.nc 202507.nc",
            sep=" ",
        )

    def assert_parse_array(
        self, c: ArrayTextConverter, text: str, expected_value: list, sep=","
    ):
        actual_value = c.parse_array(text, sep=sep)
        self.assertEqual(expected_value, actual_value)

    def assert_format_array(
        self, c: ArrayTextConverter, value: list, expected_text: str, sep=","
    ):
        actual_text = c.format_array(value, sep=sep)
        self.assertEqual(expected_text, actual_text)
