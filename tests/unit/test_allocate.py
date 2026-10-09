"""Unit tests for the pure allocation logic.

No database, no Redis, no HTTP - these run in milliseconds and are what
the CI `unit` job executes.
"""
import pytest

from app.allocate import (
    BATCH_SIZE, AllocationError, assign_individual, into_batches, parse_csv, summarise,
)


def students(n):
    return [{"id": i, "name": f"Student {i:02d}", "usn": f"U{i:03d}"} for i in range(1, n + 1)]


def projects(n):
    return [{"id": i, "title": f"Project {i}"} for i in range(1, n + 1)]


class TestAssignIndividual:
    def test_every_student_gets_exactly_one_project(self):
        out = assign_individual(students(60), projects(25), seed=42)
        assert len(out) == 60
        assert len({a["student"]["id"] for a in out}) == 60

    def test_spread_is_even(self):
        """60 students over 25 projects must be 2 or 3 each - never 1 and 5."""
        out = assign_individual(students(60), projects(25), seed=42)
        counts = {}
        for a in out:
            counts[a["project"]["id"]] = counts.get(a["project"]["id"], 0) + 1
        assert max(counts.values()) - min(counts.values()) <= 1

    def test_all_projects_used_when_students_outnumber_them(self):
        out = assign_individual(students(60), projects(25), seed=1)
        assert len({a["project"]["id"] for a in out}) == 25

    def test_same_seed_is_reproducible(self):
        a = assign_individual(students(40), projects(25), seed=7)
        b = assign_individual(students(40), projects(25), seed=7)
        assert [(x["student"]["id"], x["project"]["id"]) for x in a] == \
               [(x["student"]["id"], x["project"]["id"]) for x in b]

    def test_different_seed_differs(self):
        a = assign_individual(students(40), projects(25), seed=7)
        b = assign_individual(students(40), projects(25), seed=8)
        assert [x["project"]["id"] for x in a] != [x["project"]["id"] for x in b]

    def test_positions_are_sequential_from_one(self):
        out = assign_individual(students(13), projects(25), seed=3)
        assert [a["position"] for a in out] == list(range(1, 14))

    def test_empty_roster_returns_nothing(self):
        assert assign_individual([], projects(25), seed=1) == []

    def test_no_projects_is_an_error(self):
        with pytest.raises(AllocationError, match="no projects"):
            assign_individual(students(5), [], seed=1)

    def test_fewer_students_than_projects(self):
        out = assign_individual(students(5), projects(25), seed=1)
        assert len(out) == 5
        assert len({a["project"]["id"] for a in out}) == 5


class TestIntoBatches:
    def test_exact_division(self):
        b = into_batches(list(range(60)), 5)
        assert len(b) == 12
        assert all(len(x) == 5 for x in b)

    def test_short_final_batch_is_kept_not_padded(self):
        b = into_batches(list(range(61)), 5)
        assert len(b) == 13
        assert len(b[-1]) == 1

    def test_default_batch_size(self):
        assert len(into_batches(list(range(10)))[0]) == BATCH_SIZE

    def test_nothing_is_lost(self):
        items = list(range(37))
        assert [x for b in into_batches(items, 5) for x in b] == items

    def test_zero_batch_size_is_an_error(self):
        with pytest.raises(AllocationError):
            into_batches([1, 2, 3], 0)


class TestSummarise:
    def test_counts(self):
        s = summarise(assign_individual(students(60), projects(25), seed=42))
        assert s["students"] == 60
        assert s["distinct_projects"] == 25
        assert s["batches"] == 12
        assert s["max_per_project"] - s["min_per_project"] <= 1

    def test_empty(self):
        s = summarise([])
        assert s["students"] == 0 and s["batches"] == 0


class TestParseCsv:
    def test_name_and_usn(self):
        assert parse_csv("AAKASH SINGH,24BTRIS001") == [
            {"name": "AAKASH SINGH", "usn": "24BTRIS001"}]

    def test_header_row_is_skipped(self):
        out = parse_csv("Name,USN\nASHA,U1\nVIKRAM,U2")
        assert len(out) == 2 and out[0]["name"] == "ASHA"

    def test_sno_name_usn_layout(self):
        out = parse_csv("SNO,Name,USN\n1,AAKASH SINGH,24BTRIS001")
        assert out == [{"name": "AAKASH SINGH", "usn": "24BTRIS001"}]

    def test_name_only(self):
        assert parse_csv("ASHA RAO")[0] == {"name": "ASHA RAO", "usn": ""}

    def test_tabs_work_too(self):
        assert parse_csv("ASHA\tU1")[0]["usn"] == "U1"

    def test_blank_lines_skipped(self):
        assert len(parse_csv("ASHA,U1\n\n  \nVIKRAM,U2")) == 2

    def test_quotes_stripped(self):
        assert parse_csv('"ASHA RAO","U1"')[0]["name"] == "ASHA RAO"

    def test_duplicate_usn_is_an_error(self):
        with pytest.raises(AllocationError, match="duplicate"):
            parse_csv("ASHA,U1\nVIKRAM,U1")

    def test_empty_input_is_an_error(self):
        with pytest.raises(AllocationError, match="no students"):
            parse_csv("   \n\n")
