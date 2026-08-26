#!/bin/bash
# Mantém a Padaria Coelho no ar. Se o servidor cair, sobe de novo.
cd "$(dirname "$0")"
LOG="api/servidor.log"
echo "Padaria Coelho em http://127.0.0.1:8765"
echo "Para parar: Ctrl+C"
while true; do
  python3 -u api/servidor.py >> "$LOG" 2>&1
  echo "$(date '+%F %T') servidor parou, religando em 2s" >> "$LOG"
  sleep 2
done
