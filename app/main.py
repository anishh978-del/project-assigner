import csv
import io
import json
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import cache, db
from .allocate import (
    BATCH_SIZE, AllocationError, assign_individual, into_batches, parse_csv, summarise,
)

HERE = Path(__file__).resolve().parent
PROJECTS = json.loads((HERE / "projects.json").read_text())

app = FastAPI(title="project-assigner")


@app.get("/api/health")
def health():
    out = {"status": "ok", "postgres": False, "redis": False}
    try:
        db.query("SELECT 1")
        out["postgres"] = True
    except Exception as exc:
        out["pg_error"] = str(exc)
    try:
        cache.client().ping()
        out["redis"] = True
    except Exception as exc:
        out["redis_error"] = str(exc)
    return out if (out["postgres"] and out["redis"]) else JSONResponse(out, status_code=503)


@app.get("/api/projects")
def projects():
    hit = cache.get_json("projects")
    if hit:
        return {"projects": hit, "cached": True}
    cache.set_json("projects", PROJECTS, ttl=86400)
    return {"projects": PROJECTS, "cached": False}


def _pool(name):
    if name in ("A", "B"):
        return [p for p in PROJECTS if p["set"] == name]
    if name == "starter":
        return [p for p in PROJECTS if p.get("starter")]
    return list(PROJECTS)


# ---------------------------- cohorts -----------------------------
@app.get("/api/cohorts")
def list_cohorts():
    return {"cohorts": db.query(
        "SELECT c.id, c.label,"
        " (SELECT count(*) FROM students s WHERE s.cohort_id = c.id) AS students"
        " FROM cohorts c ORDER BY c.id DESC")}


def _store_cohort(label, roster):
    row = db.one("INSERT INTO cohorts (label) VALUES (%s) RETURNING id", (label,))
    cid = row["id"]
    with db.connect() as conn, conn.cursor() as cur:
        for s in roster:
            cur.execute("INSERT INTO students (cohort_id, name, usn) VALUES (%s,%s,%s)",
                        (cid, s["name"], s["usn"] or None))
    return {"id": cid, "label": label, "students": len(roster)}


@app.post("/api/cohorts/upload", status_code=201)
async def upload_cohort(file: UploadFile):
    """Upload the class list as CSV. This is how a cohort gets in."""
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    try:
        roster = parse_csv(raw)
    except AllocationError as exc:
        raise HTTPException(400, str(exc))
    return _store_cohort(file.filename or "Uploaded CSV", roster)


@app.post("/api/cohorts", status_code=201)
def paste_cohort(payload: dict = Body(...)):
    try:
        roster = parse_csv(payload.get("text", ""))
    except AllocationError as exc:
        raise HTTPException(400, str(exc))
    return _store_cohort(str(payload.get("label", "Pasted roster")).strip() or "Pasted roster",
                         roster)


# ------------------------------ runs ------------------------------
@app.post("/api/runs", status_code=201)
def create_run(payload: dict = Body(...)):
    cohort_id = payload.get("cohort_id")
    seed = int(payload.get("seed", 42))
    pool_name = payload.get("pool", "all")
    batch = int(payload.get("batch_size", BATCH_SIZE))

    students = db.query("SELECT id, name, usn FROM students WHERE cohort_id = %s ORDER BY id",
                        (cohort_id,))
    if not students:
        raise HTTPException(404, "no such cohort, or it has no students")

    pool = _pool(pool_name)
    if not pool:
        raise HTTPException(400, f"pool {pool_name!r} is empty")

    try:
        allocation = assign_individual([dict(s) for s in students], pool, seed)
    except AllocationError as exc:
        raise HTTPException(400, str(exc))

    batches = into_batches(allocation, batch)
    run = db.one("INSERT INTO runs (cohort_id, seed, pool, batch_size)"
                 " VALUES (%s,%s,%s,%s) RETURNING id",
                 (cohort_id, seed, pool_name, batch))
    run_id = run["id"]

    with db.connect() as conn, conn.cursor() as cur:
        for bno, group in enumerate(batches, start=1):
            for a in group:
                cur.execute(
                    "INSERT INTO assignments"
                    " (run_id, student_id, position, batch_no, project_id, project_title)"
                    " VALUES (%s,%s,%s,%s,%s,%s)",
                    (run_id, a["student"]["id"], a["position"], bno,
                     a["project"]["id"], a["project"]["title"]))

    cache.reset_reveals(run_id)
    return {"run_id": run_id, "seed": seed, "pool": pool_name, "batch_size": batch,
            **summarise(allocation)}


@app.get("/api/runs")
def list_runs():
    return {"runs": db.query(
        "SELECT r.id, c.label, r.seed, r.pool, r.batch_size,"
        " (SELECT count(*) FROM assignments a WHERE a.run_id = r.id) AS students,"
        " (SELECT count(*) FROM assignments a WHERE a.run_id = r.id AND a.revealed) AS revealed"
        " FROM runs r JOIN cohorts c ON c.id = r.cohort_id ORDER BY r.id DESC")}


@app.get("/api/runs/{run_id}")
def get_run(run_id: int):
    meta = db.one("SELECT id, cohort_id, seed, pool, batch_size FROM runs WHERE id = %s",
                  (run_id,))
    if not meta:
        raise HTTPException(404, "no such run")
    rows = db.query(
        "SELECT a.position, a.batch_no, a.project_id, a.project_title, a.revealed,"
        " s.name, s.usn FROM assignments a JOIN students s ON s.id = a.student_id"
        " WHERE a.run_id = %s ORDER BY a.position", (run_id,))
    done = db.one("SELECT count(*) AS n FROM assignments WHERE run_id = %s AND revealed",
                  (run_id,))
    return {"run": meta, "assignments": rows, "revealed": done["n"], "total": len(rows)}


@app.post("/api/runs/{run_id}/reveal")
def reveal_next_batch(run_id: int):
    """Reveal the next batch - five students per pull of the lever."""
    nxt = db.one("SELECT min(batch_no) AS b FROM assignments"
                 " WHERE run_id = %s AND NOT revealed", (run_id,))
    if not nxt or nxt["b"] is None:
        total = db.one("SELECT count(*) AS n FROM assignments WHERE run_id = %s", (run_id,))
        if not total or total["n"] == 0:
            raise HTTPException(404, "no such run")
        return JSONResponse({"done": True, "message": "every student has been assigned"},
                            status_code=409)

    bno = nxt["b"]
    db.query("UPDATE assignments SET revealed = TRUE, revealed_at = now()"
             " WHERE run_id = %s AND batch_no = %s", (run_id, bno), fetch=False)
    cache.incr_reveal(run_id)

    rows = db.query(
        "SELECT a.position, a.project_id, a.project_title, s.name, s.usn"
        " FROM assignments a JOIN students s ON s.id = a.student_id"
        " WHERE a.run_id = %s AND a.batch_no = %s ORDER BY a.position", (run_id, bno))
    by_id = {p["id"]: p for p in PROJECTS}
    revealed = [{**dict(r), "project": by_id.get(r["project_id"])} for r in rows]
    left = db.one("SELECT count(DISTINCT batch_no) AS n FROM assignments"
                  " WHERE run_id = %s AND NOT revealed", (run_id,))
    return {"done": False, "batch": bno, "students": revealed, "batches_remaining": left["n"]}


@app.post("/api/runs/{run_id}/reset")
def reset_run(run_id: int):
    db.query("UPDATE assignments SET revealed = FALSE, revealed_at = NULL WHERE run_id = %s",
             (run_id,), fetch=False)
    cache.reset_reveals(run_id)
    return {"run_id": run_id, "reset": True}


@app.get("/api/runs/{run_id}/export.csv")
def export_csv(run_id: int):
    """A real CSV download, for sharing with the class afterwards."""
    rows = db.query(
        "SELECT a.position, s.name, s.usn, a.project_id, a.project_title, a.revealed"
        " FROM assignments a JOIN students s ON s.id = a.student_id"
        " WHERE a.run_id = %s ORDER BY a.position", (run_id,))
    if not rows:
        raise HTTPException(404, "no such run")

    by_id = {p["id"]: p for p in PROJECTS}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Position", "Name", "USN", "Project #", "Project", "Set",
                "Language", "Starter repo", "Revealed"])
    for r in rows:
        p = by_id.get(r["project_id"], {})
        w.writerow([r["position"], r["name"], r["usn"] or "", r["project_id"],
                    r["project_title"], p.get("set", ""), p.get("language", ""),
                    "yes" if p.get("starter") else "no",
                    "yes" if r["revealed"] else "no"])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="assignments-run-{run_id}.csv"'})


STATIC = HERE / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC / "index.html"))
