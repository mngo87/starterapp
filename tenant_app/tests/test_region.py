import pytest
import json
from django.db import connection
from tenant_app.models import Member

pytestmark = pytest.mark.django_db(transaction=True)


def members_url(domain, region):
    return f'/client/{domain}/region/{region}/api/members'


def test_unknown_region_returns_400(tenant_client, test_tenant):
    """A URL region that is not in the active registry is rejected with 400."""
    domain = test_tenant.test_domain
    response = tenant_client.get(members_url(domain, 'atlantis'))
    assert response.status_code == 400


def test_create_member_region_mismatch_returns_400(tenant_client, test_tenant):
    """Payload region_id differing from the URL region is rejected with 400."""
    domain = test_tenant.test_domain
    region = test_tenant.test_region  # us-east

    payload = {
        "name": "Mismatch User",
        "region_id": "us-west",  # differs from the URL region
        "email": "mismatch@example.com",
        "phone": "555-000-0000"
    }
    response = tenant_client.post(
        members_url(domain, region),
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 400


def test_create_member_missing_region_returns_400(tenant_client, test_tenant):
    """A create payload without the required region_id is rejected with 400."""
    domain = test_tenant.test_domain
    region = test_tenant.test_region

    payload = {
        "name": "No Region User",
        "email": "noregion@example.com",
        "phone": "555-000-0000"
    }
    response = tenant_client.post(
        members_url(domain, region),
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 400


def test_list_is_scoped_to_request_region(tenant_client, test_tenant, member1):
    """The list endpoint only returns members of the request's region."""
    domain = test_tenant.test_domain
    region = test_tenant.test_region  # us-east; member1 is in this region

    # Insert a member in a different region directly in the tenant schema.
    connection.set_tenant(test_tenant)
    Member.objects.create(
        name="West Coast User",
        region_id="us-west",
        email="west@example.com",
        phone="555-111-1111"
    )
    connection.set_schema_to_public()

    response = tenant_client.get(members_url(domain, region))
    assert response.status_code == 200
    data = response.json()

    names = [m['name'] for m in data]
    assert member1.name in names
    assert "West Coast User" not in names
    assert all(m['region_id'] == region for m in data)
