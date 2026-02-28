#!/bin/bash
set -e

echo "⏳ Aguardando PostgreSQL..."
python -c "
import time, psycopg, os
url = os.environ['DATABASE_URL']
for i in range(30):
    try:
        psycopg.connect(url)
        print('✅ PostgreSQL pronto!')
        break
    except:
        print(f'Tentativa {i+1}/30...')
        time.sleep(2)
"

echo "📦 Inicializando migrações..."
if [ ! -d "migrations" ]; then
    flask db init
fi


echo "🔄 Gerando migração..."
flask db migrate -m "init" 2>/dev/null || true

echo "⬆️ Aplicando migrações..."
# Se houver conflito de revisão, reseta o histórico e reaaplica do zero
flask db upgrade 2>/tmp/migrate_err.txt || {
    echo "⚠️  Conflito de revisão detectado, resetando histórico Alembic..."
    python -c "
import psycopg, os
conn = psycopg.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('DROP TABLE IF EXISTS alembic_version;')
conn.commit()
conn.close()
print('✅ Tabela alembic_version removida.')
"
    flask db upgrade
}

echo "🌱 Seed inicial..."
python seed.py

echo "🚀 Iniciando servidor..."
exec gunicorn -w 2 -b 0.0.0.0:5000 "wsgi:app"
