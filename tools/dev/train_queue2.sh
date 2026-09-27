#!/bin/bash
S=${AEGLE_LOG_DIR:-/tmp/aegle-training}; mkdir -p "$S"
cd "/Users/samaunmahmud/Documents/Medical  image detector/inference-service"
while pgrep -f "train_queue.sh" >/dev/null; do sleep 30; done
for m in tissue wound eeg; do
  echo "== $m $(date +%T)"; .venv/bin/python -m training.train_$m > $S/train_$m.log 2>&1; echo "   exit $? $(date +%T)"
done
