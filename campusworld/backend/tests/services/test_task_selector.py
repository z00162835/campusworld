"""Phase B PR3: scope_selector DSL validator (F01 §4)."""

from __future__ import annotations

import pytest

from app.services.task.errors import (
    EmptySelector,
    SelectorBoundsExceeded,
    UnknownTraitClass,
    UnknownTraitMaskName,
)
from app.services.task.selector import enforce_bounds, validate_selector


@pytest.mark.unit
def test_minimal_valid_selector_with_trait_class_only():
    dsl = {
        "_schema_version": 1,
        "include": [{"trait_class": "DEVICE"}],
    }
    res = validate_selector(dsl)
    assert res.schema_version == 1
    assert res.bounds == {"min": 0, "max": 10000}
    assert len(res.include) == 1


@pytest.mark.unit
def test_default_schema_version_one_when_omitted():
    res = validate_selector({"include": [{"trait_class": "DEVICE"}]})
    assert res.schema_version == 1


@pytest.mark.unit
def test_unsupported_schema_version_rejected():
    with pytest.raises(EmptySelector):
        validate_selector({"_schema_version": 99, "include": [{"trait_class": "DEVICE"}]})


@pytest.mark.unit
def test_empty_include_without_pinned_targets_rejected():
    with pytest.raises(EmptySelector):
        validate_selector({"_schema_version": 1, "include": []})


@pytest.mark.unit
def test_empty_include_allowed_when_pinned_targets_provided():
    res = validate_selector({"_schema_version": 1, "include": []}, allow_empty_include=True)
    assert res.include == []


@pytest.mark.unit
def test_unknown_trait_class_rejected():
    with pytest.raises(UnknownTraitClass):
        validate_selector(
            {
                "_schema_version": 1,
                "include": [{"trait_class": "FAKE_NOT_REAL"}],
            }
        )


@pytest.mark.unit
def test_known_trait_class_task_accepted():
    """PR1 added trait_class=TASK; selector validator must accept it."""
    res = validate_selector({"_schema_version": 1, "include": [{"trait_class": "TASK"}]})
    assert res.include == [{"trait_class": "TASK"}]


@pytest.mark.unit
def test_unknown_trait_mask_name_rejected():
    with pytest.raises(UnknownTraitMaskName):
        validate_selector(
            {
                "_schema_version": 1,
                "include": [
                    {
                        "trait_class": "DEVICE",
                        "trait_mask_any_of": ["NOT_A_REAL_MASK"],
                    }
                ],
            }
        )


@pytest.mark.unit
def test_known_trait_mask_names_accepted():
    res = validate_selector(
        {
            "_schema_version": 1,
            "include": [
                {
                    "trait_class": "DEVICE",
                    "trait_mask_any_of": ["FACTUAL", "PERCEPTUAL"],
                    "trait_mask_all_of": ["CONCEPTUAL"],
                }
            ],
        }
    )
    assert res.include[0]["trait_mask_any_of"] == ["FACTUAL", "PERCEPTUAL"]


@pytest.mark.unit
def test_bounds_default_when_omitted():
    res = validate_selector({"_schema_version": 1, "include": [{"trait_class": "DEVICE"}]})
    assert res.bounds == {"min": 0, "max": 10000}


@pytest.mark.unit
def test_bounds_partial_override_keeps_other_default():
    res = validate_selector(
        {
            "_schema_version": 1,
            "bounds": {"max": 50},
            "include": [{"trait_class": "DEVICE"}],
        }
    )
    assert res.bounds == {"min": 0, "max": 50}


@pytest.mark.unit
def test_bounds_invalid_min_negative_rejected():
    with pytest.raises(EmptySelector):
        validate_selector(
            {
                "_schema_version": 1,
                "bounds": {"min": -1},
                "include": [{"trait_class": "DEVICE"}],
            }
        )


@pytest.mark.unit
def test_bounds_min_greater_than_max_rejected():
    with pytest.raises(EmptySelector):
        validate_selector(
            {
                "_schema_version": 1,
                "bounds": {"min": 50, "max": 10},
                "include": [{"trait_class": "DEVICE"}],
            }
        )


@pytest.mark.unit
def test_enforce_bounds_below_min_raises():
    res = validate_selector(
        {
            "_schema_version": 1,
            "bounds": {"min": 1, "max": 10},
            "include": [{"trait_class": "DEVICE"}],
        }
    )
    with pytest.raises(SelectorBoundsExceeded) as ei:
        enforce_bounds(res, actual_count=0)
    assert ei.value.reason == "min"


@pytest.mark.unit
def test_enforce_bounds_above_max_raises():
    res = validate_selector(
        {
            "_schema_version": 1,
            "bounds": {"min": 0, "max": 10},
            "include": [{"trait_class": "DEVICE"}],
        }
    )
    with pytest.raises(SelectorBoundsExceeded) as ei:
        enforce_bounds(res, actual_count=11)
    assert ei.value.reason == "max"


@pytest.mark.unit
def test_enforce_bounds_within_range_passes():
    res = validate_selector(
        {
            "_schema_version": 1,
            "bounds": {"min": 0, "max": 10},
            "include": [{"trait_class": "DEVICE"}],
        }
    )
    enforce_bounds(res, actual_count=5)


@pytest.mark.unit
def test_anchor_ref_must_coerce_to_int():
    with pytest.raises(EmptySelector):
        validate_selector(
            {
                "_schema_version": 1,
                "anchor_ref": "not-an-int",
                "include": [{"trait_class": "DEVICE"}],
            }
        )


@pytest.mark.unit
def test_non_dict_input_raises_empty_selector():
    with pytest.raises(EmptySelector):
        validate_selector(None)
    with pytest.raises(EmptySelector):
        validate_selector("not-a-dict")  # type: ignore[arg-type]
