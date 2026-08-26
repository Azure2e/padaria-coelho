#!/bin/bash
cd "$(dirname "$0")"
echo "Padaria Coelho — site + API em http://127.0.0.1:8765"
python3 api/servidor.py
