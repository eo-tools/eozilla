import shutil
import tempfile
import unittest

import xarray as xr

from procodile import ArtifactRef, ArtifactStore, ExecutionContext
from procodile.artifacts import NullArtifactStore
from .utils import DummyArtifactStore


class TestArtifactRef(unittest.TestCase):
    def test_is_frozen_and_fields_set(self):
        ref = ArtifactRef(path="data.zarr", loader="xcube_file_store")

        self.assertEqual(ref.path, "data.zarr")
        self.assertEqual(ref.loader, "xcube_file_store")

        with self.assertRaises(Exception):
            ref.path = "other.zarr"


class TestArtifactStoreABC(unittest.TestCase):
    def test_artifact_store_is_abstract(self):
        with self.assertRaises(TypeError):
            ArtifactStore()  # type: ignore


class TestNullArtifactStore(unittest.TestCase):
    def setUp(self):
        self.store = NullArtifactStore()

    def test_is_big_always_false(self):
        self.assertFalse(self.store.is_big(object()))
        self.assertFalse(self.store.is_big("string"))
        self.assertFalse(self.store.is_big(123))
        self.assertFalse(self.store.is_big(None))

    def test_save_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            self.store.save(object())

    def test_load_raises_runtime_error(self):
        ref = ArtifactRef(path="", loader="")

        with self.assertRaises(RuntimeError):
            self.store.load(ref)

    def test_null_store_is_instance_of_artifact_store(self):
        self.assertIsInstance(self.store, ArtifactStore)


class TestExecutionContext(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = DummyArtifactStore(store_kwargs={"root": self.tmpdir})
        self.ctx = ExecutionContext(self.store)

        self.dataset = xr.Dataset({"x": ("y", [1, 2])})
        self.ref = self.store.save(self.dataset)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_resolve_artifact_ref(self):
        resolved = self.ctx.resolve(self.ref)
        xr.testing.assert_identical(resolved, self.dataset)

    def test_resolve_nested_structures(self):
        value = {
            "a": self.ref,
            "b": [self.ref, (self.ref, 1)],
            "c": (1, 2, [3, 4], self.ref, True),
            "d": {
                "a": 1,
                "b": (9, 8),
                "c": False,
                "d": [1, 2],
                "e": self.ref,
                "f": "g",
            },
        }

        resolved = self.ctx.resolve(value)

        self.assertEqual(set(resolved.keys()), {"a", "b", "c", "d"})

        self.assertIsInstance(resolved["a"], xr.Dataset)

        self.assertIsInstance(resolved["b"], list)
        self.assertIsInstance(resolved["b"][0], xr.Dataset)
        self.assertIsInstance(resolved["b"][1], tuple)
        self.assertIsInstance(resolved["b"][1][0], xr.Dataset)
        self.assertEqual(resolved["b"][1][1], 1)

        self.assertIsInstance(resolved["c"], tuple)
        self.assertEqual(resolved["c"][0], 1)
        self.assertEqual(resolved["c"][1], 2)
        self.assertEqual(resolved["c"][2], [3, 4])
        self.assertIsInstance(resolved["c"][3], xr.Dataset)
        self.assertEqual(resolved["c"][4], True)

        self.assertIsInstance(resolved["d"], dict)
        self.assertEqual(resolved["d"]["a"], 1)
        self.assertEqual(resolved["d"]["b"], (9, 8))
        self.assertEqual(resolved["d"]["c"], False)
        self.assertEqual(resolved["d"]["d"], [1, 2])
        self.assertIsInstance(resolved["d"]["e"], xr.Dataset)
        self.assertEqual(resolved["d"]["f"], "g")

    def test_resolve_scalar(self):
        self.assertEqual(self.ctx.resolve(123), 123)

    def test_materialize_big_object(self):
        result = self.ctx.materialize(self.dataset, self.store)

        self.assertIsInstance(result, ArtifactRef)

        loaded = self.store.load(result)
        xr.testing.assert_identical(loaded, self.dataset)

    def test_materialize_nested(self):
        value = {
            "a": self.dataset,
            "b": [self.dataset, 1],
        }

        result = self.ctx.materialize(value, self.store)

        self.assertIsInstance(result["a"], ArtifactRef)
        self.assertIsInstance(result["b"][0], ArtifactRef)
        self.assertEqual(result["b"][1], 1)

    def test_materialize_scalar(self):
        self.assertEqual(self.ctx.materialize(5, self.store), 5)

    def test_no_output_spec(self):
        result = self.ctx.normalize_outputs(
            self.dataset,
            output_spec=None,
            store=self.store,
        )

        self.assertIn("return_value", result)
        self.assertIsInstance(result["return_value"], ArtifactRef)

    def test_single_output(self):
        result = self.ctx.normalize_outputs(
            self.dataset,
            output_spec={"out": None},
            store=self.store,
        )

        self.assertEqual(set(result.keys()), {"out"})
        self.assertIsInstance(result["out"], ArtifactRef)

    def test_tuple_outputs(self):
        result = self.ctx.normalize_outputs(
            (self.dataset, 1),
            output_spec={"a": None, "b": None},
            store=self.store,
        )

        self.assertIsInstance(result["a"], ArtifactRef)
        self.assertEqual(result["b"], 1)

    def test_tuple_length_mismatch(self):
        with self.assertRaises(ValueError):
            self.ctx.normalize_outputs(
                (self.dataset,),
                output_spec={"a": None, "b": None},
                store=self.store,
            )

    def test_dict_outputs(self):
        result = self.ctx.normalize_outputs(
            {"a": self.dataset, "b": 1},
            output_spec={"a": None, "b": None},
            store=self.store,
        )

        self.assertIsInstance(result["a"], ArtifactRef)
        self.assertEqual(result["b"], 1)

    def test_dict_missing_key_raises(self):
        with self.assertRaises(ValueError):
            self.ctx.normalize_outputs(
                {"a": self.dataset},
                output_spec={"a": None, "b": None},
                store=self.store,
            )

    def test_invalid_return_type_raises(self):
        with self.assertRaises(TypeError):
            self.ctx.normalize_outputs(
                123,
                output_spec={"a": None, "b": None},
                store=self.store,
            )
