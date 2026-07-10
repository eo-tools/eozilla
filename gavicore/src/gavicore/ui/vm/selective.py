#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from gavicore.models import Discriminator
from gavicore.ui.field.meta import FieldMeta
from gavicore.util.ensure import ensure_condition, ensure_type

from .base import ViewModel, ViewModelChangeEvent


class _InvDiscriminator:
    """
    An inverse discriminator that maps option indexes
    to the value of an original discriminator's mapping.
    """

    def __init__(self, name: str, mapping: dict[int, str]):
        self.name = name
        self.mapping = mapping

    @classmethod
    def from_discriminator(cls, discriminator: Discriminator, options: list[ViewModel]):
        mapping: dict[int, str] = {}
        if discriminator.mapping is None:
            for i, option in enumerate(options):
                mapping[i] = cls.require_option_ref(option).rsplit("/", maxsplit=1)[-1]
        else:
            for i, option in enumerate(options):
                o_ref: str = cls.require_option_ref(option)
                value: str | None = None
                for map_name, map_ref in discriminator.mapping.items():
                    if map_ref == o_ref:
                        value = map_name
                        break
                ensure_condition(
                    value is not None,
                    f"invalid discriminator mapping: "
                    f"missing value for reference {o_ref!r}",
                )
                assert value is not None
                mapping[i] = value
            no = len(options)
            nm = len(mapping)
            ensure_condition(
                no == nm,
                f"invalid discriminator mapping: "
                f"too {'many' if nm > no else 'few'} entries",
            )
        return _InvDiscriminator(discriminator.propertyName, mapping)

    @classmethod
    def require_option_ref(cls, option: ViewModel) -> str:
        option_ref = option.meta.ref
        ensure_condition(
            isinstance(option_ref, str),
            f"option {option.meta.name!r} should be a reference",
        )
        assert option_ref is not None
        return option_ref


class SelectiveViewModel(ViewModel[Any]):
    """
    A view model for values that are selected
    from a list of possible options.
    """

    def __init__(
        self,
        meta: FieldMeta,
        options: list[ViewModel],
        active_index: int = 0,
        discriminator: Discriminator | None = None,
    ):
        ensure_type("meta", meta, FieldMeta)
        ensure_type("options", options, list)
        ensure_type("active_index", active_index, int)
        ensure_condition(
            0 <= active_index < len(options),
            "active_index is out of bounds",
        )
        super().__init__(meta)
        self._options = list(options)
        self._active_index = active_index
        self._unwatch_options = [
            option.watch(self._on_option_change) for option in options
        ]
        if discriminator is not None:
            self._inv_discriminator = _InvDiscriminator.from_discriminator(
                discriminator, options
            )
        else:
            self._inv_discriminator = None

    @property
    def active_index(self) -> int:
        return self._active_index

    @active_index.setter
    def active_index(self, active_index: int) -> None:
        ensure_condition(
            0 <= active_index < len(self._options), "active_index out of bounds"
        )
        if active_index != self._active_index:
            self._active_index = active_index
            self._notify()

    def dispose(self):
        for unwatch_option in self._unwatch_options:
            unwatch_option()
        self._unwatch_options = []
        super().dispose()

    def _on_option_change(self, event: ViewModelChangeEvent) -> None:
        self._notify(*event.causes)

    def _get_value(self) -> Any:
        active_index = self._active_index
        assert 0 <= active_index < len(self._options)
        value = self._options[active_index].value
        discriminator = self._inv_discriminator
        if discriminator is not None and isinstance(value, dict):
            discriminator_value = discriminator.mapping[active_index]
            if value.get(discriminator.name) != discriminator_value:
                value = dict(value)
                value[discriminator.name] = discriminator_value
        return value

    def _set_value(self, value: Any) -> None:
        # Note, we expect that given value fits the option selected
        # by active index. This means this class does not and cannot
        # automatically set the right active index based on the value.
        self._options[self._active_index].value = value
