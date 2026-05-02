#!/bin/sh
set -eu

mkdir -p /workspace/logs

run_sync() {
  script="$1"
  log_file="$2"

  echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Starting ${script}" >> "${log_file}"
  if ! /usr/local/bin/python "/workspace/${script}" >> "${log_file}" 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR - ${script} failed; cron will continue." >> "${log_file}"
    return 1
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Finished ${script}" >> "${log_file}"
}

# Run once immediately when container starts.
cd /workspace
run_sync "visit_type_count_sync.py" "/workspace/logs/visit_type_count_sync.log" || true
run_sync "remed_summary_15d_sync.py" "/workspace/logs/remed_sync.log" || true

# Cron reads /etc/cron.d/plk-sync directly.
exec cron -f
