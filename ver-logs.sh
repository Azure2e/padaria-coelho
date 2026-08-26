#!/bin/bash
cd "$(dirname "$0")"
echo "Logs da Padaria Coelho — Ctrl+C para sair"
touch api/servidor.log
tail -n 80 -f api/servidor.log
