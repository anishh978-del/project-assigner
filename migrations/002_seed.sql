-- A demo cohort so the app works the moment it starts, with no real names.
INSERT INTO cohorts (id, label) VALUES (1, 'Demo Cohort (examples)')
ON CONFLICT DO NOTHING;
SELECT setval('cohorts_id_seq', GREATEST((SELECT MAX(id) FROM cohorts), 1));

INSERT INTO students (cohort_id, name, usn)
SELECT 1, 'Example Student ' || lpad(g::text, 2, '0'), '00DEMO' || lpad(g::text, 3, '0')
FROM generate_series(1, 20) AS g
ON CONFLICT DO NOTHING;
