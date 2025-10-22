#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import typer.testing

from s2gos_common.process import ProcessRegistry
from s2gos_common.process.cli.cli import get_cli

registry = ProcessRegistry()


@registry.process(id="f1")
def f1(a: int, b: str, c: float) -> str:
    return f"{a}, {b}, {c}"


@registry.process(id="f2")
def f2(x: bool, y: str, z: float) -> tuple:
    if y == "bibo":
        raise ValueError("y must not be bibo")
    return x, y, z


# noinspection PyUnresolvedReferences
class CliTestMixin:
    @classmethod
    def get_cli(cls) -> typer.Typer:
        raise NotImplementedError

    @classmethod
    def invoke_cli(cls, *args: str) -> typer.testing.Result:
        runner = typer.testing.CliRunner()
        return runner.invoke(cls.get_cli(), args)

    def test_execute_process_f1_success(self):
        result = self.invoke_cli(
            "execute-process", "f1", "-i", "a=0", "-i", "b=bibo", "-i", "c=0.2"
        )
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            '{\n  "return_value": "0, bibo, 0.2"\n}\n',
            result.output,
        )

    def test_execute_process_f2_success(self):
        result = self.invoke_cli(
            "execute-process", "f2", "-i", "x=true", "-i", "y=pippo", "-i", "z=0.3"
        )
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            '{\n  "return_value": [\n    true,\n    "pippo",\n    0.3\n  ]\n}\n',
            result.output,
        )

    def test_execute_process_f2_fail(self):
        result = self.invoke_cli(
            "execute-process", "f2", "-i", "x=true", "-i", "y=bibo", "-i", "z=1.8"
        )
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertIn('  "processID": "f2",', result.output)
        self.assertIn('  "status": "failed",', result.output)
        self.assertIn('  "message": "y must not be bibo",', result.output)

    def test_execute_process_fail(self):
        result = self.invoke_cli("execute-process", "f5")
        self.assertEqual(1, result.exit_code, msg=self.get_result_msg(result))
        self.assertIn("Process 'f5' not found.", result.output)

    def test_list_processes(self):
        result = self.invoke_cli("list-processes")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            (
                "{\n"
                '  "f1": {\n'
                '    "id": "f1",\n'
                '    "version": "0.0.0"\n'
                "  },\n"
                '  "f2": {\n'
                '    "id": "f2",\n'
                '    "version": "0.0.0"\n'
                "  }\n"
                "}\n"
            ),
            result.output,
        )

    def test_get_process_ok(self):
        result = self.invoke_cli("get-process", "f2")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertEqual(
            (
                "{\n"
                '  "id": "f2",\n'
                '  "version": "0.0.0",\n'
                '  "inputs": {\n'
                '    "x": {\n'
                '      "title": "X",\n'
                '      "schema": {\n'
                '        "type": "boolean"\n'
                "      }\n"
                "    },\n"
                '    "y": {\n'
                '      "title": "Y",\n'
                '      "schema": {\n'
                '        "type": "string"\n'
                "      }\n"
                "    },\n"
                '    "z": {\n'
                '      "title": "Z",\n'
                '      "schema": {\n'
                '        "type": "number"\n'
                "      }\n"
                "    }\n"
                "  },\n"
                '  "outputs": {\n'
                '    "return_value": {\n'
                '      "title": "Return Value",\n'
                '      "schema": {\n'
                '        "type": "array",\n'
                '        "items": {}\n'
                "      }\n"
                "    }\n"
                "  }\n"
                "}\n"
            ),
            result.output,
        )

    def test_get_process_fail(self):
        result = self.invoke_cli("get-process", "f9")
        self.assertEqual(1, result.exit_code, msg=self.get_result_msg(result))
        self.assertIn("Process 'f9' not found.", result.output)

    def test_help(self):
        result = self.invoke_cli("--help")
        self.assertEqual(0, result.exit_code, msg=self.get_result_msg(result))
        self.assertIn(
            "Command-line interface for process description and execution",
            result.output,
        )

    @classmethod
    def get_result_msg(cls, result: typer.testing.Result):
        if result.exit_code != 0:
            return f"output was: [{result.output}]\nstderr was: [{result.stderr}]"
        else:
            return None


class AppWithRealClientTest(TestCase):
    def test_get_processes(self):
        """Test code in app so that the non-mocked Client is used."""
        cli = CliRegistryTest.get_cli()
        runner = typer.testing.CliRunner()
        result = runner.invoke(cli, ["list-processes"])
        # May succeed if dev server is running
        self.assertTrue(
            result.exit_code in (0, 1), msg=f"exit code was {result.exit_code}"
        )
        if result.exit_code != 0:
            print(result.output)


class CliRegistryTest(CliTestMixin, TestCase):
    @classmethod
    def get_cli(cls):
        return get_cli(registry)


class CliRegistryRefTest(CliTestMixin, TestCase):
    @classmethod
    def get_cli(cls):
        return get_cli("tests.process.cli.test_cli:registry")


class CliRegistryGetterTest(CliTestMixin, TestCase):
    @classmethod
    def get_cli(cls):
        def get_registry():
            return registry

        return get_cli(get_registry)
