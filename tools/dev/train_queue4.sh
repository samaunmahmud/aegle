#!/bin/bash
S=${AEGLE_LOG_DIR:-/tmp/aegle-training}; mkdir -p "$S"
cd "/Users/samaunmahmud/Documents/Medical  image detector/inference-service"
while pgrep -f "train_queue.sh|train_queue2.sh|train_queue3.sh" >/dev/null; do sleep 30; done
echo "== gleason $(date +%T)"; .venv/bin/python -m training.train_gleason > $S/train_gleason.log 2>&1; echo "   exit $? $(date +%T)"
