#!/usr/bin/env bash
# Collect today's postings, commit the data and push, at most once a day.
#
# This runs on a personal computer rather than in GitHub Actions because StuderendeOnline
# refuses requests from cloud servers. Pushing the data triggers the workflow that
# rebuilds and publishes the dashboard.
set -euo pipefail
cd "$(dirname "$0")/.."

today=$(TZ=Europe/Copenhagen date +%F)
git pull --rebase --quiet
if [ "$(sqlite3 data/jobs.db "SELECT COUNT(*) FROM runs WHERE run_date = '$today'" 2>/dev/null || echo 0)" != "0" ] \
   && [ "${1:-}" != "--force" ]; then
  echo "Already collected on $today"
  exit 0
fi

status=0
uv run cphjobs fetch --export data/export || status=$?

git add data
if ! git diff --cached --quiet; then
  git commit --quiet -m "Update data $today"
  git push --quiet
fi
exit $status
