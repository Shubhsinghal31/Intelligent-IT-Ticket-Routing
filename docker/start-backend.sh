#!/bin/sh
# Render start command for the backend service (see render.yaml's
# dockerCommand). A plain script file instead of an inline
# `sh -c "cmd1 && cmd2"` string in render.yaml, because Render's
# dockerCommand field does not reliably shell-parse quoted, &&-chained
# commands the way docker-compose.yml's `command:` field does locally —
# it was observed to try executing the entire literal string (quotes,
# &&, and all) as a single command name, failing with "not found"
# (exit 127). A script path has no spaces or shell metacharacters for
# Render to mis-tokenize, so this sidesteps the issue entirely.
#
# set -e: if the bootstrap step fails, stop here — don't start serving
# traffic against a database that might be half-migrated.
set -e

# Bootstrap the database (legacy migrations + alembic upgrade + seed
# data). Safe to run on every container start — see database/bootstrap.py's
# own docstring on idempotency; this is the same command
# docker/docker-compose.yml's backend service already runs for local dev.
python -m database.bootstrap

# exec (not a plain call) replaces this shell process with uvicorn
# instead of running it as a child process, so uvicorn receives signals
# (e.g. SIGTERM on deploy/restart) directly rather than the shell eating
# them.
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
