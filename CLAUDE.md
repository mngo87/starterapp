# CLAUDE.md

Django multi-tenant application using django-tenants and Django Ninja API. Each tenant represents a health insurance company with isolated member data per schema.

## Environment Setup

Always activate the venv before running any Python/Django commands:

```bash
source venv/bin/activate
```

Docker must be running for PostgreSQL:

```bash
docker compose up -d
```

## Running the App

```bash
source venv/bin/activate
python manage.py runserver
```

## Running Tests

```bash
source venv/bin/activate
pytest
```

## Migrations

After modifying models in tenant_app:

```bash
python manage.py makemigrations
python manage.py migrate_schemas --tenant
python manage.py migrate_schemas --shared
```

## Project Structure

- `shared_app/` — public schema models: `Client`, `Domain`, `Region` (region registry); shared API at `/api/`
- `tenant_app/` — per-tenant models: `Member` (has `region_id`); region-scoped tenant API at `/client/{domain}/region/{region_id}/api/`
- `starterapp/` — Django settings, URL configuration, and `RegionMiddleware`

## Key URLs

- `http://localhost:8000/api/docs` — shared API docs
- `http://localhost:8000/client/{domain}/region/{region_id}/api/docs` — region-scoped tenant API docs
- `http://localhost:8000/admin/` — public schema admin (manage `Region` here)
- `http://localhost:8000/client/tenant1/admin/` — tenant1 admin

## Architecture Notes

- django-tenants uses separate PostgreSQL schemas per tenant for data isolation
- Public schema holds `Client` and `Domain` records
- Tenant schemas hold `Member` records scoped to that tenant
- `auto_create_schema = True` on `Client` triggers schema creation on save
