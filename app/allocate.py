"""Pure allocation logic.

One capstone per student. No groups - a student cannot team up with friends
to get an easier project, because there are no teams.

No database, no HTTP, no printing. Everything here takes plain data and
returns plain data, which makes it the file to unit test.

Guarantees worth pinning down in tests:
  1. every student gets exactly one project
  2. projects are spread as evenly as possible - with 60 students and 25
     projects, no project is used 4 times while another is used once
  3. the same seed always produces the same allocation
"""
import math
import random

BATCH_SIZE = 5


class AllocationError(ValueError):
    pass


def assign_individual(students, projects, seed=None):
    """Give every student exactly one project.

    Both lists are shuffled, then projects are handed out round-robin. That
    keeps the spread even: with N students and P projects every project is
    used either floor(N/P) or ceil(N/P) times, never more lopsided than that.
    """
    if not students:
        return []
    if not projects:
        raise AllocationError("no projects to assign")

    rng = random.Random(seed)
    roster = list(students)
    pool = list(projects)
    rng.shuffle(roster)
    rng.shuffle(pool)

    return [{"position": i + 1, "student": s, "project": pool[i % len(pool)]}
            for i, s in enumerate(roster)]


def into_batches(assignments, size=BATCH_SIZE):
    """Split the allocation into reveal batches - 5 students per spin.

    The final batch may be short. It is never padded and never merged,
    so the batch numbers stay predictable.
    """
    if size < 1:
        raise AllocationError("batch size must be at least 1")
    return [assignments[i:i + size] for i in range(0, len(assignments), size)]


def summarise(assignments):
    used = {}
    for a in assignments:
        pid = a["project"]["id"]
        used[pid] = used.get(pid, 0) + 1
    counts = list(used.values())
    return {
        "students": len(assignments),
        "distinct_projects": len(used),
        "batches": math.ceil(len(assignments) / BATCH_SIZE) if assignments else 0,
        "min_per_project": min(counts) if counts else 0,
        "max_per_project": max(counts) if counts else 0,
    }


def parse_csv(text):
    """Read a pasted or uploaded CSV/TSV roster.

    Accepts a header row or none, comma or tab separated, and either
    'name' alone or 'name,usn' in either column order where the USN is
    recognisable. Blank lines are skipped.
    """
    rows = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip().strip('"') for p in line.replace("\t", ",").split(",")]
        parts = [p for p in parts if p]
        if not parts:
            continue
        low = [p.lower() for p in parts]
        if low[0] in ("name", "student name", "student", "sno", "s.no", "sl no"):
            continue  # header row
        if len(parts) == 1:
            name, usn = parts[0], ""
        elif parts[0].isdigit() and len(parts) >= 3:
            name, usn = parts[1], parts[2]      # SNO, Name, USN
        elif parts[0].isdigit() and len(parts) == 2:
            name, usn = parts[1], ""            # SNO, Name
        else:
            name, usn = parts[0], parts[1]
        if not name:
            continue
        if usn and usn in seen:
            raise AllocationError(f"duplicate USN in the file: {usn}")
        if usn:
            seen.add(usn)
        rows.append({"name": name, "usn": usn})
    if not rows:
        raise AllocationError("no students found in that file")
    return rows
