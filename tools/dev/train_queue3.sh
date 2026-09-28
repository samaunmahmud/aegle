#!/bin/bash
S=${AEGLE_LOG_DIR:-/tmp/aegle-training}; mkdir -p "$S"
cd "$(dirname "$0")/../../inference-service"
while pgrep -f "train_queue.sh|train_queue2.sh" >/dev/null; do sleep 30; done
echo "== stroke $(date +%T)"; .venv/bin/python -m training.train_stroke > $S/train_stroke.log 2>&1; echo "   exit $? $(date +%T)"
