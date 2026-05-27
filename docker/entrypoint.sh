#!/bin/sh
set -eu

mkdir -p /workspace/logs

run_sync() {
  script="$1"
  log_file="$2"
  extra_args="${3:-}"

  echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Starting ${script} ${extra_args}" >> "${log_file}"
  if [ -n "${extra_args}" ]; then
    if ! /usr/local/bin/python "/workspace/${script}" "${extra_args}" >> "${log_file}" 2>&1; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR - ${script} failed; cron will continue." >> "${log_file}"
      return 1
    fi
  else
    if ! /usr/local/bin/python "/workspace/${script}" >> "${log_file}" 2>&1; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR - ${script} failed; cron will continue." >> "${log_file}"
      return 1
    fi
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Finished ${script}" >> "${log_file}"
}

# Run once immediately when container starts.
cd /workspace
run_sync "visit_type_count_sync.py" "/workspace/logs/visit_type_count_sync.log" || true
run_sync "remed_summary_15d_sync.py" "/workspace/logs/remed_sync.log" || true

# Check if drug_home_count_sync needs initial run
FLAG_FILE="/workspace/logs/.drug_home_init_done"
if [ ! -f "$FLAG_FILE" ]; then
  if run_sync "drug_home_count_sync.py" "/workspace/logs/drug_home_sync.log" "--init"; then
    touch "$FLAG_FILE"
  fi
else
  run_sync "drug_home_count_sync.py" "/workspace/logs/drug_home_sync.log" || true
fi

# Start version endpoint in the background; cron remains the foreground process.
/usr/local/bin/python /workspace/version_app.py >> /workspace/logs/version_server.log 2>&1 &

# Cron reads /etc/cron.d/plk-sync directly.
exec cron -f
