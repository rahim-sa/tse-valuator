import pytest

from tse_valuator.ingestion.label_mapper import (
    UnmappedLabelError,
    map_label,
    try_map_label,
)
from tse_valuator.ingestion.schema import LineItemKey


def test_known_label_maps_correctly():
    assert map_label("درآمدهاي عملياتي") == LineItemKey.REVENUE


def test_known_label_with_surrounding_whitespace():
    assert map_label("  درآمدهاي عملياتي  ") == LineItemKey.REVENUE


def test_unknown_label_raises_explicitly():
    with pytest.raises(UnmappedLabelError):
        map_label("یک برچسب کاملا ناشناخته")


def test_try_map_label_returns_none_for_unknown():
    assert try_map_label("یک برچسب کاملا ناشناخته") is None