"""Read a student list out of an .xlsx file.

Real spreadsheets from a college office are messy: a title, a blank row, a
department name, then the actual headers somewhere around row 7. So rather
than assuming the headers are on row 1, this finds them.
"""
from openpyxl import load_workbook

NAME_HEADERS = {"name", "student name", "student"}
ID_HEADERS = {"usn", "usr", "roll", "roll no", "roll number", "reg no", "id"}


class StudentFileError(ValueError):
    pass


def _norm(v):
    return str(v).strip().lower() if v is not None else ""


def find_header_row(ws, max_scan=30):
    """Return (row_number, {field: column_index}) for the first row that
    contains both a name column and an id column."""
    for r in range(1, min(ws.max_row, max_scan) + 1):
        cols = {}
        for c in range(1, ws.max_column + 1):
            h = _norm(ws.cell(row=r, column=c).value)
            if h in NAME_HEADERS and "name" not in cols:
                cols["name"] = c
            elif h in ID_HEADERS and "id" not in cols:
                cols["id"] = c
        if "name" in cols and "id" in cols:
            return r, cols
    raise StudentFileError(
        "could not find a header row containing both a name column "
        f"(one of {sorted(NAME_HEADERS)}) and an id column (one of {sorted(ID_HEADERS)})")


def read_students(path, sheet=None):
    """Return a list of {'name': ..., 'id': ...}, skipping blank rows."""
    wb = load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet else wb[wb.sheetnames[0]]

    header_row, cols = find_header_row(ws)
    students = []
    seen = set()
    for r in range(header_row + 1, ws.max_row + 1):
        name = ws.cell(row=r, column=cols["name"]).value
        sid = ws.cell(row=r, column=cols["id"]).value
        name = str(name).strip() if name is not None else ""
        sid = str(sid).strip() if sid is not None else ""
        if not name:
            continue
        if sid and sid in seen:
            raise StudentFileError(f"duplicate id {sid!r} on row {r}")
        if sid:
            seen.add(sid)
        students.append({"name": name, "id": sid, "row": r})

    if not students:
        raise StudentFileError("no students found below the header row")
    return students, ws.title
