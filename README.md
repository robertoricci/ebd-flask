# EBD Frequência – Flask + SQLAlchemy + PostgreSQL

Sistema de controle de frequência para Escola Bíblica Dominical.

## Stack
- **Backend**: Python 3.12 + Flask 3.0 + SQLAlchemy + Flask-Migrate
- **ORM**: SQLAlchemy (via Flask-SQLAlchemy)
- **Banco**: PostgreSQL 16
- **Auth**: Flask-Login + bcrypt
- **Templates**: Jinja2
- **Deploy**: Docker Compose

## Estrutura MVC
```
ebd-flask/
├── app/
│   ├── models/          ← Model (SQLAlchemy)
│   │   ├── user.py
│   │   ├── teacher.py
│   │   ├── student.py
│   │   ├── klass.py
│   │   ├── trimester.py
│   │   ├── lesson.py
│   │   ├── attendance.py
│   │   └── visitor.py
│   ├── controllers/     ← Controller (Blueprints Flask)
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── users.py
│   │   ├── teachers.py
│   │   ├── students.py
│   │   ├── classes.py
│   │   ├── trimesters.py
│   │   ├── lessons.py
│   │   ├── attendance.py
│   │   ├── visitors.py
│   │   ├── reports.py
│   │   └── birthdays.py
│   ├── templates/       ← View (Jinja2 HTML)
│   ├── utils/           ← Decorators e helpers
│   ├── template_filters.py
│   └── __init__.py      ← App factory
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── requirements.txt
├── seed.py
└── wsgi.py
```

## Como rodar

### Com Docker (recomendado)
```bash
docker compose up --build
```
Acesse: http://localhost:5000
Login: **admin@ebd.com** / **admin123**

### Localmente (sem Docker)
```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:pass@localhost/ebd_db
export SECRET_KEY=minha-chave-secreta
flask db upgrade
python seed.py
python wsgi.py
```

## Migrações
```bash
# Criar nova migração
flask db migrate -m "descricao"

# Aplicar migrações
flask db upgrade
```

## Funcionalidades
- ✅ Login com email/senha (bcrypt)
- ✅ Perfis: Admin / Professor
- ✅ CRUD: Usuários, Professores, Alunos, Turmas
- ✅ Trimestres com geração automática de aulas
- ✅ Controle de presença (toggle por aluno)
- ✅ Visitantes por aula
- ✅ Status de aula: ABERTO → LIBERADO → FINALIZADO
- ✅ Dashboard com filtros
- ✅ Relatórios com barras de progresso
- ✅ Aniversários do mês
- ✅ Oferta por aula
- ✅ Design responsivo (mobile-first)
