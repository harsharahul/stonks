#!/bin/bash
# Container entrypoint: wait for the database, bring the schema to head,
# seed an empty database, then hand off to the requested process.
set -e
python -m app.core.bootstrap
exec "$@"
