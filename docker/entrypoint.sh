#!/bin/sh
set -eu

mkdir -p /workspace/logs

# ค้นหาพาธของ python ที่ถูกต้องในระบบ
PYTHON_BIN="python"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif [ -x "/usr/local/bin/python" ]; then
  PYTHON_BIN="/usr/local/bin/python"
fi

run_sync() {
  script="$1"
  log_file="$2"
  shift 2 || true
  extra_args="$*"

  echo "$(date '+%Y-%m-%d %H:%M:%S') - INFO - Starting ${script} ${extra_args}" >> "${log_file}"
  if [ -n "${extra_args}" ]; then
    if ! ${PYTHON_BIN} "/workspace/${script}" ${extra_args} >> "${log_file}" 2>&1; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR - ${script} failed; cron will continue." >> "${log_file}"
      return 1
    fi
  else
    if ! ${PYTHON_BIN} "/workspace/${script}" >> "${log_file}" 2>&1; then
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
${PYTHON_BIN} /workspace/version_app.py >> /workspace/logs/version_server.log 2>&1 &

# ค้นหาและรัน cron daemon ที่เหมาะสมกับ OS (cron สำหรับ Debian/Ubuntu, crond สำหรับ Alpine)
if command -v cron >/dev/null 2>&1; then
  exec cron -f
elif command -v crond >/dev/null 2>&1; then
  exec crond -f -d 8
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR - Neither cron nor crond found!" >> /workspace/logs/cron_error.log 2>&1
  exit 1
fi
