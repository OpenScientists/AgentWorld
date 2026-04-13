from __future__ import annotations

from typing import Any, Callable

Reducer = Callable[[Any, Any], Any]


def last_value(_: Any, new_value: Any) -> Any:
    return new_value


def append_list(current: Any, new_value: Any) -> list[Any]:
    items = list(current or [])
    if new_value is None:
        return items
    if isinstance(new_value, list):
        return items + new_value
    return items + [new_value]


def merge_dict(current: Any, new_value: Any) -> dict[str, Any]:
    merged = dict(current or {})
    if new_value:
        merged.update(dict(new_value))
    return merged


def merge_state(
    state: dict[str, Any],
    patch: dict[str, Any],
    reducers: dict[str, Reducer],
) -> dict[str, Any]:
    merged = dict(state)
    for key, value in patch.items():
        if key in merged and key in reducers:
            merged[key] = reducers[key](merged[key], value)
        else:
            merged[key] = value
    return merged
