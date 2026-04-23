#!/bin/sh
set -eu

mkdir -p /workspace/logs

# Run once immediately when container starts.
cd /workspace
if ! /usr/local/bin/python /workspace/sync_visit_type_daily.py >> /workspace/logs/visit_sync.log 2>&1; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR - Initial startup run failed; cron will continue." >> /workspace/logs/visit_sync.log
fi

# Cron reads /etc/cron.d/visit-sync directly.
exec cron -f
