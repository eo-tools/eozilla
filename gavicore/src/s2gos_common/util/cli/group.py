#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import click
import typer.core


class AliasedGroup(typer.core.TyperGroup):
    """
    A group that accepts command aliases created from the
    first letters of the words after splitting a command name
    at hyphens.
    """

    @staticmethod
    def to_alias(name: str):
        """Create a short alias for given command name."""
        return "".join(map(lambda n: n[0], name.split("-")))

    def get_command(self, ctx, cmd_name):
        rv = super().get_command(ctx, cmd_name)

        if rv is not None:
            return rv

        matches = [
            x
            for x in self.list_commands(ctx)
            if cmd_name == x or cmd_name == self.to_alias(x)
        ]

        if not matches:
            return None

        if len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])

        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(
        self, ctx, args
    ) -> tuple[str | None, click.Command | None, list[str]]:
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        if cmd is not None:
            return cmd.name, cmd, args
        else:
            return None, None, args

    def list_commands(self, ctx):
        # prevent alphabetical ordering
        return list(self.commands)
