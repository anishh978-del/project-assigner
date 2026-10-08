"""Pure allocation logic.

No Excel, no file system, no printing. Every function here takes plain data
and returns plain data, which makes this the file to unit test.

Two guarantees the tests should pin down:
  1. given the same seed, the same input always produces the same output
  2. nobody is ever left in a group on their own
"""
import random


class AllocationError(ValueError):
    pass


def make_groups(students, size=3, seed=None):
    """Shuffle students and split them into groups of roughly `size`.

    The remainder is the interesting part. 60 students in 3s divides evenly,
    but 61 does not - and the wrong answer is a final group of one. Leftover
    students are spread across the existing groups instead, so a group may
    end up with size+1, but never with a single person.
    """
    if size < 2:
        raise AllocationError("group size must be at least 2")
    students = list(students)
    if not students:
        return []
    if len(students) < size:
        return [students]

    rng = random.Random(seed)
    shuffled = students[:]
    rng.shuffle(shuffled)

    count = len(shuffled) // size
    groups = [shuffled[i * size:(i + 1) * size] for i in range(count)]

    # hand the leftovers out one at a time rather than making a tiny group
    for idx, student in enumerate(shuffled[count * size:]):
        groups[idx % len(groups)].append(student)

    return groups


def assign_projects(groups, projects, seed=None, allow_repeats=True):
    """Give each group a project.

    Projects are used up before any is repeated, so with 20 groups and 25
    projects every group gets something different. With more groups than
    projects the list simply wraps round, which keeps repeats even.
    """
    if not projects:
        raise AllocationError("no projects to assign")
    if len(groups) > len(projects) and not allow_repeats:
        raise AllocationError(
            f"{len(groups)} groups but only {len(projects)} projects; "
            "either raise the group size or allow repeats")

    rng = random.Random(seed)
    pool = list(projects)
    rng.shuffle(pool)

    out = []
    for i, group in enumerate(groups):
        out.append({"group": i + 1, "members": group, "project": pool[i % len(pool)]})
    return out


def summarise(assignments):
    """Counts worth printing, and worth asserting in a test."""
    used = {}
    for a in assignments:
        key = a["project"]["id"]
        used[key] = used.get(key, 0) + 1
    sizes = [len(a["members"]) for a in assignments]
    return {
        "groups": len(assignments),
        "students": sum(sizes),
        "smallest_group": min(sizes) if sizes else 0,
        "largest_group": max(sizes) if sizes else 0,
        "distinct_projects": len(used),
        "most_repeated": max(used.values()) if used else 0,
    }
