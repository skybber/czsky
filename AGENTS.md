# AGENTS Guide (v1)

## What This Project Does
- Flask web app for astronomy observers (catalog browsing, planning, observations, solar-system objects, charts).
- Includes Python backend + JS/CSS frontend assets.
- Uses local astronomy datasets and import scripts to seed/update DB content.

## Project Map (Main Folders)
- `app/`: Main Flask app.
- `app/account/`: Auth/account flows.
- `app/admin/`: Admin UI and admin-only actions.
- `app/commons/`: Shared domain/application helpers.
- `app/compat/`: Compatibility shims/wrappers.
- `app/main/`: Main feature blueprints.
- `app/main/catalogue/`: Catalogue browsing and object lists.
- `app/main/chart/`: Chart pages and chart theme management.
- `app/main/equipment/`: Equipment features.
- `app/main/import_history/`: Import history screens.
- `app/main/location/`: Observer locations.
- `app/main/news/`: News pages.
- `app/main/observation/`: Observations, observed objects, observing sessions.
- `app/main/planner/`: Planner, wishlist, and session plans.
- `app/main/skyquality/`: Sky quality / SQM features.
- `app/main/solarsystem/`: Planets, comets, minor planets, moons.
- `app/main/system/`: System/internal pages. 
- `app/main/userdata/`: User-managed content and git-backed storage.
- `app/main/usersettings/`: User settings and account maintenance.
- `app/models/`: SQLAlchemy models and DB-facing domain types.
- `app/assets/`: Editable frontend asset sources.
- `app/templates/`: Jinja templates.
- `app/static/`: Generated/static-served assets and static resources.
- `app/translations/`: i18n translation files.
- `imports/`: Initialization/import scripts for catalog/data ingestion.
- `tests/`: Python `unittest` suite.
- `migrations/`: Alembic/Flask-Migrate DB schema history.
- `fchart3/`: Embedded chart engine/CLI package (separate Python package layout).
- `data/`: Catalog source files used by import commands.
- `private_data/`, `user_data/`, `uploads/`: Runtime/user content; not source code.
- `docs/`: TODO (minimal content; no clear active doc workflow).

## Run, Test, Build
- Environment:
  - `python3 -m venv venv && source venv/bin/activate`
  - `pip install -r requirements.txt`
  - Create `config.env` from `config.env.example`.
- Initialize DB/data:
  - `./recreate_all.sh` (production-like seed)
  - `./recreate_all_test.sh` (test/dev seed)
- Run locally:
  - `honcho start -e config.env -f Local`
- Test:
  - `python -m unittest`
  - or `flask --app manage test`
- Lint:
  - `flake8`
- Frontend assets:
  - Source: `app/assets/scripts/*`, `app/assets/styles/*`
  - Generated outputs: `app/static/scripts/*`, `app/static/styles/*`, `app/static/.webassets-cache/*`, `app/static/webassets-external/*`

## Safe Edit Rules For Agents
- Prefer edits in `app/`, `imports/`, `tests/`, and migration files only when needed.
- Do not commit secrets from `config.env` or private credentials.
- Treat large catalog/data/ephemeris files as runtime assets unless task explicitly targets data updates.
- Keep DB changes via migrations (do not silently change models without matching migration intent).
- For frontend changes, edit asset sources in `app/assets/*`, not generated files under `app/static/*`.
- Avoid broad refactors across `fchart3/` unless task explicitly targets chart engine behavior.
- Validate changes with focused tests (`python -m unittest`) and relevant smoke checks.

## Generated / Do-Not-Edit Files
- Python/runtime caches:
  - `__pycache__/`, `*.pyc`, `*.pyo`
- Webassets outputs:
  - `app/static/scripts/*`
  - `app/static/styles/*`
  - `app/static/.webassets-cache/*`
  - `app/static/webassets-external/*`
- Runtime and local state:
  - `*.sqlite`
  - `*.log`, `dump.rdb`
  - `uploads/*`, `user_data/*`, `private_data/*`
- Generated bindings/artifacts:
  - `messages.mo` (compiled translation artifact)
