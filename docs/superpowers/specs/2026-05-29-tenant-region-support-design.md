# Add Region Support for Each Tenant

## Context

Each tenant in this django-tenants app is a health insurance company with its
own PostgreSQL schema holding `Member` records. We are introducing **region**
as a first-class concept so every tenant is bound to a single geographic region
and members are scoped to that region.

The driving requirement: **access patterns for members outside a tenant's region
are not supported.** A request must declare the region it is targeting in the URL,
and that region must match the tenant's assigned region — otherwise the request is
rejected (403). This adds a region-aware routing layer for navigating
region + tenant, plus a small registry so regions can be managed centrally.

### Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Region granularity | Region is addressed **per request via the URL** and stored **per `Member`**. The `Client` (tenant) is region-agnostic — **no region on `Client`** (it's the higher-level tenant). |
| Identifier representation | **String code** (e.g. `us-east`) in a `region_id` CharField on `Member`. No cross-schema FK. |
| Region registry | `Region` model in **public schema** (`shared_app`), **Django admin only** (no API). Source of truth for valid region codes. Keeps a `code` column + a **code generator** utility. |
| URL shape | `/client/{domain}/region/{region_id}/api/...` |
| Enforcement | URL `region_id` must exist in the active registry, and member writes must target that same region. **All region failures map to 400 externally.** Internally we distinguish `RegionNotFound` vs `RegionForbidden` for clarity/logging, but both surface as 400. Lookup/enforcement lives in a **reusable component** (used by middleware and API). |
| Member region on write | `region_id` is **required** in the payload; **400** if missing or if it ≠ the request's region. No defaulting. |
| `Member.region_id` | **Non-nullable** (breaking migration — acceptable, this is an interview project). |

## Architecture

```
Request: /client/{domain}/region/{region_id}/api/members
              │            │
              │            └─ validated against the Region registry (400 if unknown);
              │               scopes Member queries to this region
              └─ TenantSubfolderMiddleware resolves tenant (UNCHANGED — domain is still
                 the first segment after "client/")
```

- **Public schema** (`shared_app`): `Region` registry (no region field on `Client`).
- **Tenant schema** (`tenant_app`): `Member.region_id`.
- **TenantSubfolderMiddleware needs no change** — `{domain}` remains `path_chunks[0]`
  after the `client/` prefix. The `region/{region_id}` segment is consumed by the
  tenant urlconf and Ninja silently ignores the extra `region_id` kwarg
  (verified in django-ninja source: undeclared URL kwargs are dropped in
  `Operation._get_values`).

## Changes

### 1. Region registry model + code generator — `shared_app/models.py`, `shared_app/regions.py`
Add a `Region` model (public schema):
```python
class Region(models.Model):
    code = models.CharField(max_length=50, unique=True)   # e.g. "us-east"
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.code
```
Keep the `code` column. Add a **code generator** utility (e.g.
`generate_region_code(name)` in `shared_app/regions.py`) that derives a
normalized, unique region code (slugify + collision-resistant suffix). Wire it as
the default/auto-fill for `Region.code` when omitted (model `save()` or admin).

### 2. `Member.region_id` — `tenant_app/models.py`
Add `region_id = models.CharField(max_length=50)` to `Member` — **non-nullable**
(no `null`/`blank`). This is a breaking migration on the existing `Member` table;
acceptable because this is an interview project. No registry validation at the
member level (the tenant's region is the validated source of truth; member region
is enforced to equal it).

### 3. Reusable region enforcement component + middleware
**Reusable component** — `shared_app/regions.py` (alongside the code generator):
a single place for region lookup/enforcement, since it will be needed in multiple
areas (middleware now, API/other call sites later). Internally distinguishes two
error types **but both map to HTTP 400 externally**:
```python
class RegionError(Exception): ...        # base → 400
class RegionNotFound(RegionError): ...   # code not in active registry
class RegionForbidden(RegionError): ...  # acting on a region other than the request's

def resolve_region(region_code):
    """Raise RegionNotFound if code not in the active Region registry; else return it."""

def require_matching_region(request_region, target_region):
    """Raise RegionForbidden if target_region != request_region."""
```
The registry lookup hits the public-schema `Region` table; from a tenant request,
query it via `schema_context(get_public_schema_name())`.

**Middleware** — new `starterapp/middleware.py`, `RegionMiddleware.process_view`
(runs after `TenantSubfolderMiddleware`, so `request.tenant` is set and
`view_kwargs` holds the captured `region_id`):
- If `region_id` not in `view_kwargs` → no-op (non-region routes, e.g. admin).
- Else call `resolve_region(view_kwargs['region_id'])`:
  - any `RegionError` → `HttpResponse(status=400)`
  - success → set `request.region_id` for downstream use.

Register it in `MIDDLEWARE` (settings.py) immediately after
`django_tenants.middleware.TenantSubfolderMiddleware`.

### 4. URL routing — `starterapp/urls.py`
Change the tenant mount from `path('api/', tenant_api.urls)` to:
```python
path('region/<str:region_id>/api/', tenant_api.urls)
```
`starterapp/urls_public.py` (shared API) is unchanged — region does not apply to
the public schema.

### 5. Member API region scoping — `tenant_app/api.py`
- `region_id: str` is **required** (not Optional) on both `MemberUpdateSchema`
  (input) and `MemberResponseSchema` (output).
- **List** (`list_members`): `Member.objects.filter(region_id=request.region_id)`.
- **Get / Update / Delete**: look up within the region
  (`Member.objects.get(id=member_id, region_id=request.region_id)`), so out-of-region
  members are simply invisible → existing `ObjectDoesNotExist` handler returns 404.
- **Create / Update**: `require_matching_region(request.region_id, payload.region_id)`
  → `RegionForbidden` (400) on mismatch; otherwise set `member.region_id =
  request.region_id`. **No defaulting** — a missing `region_id` is a bad request.
  Add a Ninja `ValidationError` handler returning 400 so a missing/invalid
  `region_id` yields 400 (not Ninja's default 422).

### 6. Admin — `shared_app/admin.py`, `tenant_app/admin.py`
- Register `Region` (`list_display = ('code', 'name', 'is_active')`).
- `ClientAdmin` is **unchanged** (no region on the tenant).
- `MemberAdmin` may add `region_id` to `list_display` for visibility.

### 7. Migrations + seed
- `shared_app`: migration adds the `Region` model only; include a **data migration**
  seeding a couple of regions (e.g. `us-east`, `us-west`). No `Client` change.
- `tenant_app`: migration adds **non-nullable** `Member.region_id`. Against existing
  rows this needs a one-off default (e.g. add with `default='us-east'` then drop the
  default, or an add-column → data-migration → alter-not-null sequence). Expect to
  iterate until it applies.
- Apply: `migrate_schemas --shared` then `migrate_schemas --tenant`.

### 8. Tests — `tenant_app/tests/`
- **conftest.py**: set `region_id` on `member1`/`member2` fixtures (e.g. `us-east`);
  ensure the region codes used in tests exist in the seeded `Region` registry.
- **test_integration_members.py**: update URLs from
  `f'/client/{domain}/api/members'` to
  `f'/client/{domain}/region/{region}/api/members'`.
- **New region tests**: (a) valid registered region → 200 and members visible;
  (b) unknown region in URL → 400; (c) create with mismatched payload `region_id`
  → 400; (d) create with missing `region_id` → 400; (e) list only returns members
  of the request region.
- **test_tenant_isolation.py**: ensure isolation tests use the region-qualified URLs.
- **test_unit_members.py**: unit tests set `request.region_id` on the mocked request.

## Files

- `shared_app/models.py` — `Region` model (no change to `Client`)
- `shared_app/regions.py` — **new** reusable `resolve_region(...)` / `require_matching_region(...)` + `generate_region_code(...)`
- `tenant_app/models.py` — `Member.region_id` (non-nullable)
- `starterapp/middleware.py` — **new** `RegionMiddleware` (delegates to `resolve_region`)
- `starterapp/settings.py` — register middleware
- `starterapp/urls.py` — region-qualified tenant mount
- `tenant_app/api.py` — region scoping + schemas
- `shared_app/admin.py`, `tenant_app/admin.py` — register `Region`, show `Member.region_id`
- `shared_app/migrations/`, `tenant_app/migrations/` — schema + seed
- `tenant_app/tests/conftest.py`, `test_integration_members.py`,
  `test_tenant_isolation.py`, `test_unit_members.py`

## Parallelization Plan

The work splits into a small **foundation wave**, a **fan-out wave** of independent
streams (almost no file overlap), and a final **integration wave**. Lock the shared
**contracts** first so the fan-out streams can be built concurrently against them
without waiting on each other's code.

### Shared contracts (frozen in Wave 0, consumed by everyone)
- `shared_app/regions.py`:
  - `RegionError(Exception)` → maps to **400**; subclasses `RegionNotFound`, `RegionForbidden`.
  - `resolve_region(code) -> code` — raises `RegionNotFound` if not in the active registry.
  - `require_matching_region(request_region, target_region)` — raises `RegionForbidden` on mismatch.
  - `generate_region_code(name) -> str`.
- `request.region_id` — a validated region code string set by `RegionMiddleware`.
- URL captures the region as a `<str:region_id>` kwarg.
- `Member.region_id` — non-nullable `CharField(max_length=50)`.

### Wave 0 — Foundation (do first; the two tasks are independent of each other)
- **W0-A** (`shared_app`): `Region` model + `shared_app/regions.py` (exceptions,
  `resolve_region`, `require_matching_region`, `generate_region_code`) + shared
  migration + **seed** data migration (`us-east`, `us-west`).
- **W0-B** (`tenant_app`): add non-nullable `Member.region_id` + tenant migration
  (with the add→default→alter sequence; expect iteration).

W0-A and W0-B touch disjoint apps/files → can run in parallel. Apply migrations
(`migrate_schemas --shared` / `--tenant`) at the end of Wave 0 so downstream streams
have a working DB.

### Wave 1 — Fan-out (all parallel; disjoint files)
| Stream | Files | Depends on | Notes |
|---|---|---|---|
| **S1 Middleware** | `starterapp/middleware.py` (new), `starterapp/settings.py` | W0-A (regions.py + Region migrated) | `process_view` → `resolve_region`; any `RegionError` → 400; sets `request.region_id`. |
| **S2 Routing** | `starterapp/urls.py` | contract only | Change mount to `region/<str:region_id>/api/`. |
| **S3 Member API** | `tenant_app/api.py` | W0-B + regions.py + `request.region_id` contract | Required `region_id` schemas, region-scoped queries, `require_matching_region` (400), Ninja `ValidationError`→400 handler. |
| **S4 Admin** | `shared_app/admin.py`, `tenant_app/admin.py` | W0-A + W0-B | Register `Region`; show `Member.region_id`. |

No two Wave-1 streams edit the same file, so they merge cleanly (use a worktree per
stream if running as parallel agents).

### Wave 2 — Integration (serialized; after Wave 1 merges)
- **S5 Tests** (`tenant_app/tests/`): conftest region fixtures, region-qualified
  URLs in integration + isolation tests, new region tests, unit-test `request.region_id`.
- Run the **full migration + pytest** loop end-to-end; **iterate** on the
  `Member.region_id` migration until `--shared` and `--tenant` both apply and tests pass.

### Critical path
`W0-A → S1 (middleware) → S5 (integration tests)`. S2/S3/S4 are off the critical
path and finish earlier. The migration-iteration risk lives in W0-B and S5.

## Verification

```bash
source venv/bin/activate
docker compose up -d
python manage.py makemigrations
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant
pytest
```

> **Note:** `migrate_schemas` may fail on the first pass (e.g. the non-nullable
> `Member.region_id` against existing rows, or shared/tenant ordering). Expect to
> **iterate** here — adjust the migration (default value / data migration / split
> add-then-alter) until both `--shared` and `--tenant` apply cleanly.

Manual end-to-end (with `us-east` seeded in the `Region` registry):
- `GET /client/tenant1/region/us-east/api/members` → 200, members of `us-east` listed.
- `GET /client/tenant1/region/does-not-exist/api/members` → 400 (region not in registry).
- `POST /client/tenant1/region/us-east/api/members` body `{"name":"A","region_id":"us-west"}` → 400 (payload region ≠ request region).
- `POST` same with **no** `region_id` → 400 (region_id is required; rejected, not defaulted).
- `POST` same with `region_id":"us-east"` → 201, member stored with `region_id="us-east"`.
- Region registry editable at `/admin/` (public schema); new `Region` rows get an auto-generated `code` when omitted.

## Notes / Out of scope

- A request targets exactly **one** region (the URL segment). **Cross-region
  access patterns are not supported** — no querying members across regions in a
  single call.
- The tenant itself is region-agnostic; region lives on `Member` and in the URL.
- No region API endpoints — registry is admin-managed only.
- `Member.region_id` is a denormalized string code, not an FK (avoids
  tenant→public cross-schema FK fragility in django-tenants).
