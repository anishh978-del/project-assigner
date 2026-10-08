# Project Assigner

Reads a student list from Excel, randomly puts students into groups, gives
each group a capstone project, and writes the result back out as Excel.

## Install and run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m assigner.cli "~/Downloads/ISE Student List.xlsx" --seed 42 -o out/assignments.xlsx
```

## Options

| Flag | Does |
|---|---|
| `-n, --group-size` | students per group (default 3) |
| `-s, --seed` | **use one.** Same seed = same allocation, so you can reproduce or defend it |
| `--sheet` | pick a sheet by name (default: the first) |
| `--cohort` | label for the output, e.g. `"3rd Year ISE"`. The sheet in the supplied file is labelled `2nd Year` but the cohort is third year, so set this. |
| `--set A` / `--set B` | limit to one half of the catalogue |
| `--starters-only` | only the projects that ship with a ready-made starter repo |
| `--no-repeats` | fail rather than give one project to two groups |
| `--dry-run` | print the allocation, write nothing |
| `--projects` | point at a different catalogue `.json` |

## Output

Three sheets:

- **Assignments** — one row per student: group, name, USN, project, language
- **Groups** — one row per group: members, project, whether a starter exists,
  and the project's *hard part*
- **Summary** — the seed, group size, source sheet and the counts, so the run
  is auditable afterwards

## Reading messy spreadsheets

College lists rarely have headers on row 1. The one this was built against
has a title, a department name, a blank row, and the real headers on **row 7**.

So the reader *searches* the first 30 rows for a row containing both a name
column and an id column, accepting `USN`, `USR`, `Roll No`, `Reg No` and so
on. It fails with a clear message rather than silently importing nothing.

It also refuses duplicate IDs, and skips rows with no name.

## Verified against the real list

```
source       : ISE Student List.xlsx, sheet "2nd Year" (mislabelled - cohort is 3rd year)
students     : 60      (no blanks, no duplicate USNs)
group size 3 : 20 groups, 20 distinct projects, 0 repeats
group size 4 : 15 groups, 15 distinct projects, 0 repeats
group size 2 : 30 groups - refuses with --no-repeats, since there are only 25 projects
--starters-only : 4 projects spread evenly, 5 groups each
```

## Where the logic lives

`assigner/allocate.py` is **pure** — no Excel, no file system, no printing.
That is the file worth unit testing, and the cases that matter are:

- an exact division (60 ÷ 3) versus an awkward one (61 ÷ 3)
- **nobody is ever left in a group alone** — leftovers join existing groups
  rather than forming a group of one
- the same seed always produces the same allocation
- more groups than projects wraps round evenly instead of running out
