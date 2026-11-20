-- Loaded by build-results.py (run from benchmarking/analysis/results/).

CREATE TABLE sources AS SELECT * FROM read_csv('sources.csv', header = true, types = {'date': 'VARCHAR'});

CREATE TABLE runs AS SELECT * FROM read_csv('runs.csv', header = true, types = {
  'date': 'VARCHAR', 'variant': 'VARCHAR', 'level': 'INTEGER', 'trains': 'INTEGER',
  'choices': 'BIGINT', 'conflicts': 'BIGINT', 'constraints': 'BIGINT', 'error': 'INTEGER',
  'mem': 'DOUBLE', 'memout': 'INTEGER', 'models': 'INTEGER', 'overall_time': 'DOUBLE',
  'par2': 'DOUBLE', 'restarts': 'BIGINT', 'rstatus': 'VARCHAR', 'rules': 'BIGINT',
  'solving_time': 'DOUBLE', 'status': 'VARCHAR', 'time': 'DOUBLE', 'timeout': 'INTEGER',
  'variables': 'BIGINT'});
UPDATE runs SET variant = '' WHERE variant IS NULL;
UPDATE sources SET variant = '' WHERE variant IS NULL;
-- Date folders are named YYYYMMDD.
ALTER TABLE runs ALTER date TYPE DATE USING strptime(date, '%Y%m%d');
ALTER TABLE sources ALTER date TYPE DATE USING strptime(date, '%Y%m%d');

-- `runs` plus derived columns. Use this for ad-hoc queries.
CREATE VIEW results AS
SELECT *,
       overall_time - solving_time AS grounding_time,
       rstatus = 'ok' AND status IN ('SATISFIABLE', 'UNSATISFIABLE') AS solved,
       CASE WHEN rstatus = 'ok' AND status IN ('SATISFIABLE', 'UNSATISFIABLE') THEN 'solved'
            WHEN rstatus = 'out of time' THEN 'timeout'
            WHEN rstatus = 'out of memory' THEN 'memout'
            WHEN rstatus LIKE 'signal%' THEN 'killed'
            ELSE 'other' END AS outcome
FROM runs;

-- One row per source spreadsheet and train count.
CREATE VIEW summary_by_trains AS
SELECT source, experiment, variant, date, system, trains,
       count(*)                                        AS n,
       count(*) FILTER (solved)                        AS solved,
       count(*) FILTER (outcome = 'timeout')           AS timeouts,
       count(*) FILTER (outcome = 'memout')            AS memouts,
       count(*) FILTER (outcome IN ('killed','other')) AS failed,
       round(median(time) FILTER (solved), 3)          AS median_time,
       round(avg(time) FILTER (solved), 3)             AS mean_time,
       round(avg(par2), 3)                             AS mean_par2,
       round(avg(grounding_time), 3)                   AS mean_grounding,
       round(avg(solving_time), 3)                     AS mean_solving,
       round(avg(rules))                               AS mean_rules,
       round(avg(variables))                           AS mean_variables,
       round(avg(constraints))                         AS mean_constraints,
       round(avg(mem))                                 AS mean_mem
FROM results
GROUP BY ALL;

-- One row per source spreadsheet.
CREATE VIEW summary AS
SELECT s.source, s.experiment, s.variant, s.date, s.system, s.timeout_limit,
       count(*) AS n, count(*) FILTER (solved) AS solved,
       count(*) FILTER (outcome = 'timeout') AS timeouts,
       count(*) FILTER (outcome = 'memout') AS memouts,
       round(sum(par2), 1) AS par2_sum,
       round(median(time) FILTER (solved), 3) AS median_time
FROM results r JOIN sources s USING (source)
GROUP BY ALL
ORDER BY s.date, s.experiment, s.variant;
