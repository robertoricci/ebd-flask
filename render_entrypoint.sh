#!/bin/bash
set -e
echo "Rodando migrações..."
flask db upgrade
echo "Seed..."
python seed.py
echo "Iniciando..."
exec gunicorn -w 2 -b 0.0.0.0:$PORT "wsgi:app"
