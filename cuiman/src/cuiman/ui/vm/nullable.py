#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Generic, TypeVar

from gavicore.util.undefined import UNDEFINED, UndefinedType

from ..field.meta import FieldMeta
from .base import ViewModel, ViewModelChangeEvent

K = TypeVar("K", bound=str | int)
T = TypeVar("T", bound=dict[str, Any] | list[Any])
NoneType = type(None)


class NullableViewModel(Generic[T], ViewModel[T | None]):
    """
    A view model used to represent a nullable value.
    """

    def __init__(
        self,
        meta: FieldMeta,
        *,
        value: Any | UndefinedType = UNDEFINED,
        inner: ViewModel[T] | None = None,
    ):
        super().__init__(meta)
        if not meta.nullable:
            raise ValueError("meta must be nullable")
        if inner is not None:
            if inner.meta.nullable:
                raise ValueError("inner view model must not be nullable")
            self._inner = inner
            self._inner.watch(self._on_inner_change)
        else:
            non_nullable_meta = meta.to_non_nullable()
            self._inner = self.create(
                non_nullable_meta,
                value=(
                    non_nullable_meta.get_initial_value()
                    if value is None or not UndefinedType.is_defined(value)
                    else value
                ),
            )
        self._is_null = (
            value is None if UndefinedType.is_defined(value) else meta.default is None
        )

    @property
    def is_null(self) -> bool:
        return self._is_null

    @property
    def inner(self) -> ViewModel:
        return self._inner

    def _get_value(self) -> T | None:
        if self._is_null:
            return None
        return self._inner._get_value()

    def _set_value(self, value: T | None) -> None:
        was_null = self._is_null
        if value is None:
            self._is_null = True
            if not was_null:
                self._notify()
        else:
            self._is_null = False
            with self.intercept_changes() as changes:
                self._inner._set_value(value)
            if changes or was_null:
                self._notify(*changes)

    def _on_inner_change(self, event: ViewModelChangeEvent):
        self._notify(event)
