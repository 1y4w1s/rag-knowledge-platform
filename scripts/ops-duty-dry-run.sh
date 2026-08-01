#!/usr/bin/env bash
# Ruige ops duty quartet: orphan + stale + trash purge + chat retention (DRY-RUN ONLY)
# Usage (repo root): ./scripts/ops-duty-dry-run.sh
# Never passes an apply flag. For real delete/mark-failed, run one CLI by hand after review.
# See docs/tasks/eval-ops-duty-triplet-runbook.md (NW-16 + NW-35)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_ABS="${REPO_ROOT}/backend/scripts"
cd "$REPO_ROOT"

invoke_duty_dry_run() {
  local script_name="$1"
  echo ""
  echo "=== ${script_name} (DRY-RUN only) ==="
  docker compose run --rm --no-deps \
    -v "${SCRIPTS_ABS}:/app/scripts:ro" \
    api python "scripts/${script_name}"
}

echo "=== Ruige ops duty dry-run start ==="
echo "Scripts: ${SCRIPTS_ABS}"
echo "Mode: DRY-RUN only (wrapper never passes apply flag)"

invoke_duty_dry_run "scan_orphans.py"
invoke_duty_dry_run "scan_stale_ingestion.py"
invoke_duty_dry_run "purge_trash.py"
invoke_duty_dry_run "purge_chat_threads.py"

echo ""
echo "All four dry-runs finished."
