-- A cohort of students, uploaded from a CSV.
CREATE TABLE IF NOT EXISTS cohorts (
    id         SERIAL PRIMARY KEY,
    label      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS students (
    id        SERIAL PRIMARY KEY,
    cohort_id INT  NOT NULL REFERENCES cohorts(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    usn       TEXT,
    UNIQUE (cohort_id, usn)
);

-- One allocation of the whole cohort. The seed is stored so the run can be
-- reproduced later and defended if a student says they were singled out.
CREATE TABLE IF NOT EXISTS runs (
    id         SERIAL PRIMARY KEY,
    cohort_id  INT  NOT NULL REFERENCES cohorts(id) ON DELETE CASCADE,
    seed       INT  NOT NULL,
    pool       TEXT NOT NULL DEFAULT 'all',
    batch_size INT  NOT NULL DEFAULT 5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ONE ROW PER STUDENT. There are no groups: a student is assigned a project
-- individually, so nobody can arrange themselves into a team to get an
-- easier one.
CREATE TABLE IF NOT EXISTS assignments (
    id            SERIAL PRIMARY KEY,
    run_id        INT  NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    student_id    INT  NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    position      INT  NOT NULL,
    batch_no      INT  NOT NULL,
    project_id    INT  NOT NULL,
    project_title TEXT NOT NULL,
    revealed      BOOLEAN NOT NULL DEFAULT FALSE,
    revealed_at   TIMESTAMPTZ,
    UNIQUE (run_id, student_id)
);

CREATE INDEX IF NOT EXISTS students_cohort ON students (cohort_id);
CREATE INDEX IF NOT EXISTS assignments_batch ON assignments (run_id, batch_no, position);
