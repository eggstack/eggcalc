"""Tests for deterministic temporal and cron utilities.

Covers ``eggcalc.exact.temporal`` (``datetime_convert``, ``cron_inspect``).

Static parity vectors are transcribed from the reviewed eggsact behavior
(upstream feature commit ``879570e``, corrective commit ``ae2be1d``, cron
semantics correction ``330e7a6``); the test suite does not shell out to
eggsact.
"""

from __future__ import annotations

import pytest

from eggcalc.exact.temporal import cron_inspect, datetime_convert


class TestDatetimeConvertEpoch:
    """Unix epoch and nanosecond floor semantics."""

    def test_zero_seconds_is_epoch(self):
        result = datetime_convert("0", "unix_seconds")
        assert result["rfc3339"] == "1970-01-01T00:00:00Z"
        assert result["utc_rfc3339"] == "1970-01-01T00:00:00Z"
        assert result["unix_seconds"] == "0"
        assert result["unix_milliseconds"] == "0"
        assert result["unix_nanoseconds"] == "0"
        assert result["offset_seconds"] == 0
        assert result["selected_offset"] == "Z"
        assert result["components"]["weekday"] == "THU"

    def test_minus_one_nanosecond_floor(self):
        result = datetime_convert("-1", "unix_nanoseconds")
        assert result["unix_nanoseconds"] == "-1"
        assert result["unix_seconds"] == "-1"
        assert result["unix_milliseconds"] == "-1"
        assert result["rfc3339"] == "1969-12-31T23:59:59.999999999Z"

    def test_plus_one_nanosecond(self):
        result = datetime_convert("1", "unix_nanoseconds")
        assert result["rfc3339"] == "1970-01-01T00:00:00.000000001Z"
        assert result["unix_seconds"] == "0"
        assert result["unix_milliseconds"] == "0"

    def test_millisecond_boundaries(self):
        before = datetime_convert("-1000000", "unix_nanoseconds")
        assert before["unix_seconds"] == "-1"
        assert before["unix_milliseconds"] == "-1"
        exact = datetime_convert("999999999", "unix_nanoseconds")
        assert exact["unix_seconds"] == "0"
        assert exact["unix_milliseconds"] == "999"
        second = datetime_convert("1000000000", "unix_nanoseconds")
        assert second["unix_seconds"] == "1"
        assert second["unix_milliseconds"] == "1000"
        assert second["rfc3339"] == "1970-01-01T00:00:01Z"

    def test_nine_digit_fraction_round_trip(self):
        result = datetime_convert("1970-01-01T00:00:00.123456789Z", "rfc3339")
        assert result["unix_nanoseconds"] == "123456789"
        assert result["rfc3339"] == "1970-01-01T00:00:00.123456789Z"
        assert result["components"]["nanosecond"] == 123456789

    def test_trailing_zeroes_trimmed_but_exact(self):
        result = datetime_convert("1970-01-01T00:00:00.100000000Z", "rfc3339")
        assert result["unix_nanoseconds"] == "100000000"
        assert result["rfc3339"] == "1970-01-01T00:00:00.1Z"
        reparsed = datetime_convert(result["rfc3339"], "rfc3339")
        assert reparsed["unix_nanoseconds"] == "100000000"


class TestDatetimeConvertOffsets:
    """Fixed-offset preservation and conversion."""

    def test_offset_conversion_to_z(self):
        result = datetime_convert("2026-09-03T11:00:00-04:00", "rfc3339")
        assert result["rfc3339"] == "2026-09-03T11:00:00-04:00"
        assert result["utc_rfc3339"] == "2026-09-03T15:00:00Z"
        assert result["offset_seconds"] == -14400
        assert result["selected_offset"] == "-04:00"

    def test_offset_override_to_z(self):
        result = datetime_convert("2026-09-03T11:00:00-04:00", "rfc3339", output_offset="Z")
        assert result["rfc3339"] == "2026-09-03T15:00:00Z"
        assert result["utc_rfc3339"] == "2026-09-03T15:00:00Z"
        assert result["offset_seconds"] == 0
        assert result["selected_offset"] == "Z"

    def test_unix_default_is_utc(self):
        result = datetime_convert("0", "unix_seconds")
        assert result["selected_offset"] == "Z"
        assert result["offset_seconds"] == 0

    def test_unix_output_offset(self):
        result = datetime_convert("0", "unix_seconds", output_offset="+05:30")
        assert result["rfc3339"] == "1970-01-01T05:30:00+05:30"
        assert result["utc_rfc3339"] == "1970-01-01T00:00:00Z"
        assert result["offset_seconds"] == 19800
        assert result["selected_offset"] == "+05:30"
        assert result["components"]["hour"] == 5
        assert result["components"]["minute"] == 30

    def test_zero_offset_canonicalizes_to_z(self):
        result = datetime_convert("2026-09-03T11:00:00Z", "rfc3339", output_offset="+00:00")
        assert result["selected_offset"] == "Z"
        assert result["rfc3339"] == "2026-09-03T11:00:00Z"

    @pytest.mark.parametrize("offset", ["+24:00", "-24:00", "+23:60", "UTC", "+0000"])
    def test_offset_bounds_rejected(self, offset: str):
        with pytest.raises(ValueError):
            datetime_convert("2026-09-03T11:00:00Z", "rfc3339", output_offset=offset)

    def test_invalid_rfc3339_offset_rejected(self):
        with pytest.raises(ValueError):
            datetime_convert("2026-09-03T11:00:00+24:00", "rfc3339")


class TestDatetimeConvertValidation:
    """Grammar, calendar, and range rejection."""

    @pytest.mark.parametrize(
        "value",
        [
            "2026-09-03T11:00:00",
            "2026-09-03 11:00:00Z",
            "2026/09/03T11:00:00Z",
            "2026-09-03T11:00:00.1234567890Z",
            "2026-09-03T11:00:00.Z",
            "2026-09-03T24:00:00Z",
            "2026-09-03T11:60:00Z",
            "2026-09-03T11:00:60Z",
            "2026-13-01T00:00:00Z",
            "2023-02-29T00:00:00Z",
            "2026-09-03T11:00:00+00:00:00",
            "2026-09-03t11:00:00z",
        ],
    )
    def test_invalid_rfc3339_rejected(self, value: str):
        with pytest.raises(ValueError):
            datetime_convert(value, "rfc3339")

    @pytest.mark.parametrize(
        "value",
        ["", "-", "+1", "1.0", "1e3", "1_0", " 1", "1 ", "0x1", "١٢٣"],
    )
    def test_invalid_unix_rejected(self, value: str):
        with pytest.raises(ValueError):
            datetime_convert(value, "unix_seconds")

    def test_unsupported_format_rejected(self):
        with pytest.raises(ValueError):
            datetime_convert("0", "unix_micros")  # type: ignore[arg-type]

    def test_leap_day_accepted(self):
        result = datetime_convert("2024-02-29T12:00:00Z", "rfc3339")
        assert result["components"]["day"] == 29
        assert result["components"]["month"] == 2

    def test_invalid_leap_day_rejected(self):
        with pytest.raises(ValueError):
            datetime_convert("2023-02-29T00:00:00Z", "rfc3339")

    def test_year_boundaries(self):
        first = datetime_convert("0001-01-01T00:00:00Z", "rfc3339")
        assert first["components"]["year"] == 1
        last = datetime_convert("9999-12-31T23:59:59.999999999Z", "rfc3339")
        assert last["components"]["year"] == 9999

    def test_year_zero_rejected(self):
        with pytest.raises(ValueError):
            datetime_convert("0000-01-01T00:00:00Z", "rfc3339")

    def test_non_string_rejected(self):
        with pytest.raises(ValueError):
            datetime_convert(0, "unix_seconds")  # type: ignore[arg-type]


class TestCronBasic:
    """Five-field grammar, names, lists, ranges, steps."""

    def test_weekday_schedule_after_thursday(self):
        result = cron_inspect("0 9 * * MON-FRI", "2026-09-03T12:00:00-04:00", count=1)
        assert result["next_runs"] == ["2026-09-04T09:00:00-04:00"]
        assert result["offset"] == "-04:00"
        assert result["offset_seconds"] == -14400
        assert result["satisfiable"] is True
        assert result["count"] == 1

    def test_names_case_insensitive(self):
        lower = cron_inspect("0 9 * * mon-fri", "2026-09-03T00:00:00Z", count=1)
        upper = cron_inspect("0 9 * * MON-FRI", "2026-09-03T00:00:00Z", count=1)
        assert lower["next_runs"] == upper["next_runs"]
        jan = cron_inspect("0 0 1 jan *", "2026-01-01T00:00:00Z", count=1)
        assert jan["next_runs"] == ["2027-01-01T00:00:00Z"]

    def test_sunday_zero_seven_equivalence(self):
        zero = cron_inspect("0 0 * * 0", "2026-09-06T00:00:00Z", count=2)
        seven = cron_inspect("0 0 * * 7", "2026-09-06T00:00:00Z", count=2)
        assert zero["parsed_values"]["day_of_week"] == [0]
        assert seven["parsed_values"]["day_of_week"] == [0]
        assert zero["next_runs"] == seven["next_runs"]

    def test_lists_ranges_steps(self):
        listed = cron_inspect("1,15,30 * * * *", "2026-09-03T00:00:00Z", count=3)
        assert listed["parsed_values"]["minute"] == [1, 15, 30]
        assert listed["next_runs"] == [
            "2026-09-03T00:01:00Z",
            "2026-09-03T00:15:00Z",
            "2026-09-03T00:30:00Z",
        ]
        stepped = cron_inspect("1-10/2 * * * *", "2026-09-03T00:00:00Z", count=1)
        assert stepped["parsed_values"]["minute"] == [1, 3, 5, 7, 9]
        quarter = cron_inspect("*/15 * * * *", "2026-09-03T00:00:00Z", count=2)
        assert quarter["parsed_values"]["minute"] == [0, 15, 30, 45]

    def test_single_stepped_start(self):
        result = cron_inspect("5/10 * * * *", "2026-09-03T00:00:00Z", count=1)
        assert result["parsed_values"]["minute"] == [5, 15, 25, 35, 45, 55]

    def test_strict_after_excludes_equal(self):
        result = cron_inspect("* * * * *", "2026-09-03T09:00:00Z", count=1)
        assert result["next_runs"] == ["2026-09-03T09:01:00Z"]
        nanos = cron_inspect("* * * * *", "2026-09-03T09:00:00.000000001Z", count=1)
        assert nanos["next_runs"] == ["2026-09-03T09:01:00Z"]

    def test_impossible_date_no_invalid_runs(self):
        result = cron_inspect("0 0 31 2 *", "2026-01-01T00:00:00Z", count=5)
        assert result["satisfiable"] is False
        assert result["next_runs"] == []
        assert result["count"] == 0

    @pytest.mark.parametrize(
        "expression",
        [
            "@daily",
            "@weekly",
            "* * * * * *",
            "* * * *",
            "CRON_TZ=UTC * * * * *",
            "TZ=UTC 0 9 * * *",
            "",
            "   ",
        ],
    )
    def test_alias_and_shape_rejected(self, expression: str):
        with pytest.raises(ValueError):
            cron_inspect(expression, "2026-09-03T00:00:00Z")

    @pytest.mark.parametrize(
        "expression",
        [
            "0 0 * * FRI-MON",
            "5-2 * * * *",
            "* * * DEC-JAN *",
        ],
    )
    def test_wrapping_ranges_rejected(self, expression: str):
        with pytest.raises(ValueError):
            cron_inspect(expression, "2026-09-03T00:00:00Z")

    @pytest.mark.parametrize(
        "expression",
        [
            "*/0 * * * *",
            "5//2 * * * *",
            "1,,2 * * * *",
            "60 * * * *",
            "* 24 * * *",
            "* * 0 * *",
            "* * * 13 *",
            "* * * * 8",
        ],
    )
    def test_invalid_fields_rejected(self, expression: str):
        with pytest.raises(ValueError):
            cron_inspect(expression, "2026-09-03T00:00:00Z")

    def test_count_bounds(self):
        assert cron_inspect("* * * * *", "2026-09-03T00:00:00Z", count=1)["count"] == 1
        assert cron_inspect("* * * * *", "2026-09-03T00:00:00Z", count=32)["count"] == 32
        with pytest.raises(ValueError):
            cron_inspect("* * * * *", "2026-09-03T00:00:00Z", count=0)
        with pytest.raises(ValueError):
            cron_inspect("* * * * *", "2026-09-03T00:00:00Z", count=33)

    def test_upper_bound_fails_cleanly(self):
        with pytest.raises(ValueError):
            cron_inspect("* * * * *", "9999-12-31T23:59:00Z", count=5)


class TestCronDomDowStarSyntax:
    """Corrected Vixie/Cronie DOM/DOW star-syntax semantics."""

    def test_star_dom_and_named_dow_is_and(self):
        result = cron_inspect("0 0 * * MON", "2026-09-03T00:00:00Z", count=2)
        assert result["next_runs"] == ["2026-09-07T00:00:00Z", "2026-09-14T00:00:00Z"]

    def test_named_dom_and_star_dow_is_and(self):
        result = cron_inspect("0 0 1 * *", "2026-09-03T00:00:00Z", count=2)
        assert result["next_runs"] == ["2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z"]

    def test_neither_star_is_or(self):
        result = cron_inspect("0 0 1 * MON", "2026-09-03T00:00:00Z", count=5)
        assert result["next_runs"][0] == "2026-09-07T00:00:00Z"
        assert "2026-10-01T00:00:00Z" in result["next_runs"]

    def test_explicit_full_range_is_not_star(self):
        result = cron_inspect("0 0 1-31 * MON", "2026-09-03T00:00:00Z", count=2)
        assert result["next_runs"] == ["2026-09-04T00:00:00Z", "2026-09-05T00:00:00Z"]

    def test_star_slash_one_retains_star(self):
        result = cron_inspect("0 0 */1 * MON", "2026-09-03T00:00:00Z", count=2)
        assert result["next_runs"] == ["2026-09-07T00:00:00Z", "2026-09-14T00:00:00Z"]

    def test_star_slash_two_requires_both(self):
        result = cron_inspect("0 0 */2 * MON", "2026-09-03T00:00:00Z", count=2)
        assert result["next_runs"] == ["2026-09-07T00:00:00Z", "2026-09-21T00:00:00Z"]

    def test_star_dow_with_named_dom_is_and(self):
        result = cron_inspect("0 0 1 * */1", "2026-09-03T00:00:00Z", count=2)
        assert result["next_runs"] == ["2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z"]


class TestCronOutputShape:
    """Normalized expression, parsed values, and count semantics."""

    def test_normalized_expression_expands(self):
        result = cron_inspect("0 9 * * MON-FRI", "2026-09-03T00:00:00Z", count=1)
        assert result["expression"] == "0 9 * * MON-FRI"
        assert result["parsed_values"]["minute"] == [0]
        assert result["parsed_values"]["hour"] == [9]
        assert result["parsed_values"]["day_of_week"] == [1, 2, 3, 4, 5]
        assert result["normalized_expression"].startswith("0 9 ")
        assert "1,2,3" in result["normalized_expression"]

    def test_count_is_actual(self):
        empty = cron_inspect("0 0 31 2 *", "2026-01-01T00:00:00Z", count=5)
        assert empty["count"] == len(empty["next_runs"]) == 0


class TestExactLazyExports:
    """Temporal utilities are available through the lazy exact surface."""

    def test_lazy_imports(self):
        import eggcalc.exact as exact

        assert callable(exact.datetime_convert)
        assert callable(exact.cron_inspect)
        assert exact.datetime_convert("0", "unix_seconds")["rfc3339"] == ("1970-01-01T00:00:00Z")
        assert (
            exact.cron_inspect("0 9 * * MON-FRI", "2026-09-03T00:00:00Z", count=1)["satisfiable"]
            is True
        )
