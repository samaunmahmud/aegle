#!/bin/bash
S=${AEGLE_LOG_DIR:-/tmp/aegle-training}; mkdir -p "$S"
cd "/Users/samaunmahmud/Documents/Medical  image detector/inference-service"
while pgrep -f "training.train_malaria" >/dev/null; do sleep 20; done
for m in retinopathy glaucoma dermatology gastro; do
  echo "== $m $(date +%T)"; .venv/bin/python -m training.train_$m > $S/train_$m.log 2>&1; echo "   exit $? $(date +%T)"
done
while [ "$(find ../dataset/ptbxl/records100 -name '*.dat' | wc -l)" -lt 21799 ]; do sleep 30; done
echo "== ecg $(date +%T)"; .venv/bin/python -m training.train_ecg > $S/train_ecg.log 2>&1; echo "   exit $? $(date +%T)"
