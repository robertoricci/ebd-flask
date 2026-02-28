#!/bin/bash
set -e

echo "Inicializando migrações..."
if [ ! -d "migrations" ]; then
    flask db init
fi
flask db migrate -m "lesson teacher_id and lesson_students"

echo "Gerando migração..."
flask db migrate -m "init" 2>/dev/null || true

echo "Aplicando migrações..."
flask db upgrade 2>/tmp/migrate_err.txt || {
    echo "Conflito de revisão detectado, resetando..."
    python -c "
import psycopg, os
conn = psycopg.connect(os.environ['DATABASE_URL'])
conn.autocommit = True
conn.execute('DROP TABLE IF EXISTS alembic_version;')
conn.close()
print('Tabela alembic_version removida.')
"
    flask db upgrade
}

echo "Seed..."
python seed.py

echo "Iniciando servidor..."
exec gunicorn -w 2 -b 0.0.0.0:$PORT "wsgi:app"
