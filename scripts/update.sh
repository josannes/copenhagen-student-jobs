#!/usr/bin/env bash
# Collect today's postings, commit the data and push. Safe to run every hour: it collects
# at most once a day and stays quiet while offline.
#
# This runs on a personal computer rather than in GitHub Actions because StuderendeOnline
# refuses requests from cloud servers. Pushing the data triggers the workflow that
# rebuilds and publishes the dashboard. Run it from a clone used only for this, so it
# never touches work in progress.
#
#   scripts/update.sh            normal run
#   scripts/update.sh --force    collect again even if today is already collected
#
# Environment:
#   CPHJOBS_LOG   log file (default: print to the terminal)
set -uo pipefail
cd "$(dirname "$0")/.."

# Data commits get their own author. The .invalid domain can never be verified on GitHub,
# so these commits are never linked to a person's account or contribution graph.
export GIT_AUTHOR_NAME="copenhagen-student-jobs data" GIT_AUTHOR_EMAIL="data@copenhagen-student-jobs.invalid"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

today=$(TZ=Europe/Copenhagen date +%F)

if [ -n "${CPHJOBS_LOG:-}" ]; then
  mkdir -p "$(dirname "$CPHJOBS_LOG")"
  touch "$CPHJOBS_LOG"
  tail -n 1000 "$CPHJOBS_LOG" > "$CPHJOBS_LOG.tmp" && mv "$CPHJOBS_LOG.tmp" "$CPHJOBS_LOG"
  exec >> "$CPHJOBS_LOG" 2>&1
fi
log() { echo "$(date '+%F %T') $*"; }

# At most one notification a day, so a bad day doesn't nag every hour.
notify() {
  local marker="${CPHJOBS_LOG:-/tmp/cphjobs}.notified"
  [ "$(cat "$marker" 2>/dev/null)" = "$today" ] && return
  echo "$today" > "$marker"
  command -v osascript > /dev/null &&
    osascript -e "display notification \"$1\" with title \"Student jobs: collection failed\""
}

if [ "${1:-}" != "--force" ] &&
   [ "$(sqlite3 data/jobs.db "SELECT COUNT(*) FROM runs WHERE run_date = '$today'" 2>/dev/null)" != "0" ]; then
  exit 0  # already collected today; stay silent so the log isn't filled every hour
fi

if ! curl -sfI --max-time 10 https://github.com > /dev/null; then
  log "offline, will try again later"
  exit 0
fi

log "collecting"
if ! git pull --rebase --quiet; then
  log "git pull failed"
  notify "Could not update the local copy from GitHub. See the log."
  exit 1
fi

status=0
output=$(uv run cphjobs fetch --export data/export 2>&1) || status=$?
echo "$output"

git add data
if ! git diff --cached --quiet; then
  git commit --quiet -m "Update data $today"
  if ! git push --quiet; then
    log "git push failed"
    notify "The data was collected but could not be pushed to GitHub. See the log."
    exit 1
  fi
  log "pushed"
fi

if [ "$status" -ne 0 ]; then
  failed=$(echo "$output" | sed -n 's/^ERROR \([a-z]*\) failed.*/\1/p' | paste -sd, - | sed "s/,/, /g")
  notify "${failed:-A source} failed. The rest was saved. See the log."
  exit "$status"
fi
log "done"
