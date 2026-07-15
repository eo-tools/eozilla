#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import unittest

import pytest
import typer
from typer.core import TyperCommand
from typer.testing import CliRunner

from gavicore.util.cli.group import AliasedGroup


class AliasedGroupTest(unittest.TestCase):
    def setUp(self):
        tca = TyperCommand("test-command-a")
        tcb = TyperCommand("test-command-b")
        tcc1 = TyperCommand("test-command-c")
        tcc2 = TyperCommand("tiger-claw-command")
        self.group = AliasedGroup(name="test-group", commands=[tca, tcb, tcc1, tcc2])

    def test_get_command_ok(self):
        self.assert_alias_ok("test-command-a", "tca")
        self.assert_alias_ok("test-command-b", "tcb")

    def test_get_command_fail(self):
        ctx = typer.Context(self.group)
        with pytest.raises(typer.BadParameter, match="Too many matches"):
            self.group.get_command(ctx, "tcc")
        self.assertIsNone(self.group.get_command(ctx, "test-command-d"))
        self.assertIsNone(self.group.get_command(ctx, "tcd"))

    def assert_alias_ok(self, command_name, command_alias_name):
        ctx = typer.Context(self.group)
        command = self.group.get_command(ctx, command_name)
        self.assertIsNotNone(command)
        self.assertEqual(command_name, command.name)
        alias_command = self.group.get_command(ctx, command_alias_name)
        self.assertIsNotNone(alias_command)
        self.assertEqual(command_name, alias_command.name)

    def test_resolve_command_ok(self):
        ctx = typer.Context(self.group)
        result = self.group.resolve_command(ctx, ["tcb"])
        self.assertIsInstance(result, tuple)
        self.assertEqual(3, len(result))
        self.assertEqual("test-command-b", result[0])
        self.assertIsInstance(result[1], TyperCommand)
        self.assertEqual([], result[2])

    def test_resolve_command_fail(self):
        ctx = typer.Context(self.group, resilient_parsing=True)
        result = self.group.resolve_command(ctx, ["tcx"])
        self.assertEqual((None, None, []), result)

        app = typer.Typer(cls=AliasedGroup)

        @app.command("test-command")
        def test_command():
            pass

        @app.command("other-command")
        def other_command():
            pass

        result = CliRunner().invoke(app, ["tcx"])
        self.assertEqual(2, result.exit_code)
        self.assertIn("No such command", result.output)
