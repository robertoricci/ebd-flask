#!/bin/bash
set -e

# ── Função para limpar alembic_version ──────────────────────────────────────
reset_alembic() {
    echo "==> Resetando alembic_version no banco..."
    python3 - << 'PYEOF'
import psycopg, os
conn = psycopg.connect(os.environ['DATABASE_URL'])
conn.autocommit = True
conn.execute('DROP TABLE IF EXISTS alembic_version;')
conn.close()
print("    alembic_version removida com sucesso.")
PYEOF
}

# ── 1. Inicializa pasta de migrations se necessário ──────────────────────────
echo "==> Verificando migrações..."
if [ ! -d "migrations" ]; then
    echo "    Pasta migrations não existe, inicializando..."
    flask db init
fi

# ── 2. Testa se o banco reconhece a revisão atual ────────────────────────────
echo "==> Verificando revisão do banco..."
flask db current 2>/tmp/db_current_err.txt || {
    ERR=$(cat /tmp/db_current_err.txt)
    if echo "$ERR" | grep -qE "Can't locate revision|No such revision"; then
        echo "    Revisão desconhecida detectada. Limpando..."
        reset_alembic
    fi
}

# ── 3. Gera migration automática (ignora erro se não houver mudanças) ────────
echo "==> Gerando migration se necessário..."
flask db migrate -m "auto" 2>/tmp/migrate_err.txt || {
    ERR=$(cat /tmp/migrate_err.txt)
    # "Target database is not up to date" ou "Nothing new" são ok
    if echo "$ERR" | grep -qE "Can't locate revision|No such revision"; then
        echo "    Revisão inválida no migrate, resetando..."
        reset_alembic
        flask db migrate -m "auto" 2>/dev/null || true
    else
        echo "    Nenhuma migration nova gerada (ok)."
    fi
}

# ── 4. Aplica migrations ─────────────────────────────────────────────────────
echo "==> Aplicando migrations..."
flask db upgrade 2>/tmp/upgrade_err.txt || {
    ERR=$(cat /tmp/upgrade_err.txt)
    echo "    Erro no upgrade: $ERR"

    if echo "$ERR" | grep -qE "Can't locate revision|No such revision"; then
        echo "    Revisão inválida detectada. Resetando e reaplicando..."
        reset_alembic
        flask db upgrade
    else
        echo "    Erro desconhecido no upgrade, abortando."
        cat /tmp/upgrade_err.txt
        exit 1
    fi
}

echo "==> Migrations aplicadas com sucesso."

# ── 5. Seed ──────────────────────────────────────────────────────────────────
echo "==> Executando seed..."
python seed.py || echo "    Seed ignorado (dados já existem ou erro não crítico)."

# ── 6. Inicia servidor ───────────────────────────────────────────────────────
echo "==> Iniciando servidor Gunicorn..."
exec gunicorn \
    -w 2 \
    -b 0.0.0.0:$PORT \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --log-level info \
    "wsgi:app"
