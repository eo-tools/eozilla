#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Generic, TypeVar

from .._util import UNDEFINED, UndefinedType
from ..fieldmeta import UIFieldMeta
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
        field_meta: UIFieldMeta,
        initial_value: Any | UndefinedType = UNDEFINED,
        non_nullable_view_model: ViewModel[T] | None = None,
    ):
        super().__init__(field_meta)
        if not field_meta.nullable:
            raise ValueError("field_meta must be nullable")
        if non_nullable_view_model is not None:
            if non_nullable_view_model.field_meta.nullable:
                raise ValueError("non_nullable_view_model must not be nullable")
            self._non_nullable = non_nullable_view_model
            self._non_nullable.watch(self._on_non_nullable_change)
        else:
            non_nullable_meta = field_meta.to_non_nullable()
            self._non_nullable = ViewModel.create(
                non_nullable_meta,
                (
                    non_nullable_meta.get_initial_value()
                    if initial_value is None or initial_value is UNDEFINED
                    else initial_value
                ),
            )
        self._is_null = initial_value is None

    @property
    def is_null(self) -> bool:
        return self._is_null

    @property
    def property_view_models(self) -> ViewModel:
        return self._non_nullable

    def _get_value(self) -> T | None:
        if self._is_null:
            return None
        return self._non_nullable._get_value()

    def _set_value(self, value: T | None) -> None:
        was_null = self._is_null
        if value is None:
            self._is_null = True
            if not was_null:
                self._notify()
        else:
            self._is_null = False
            with self.record_changes() as changes:
                self._non_nullable._set_value(value)
            if not changes and was_null:
                self._notify()

    def _on_non_nullable_change(self, event: ViewModelChangeEvent):
        self._notify(cause=event)
