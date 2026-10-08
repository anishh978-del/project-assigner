"""Command line entry point."""
import argparse
import json
import sys
from pathlib import Path

from .allocate import assign_projects, make_groups, summarise
from .reader import StudentFileError, read_students
from .writer import write_report

DEFAULT_PROJECTS = Path(__file__).resolve().parent.parent / "data" / "projects.json"


def build_parser():
    p = argparse.ArgumentParser(
        prog="assigner",
        description="Randomly assign capstone projects to students from an Excel list.")
    p.add_argument("students", help="path to the student list .xlsx")
    p.add_argument("-o", "--output", default="assignments.xlsx", help="output .xlsx")
    p.add_argument("-n", "--group-size", type=int, default=3, help="students per group (default 3)")
    p.add_argument("-s", "--seed", type=int, default=None,
                   help="random seed. Use one so the result can be reproduced.")
    p.add_argument("--sheet", default=None, help="sheet name (default: the first)")
    p.add_argument("--cohort", default=None,
                   help="label for the cohort, e.g. '3rd Year ISE'. Use this when the "
                        "sheet name in the source file is wrong or stale.")
    p.add_argument("--projects", default=str(DEFAULT_PROJECTS), help="project catalogue .json")
    p.add_argument("--set", choices=["A", "B"], default=None,
                   help="limit to one set of projects")
    p.add_argument("--starters-only", action="store_true",
                   help="only projects that ship with a ready-made starter repo")
    p.add_argument("--no-repeats", action="store_true",
                   help="fail rather than give the same project to two groups")
    p.add_argument("--dry-run", action="store_true", help="print, do not write a file")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        students, sheet = read_students(args.students, args.sheet)
    except (StudentFileError, FileNotFoundError) as e:
        print(f"error reading students: {e}", file=sys.stderr)
        return 2

    projects = json.loads(Path(args.projects).read_text())
    if args.set:
        projects = [p for p in projects if p["set"] == args.set]
    if args.starters_only:
        projects = [p for p in projects if p.get("starter")]
    if not projects:
        print("error: no projects left after filtering", file=sys.stderr)
        return 2

    groups = make_groups(students, args.group_size, args.seed)
    try:
        assignments = assign_projects(groups, projects, args.seed,
                                      allow_repeats=not args.no_repeats)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    summary = summarise(assignments)
    summary["seed"] = args.seed if args.seed is not None else "(not set - not reproducible)"
    summary["group_size"] = args.group_size
    summary["cohort"] = args.cohort or sheet
    summary["source_sheet"] = sheet

    for a in assignments:
        p = a["project"]
        print(f"  Group {a['group']:2d}  [{p['id']:2d}] {p['title'][:38]:38s} "
              f"{p['language'][:18]:18s} {', '.join(m['name'] for m in a['members'])}")
    print()
    for k, v in summary.items():
        print(f"  {k.replace('_',' '):18s} {v}")

    if args.dry_run:
        print("\n  (dry run - no file written)")
        return 0

    out = write_report(args.output, assignments, summary,
                       source_note=f"{Path(args.students).name} / sheet '{sheet}'")
    print(f"\n  written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
