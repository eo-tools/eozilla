#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Callable

from pydantic import BaseModel


# noinspection PyAttributeOutsideInit,PyUnresolvedReferences,PyPep8Naming
class BaseModelMixin:
    """
    Add to test classes to get the `assertBaseModelEqual` method.
    """

    def assertBaseModelEqual(self, a: BaseModel, b: BaseModel):
        """Assert that two `BaseModel`s are equal."""
        self.maxDiff = None
        self.assertIsInstance(a, BaseModel)  # type: ignore[attr-defined]
        self.assertIsInstance(b, BaseModel)  # type: ignore[attr-defined]
        self.assertIs(b.__class__, a.__class__)  # type: ignore[attr-defined]
        a_value = a.model_dump(
            mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
        )
        b_value = b.model_dump(
            mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
        )
        self.assertEqual(a_value, b_value)  # type: ignore[attr-defined]


@contextmanager
def set_env_cm(**new_env: str | None) -> Generator[dict[str, str | None]]:
    """Run the code in the block with a new environment `new_env`."""
    restore_env = set_env(**new_env)
    try:
        yield new_env
    finally:
        restore_env()


def set_env(**new_env: str | None) -> Callable[[], None]:
    """
    Set the new environment in `new_env` and return a no-arg
    function to restore the old environment.
    """
    old_env = {k: os.environ.get(k) for k in new_env.keys()}

    def restore_env():
        for ko, vo in old_env.items():
            if vo is not None:
                os.environ[ko] = vo
            elif ko in os.environ:
                del os.environ[ko]

    for kn, vn in new_env.items():
        if vn is not None:
            os.environ[kn] = vn
        elif kn in os.environ:
            del os.environ[kn]

    return restore_env
