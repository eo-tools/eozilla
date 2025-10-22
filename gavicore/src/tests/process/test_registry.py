#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from s2gos_common.process import Process, ProcessRegistry
from s2gos_common.util.testing import BaseModelMixin

from .test_process import f1, f2, f3


class ProcessRegistryTest(BaseModelMixin, TestCase):
    def test_register(self):
        registry = ProcessRegistry()
        self.assertEqual(None, registry.get("f1"))
        self.assertEqual([], list(registry.keys()))

        # use as no-arg decorator
        registry.process(f1)
        self.assertEqual(1, len(registry))
        p1 = list(registry.values())[0]
        self.assertIsInstance(p1, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertEqual(["tests.process.test_process:f1"], list(registry.keys()))

        # use as decorator with args
        registry.process(id="f2")(f2)
        self.assertEqual(2, len(registry))
        p1, p2 = registry.values()
        self.assertIsInstance(p1, Process)
        self.assertIsInstance(p2, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertIs(p2, registry.get(p2.description.id))
        self.assertEqual(["tests.process.test_process:f1", "f2"], list(registry.keys()))

        # use as function
        registry.process(f3, id="my_fn3")
        self.assertEqual(3, len(registry))
        p1, p2, p3 = registry.values()
        self.assertIsInstance(p1, Process)
        self.assertIsInstance(p2, Process)
        self.assertIsInstance(p3, Process)
        self.assertIs(p1, registry.get(p1.description.id))
        self.assertIs(p2, registry.get(p2.description.id))
        self.assertIs(p3, registry.get(p3.description.id))
        self.assertEqual(
            ["tests.process.test_process:f1", "f2", "my_fn3"], list(registry.keys())
        )
