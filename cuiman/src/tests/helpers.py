#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from enum import Enum
from types import NoneType
from typing import Any

import pydantic
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from s2gos_client.api.transport import AsyncTransport, Transport, TransportArgs


class MockTransport(AsyncTransport, Transport):  # pragma: no cover
    def __init__(self):
        self.calls: list[TransportArgs] = []
        self.async_calls: list[TransportArgs] = []
        self.closed = False
        self.id_counter = 0

    def new_id(self):
        self.id_counter += 1
        return f"ID-{self.id_counter}"

    def call(self, args: TransportArgs) -> Any:
        self.calls.append(args)
        return self._create_model_object(args)

    async def async_call(self, args: TransportArgs) -> Any:
        self.async_calls.append(args)
        return self._create_model_object(args)

    def _create_model_object(self, args: TransportArgs) -> Any:
        return_type = args.return_types.get("200", args.return_types.get("201"))
        return self.new_default_value(return_type) if return_type is not None else None

    def close(self):
        self.closed = True

    async def async_close(self):
        self.closed = True

    def new_default_value(self, t: type) -> Any:
        # args = get_args(t)
        # t = get_origin(t)
        defaults: dict[type, Any] = {
            Any: None,
            NoneType: None,
            bool: False,
            bytes: b"",
            dict: {},
            float: 0.0,
            int: 0,
            list: [],
            tuple: (),
            set: set(),
            str: "",
        }
        if t in defaults:
            return defaults[t]
        if inspect.isclass(t) and issubclass(t, Enum):
            return next(iter(t))
        if inspect.isclass(t) and issubclass(t, BaseModel):
            model_cls: type[pydantic.BaseModel] = t
            # noinspection PyTypeChecker
            fields: dict[str, FieldInfo] = model_cls.model_fields
            kwargs = {
                k: (
                    v.default
                    if v.default is not PydanticUndefined
                    else (
                        self.new_id()
                        if k == "id"
                        else (
                            v.default_factory()
                            if v.default_factory is not None
                            else self.new_default_value(v.annotation)
                        )
                    )
                )
                for k, v in fields.items()
            }
            return t(**kwargs)
        return t()
