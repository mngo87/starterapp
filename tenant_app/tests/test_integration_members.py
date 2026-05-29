import pytest
import json
from tenant_app.models import Member
from django.db import connection

# Mark all tests in this module to use the database
pytestmark = pytest.mark.django_db(transaction=True) # Use transactions for speed

# Constant used in tests
NONEXISTENT_ID = 9999

def members_url(tenant_domain, region):
    """List/create URL for members, including tenant domain + region prefix."""
    return f'/client/{tenant_domain}/region/{region}/api/members'

def detail_url(tenant_domain, region, member):
    """Detail URL for a member, including tenant domain + region prefix."""
    return f'/client/{tenant_domain}/region/{region}/api/members/{member.id}'

def test_list_members(tenant_client, test_tenant, member1, member2):
    """Test listing all members"""
    domain = test_tenant.test_domain # Get domain from the tenant fixture
    region = test_tenant.test_region
    list_url = members_url(domain, region)

    response = tenant_client.get(list_url)
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2

    # Check member data is correct (order might vary, sort by id)
    members_data = sorted(data, key=lambda x: x['id'])
    assert members_data[0]['id'] == member1.id
    assert members_data[0]['name'] == member1.name
    assert members_data[0]['email'] == member1.email
    assert members_data[0]['phone'] == member1.phone
    assert members_data[0]['region_id'] == region
    assert members_data[1]['id'] == member2.id
    assert members_data[1]['name'] == member2.name

def test_create_member(tenant_client, test_tenant):
    """Test creating a new member"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    list_url = members_url(domain, region)

    new_member_data = {
        "name": "New Test User",
        "region_id": region,
        "email": "new@example.com",
        "phone": "555-555-5555"
    }

    response = tenant_client.post(
        list_url, # Use dynamic URL
        data=json.dumps(new_member_data),
        content_type='application/json'
    )
    data = response.json()

    assert response.status_code == 200
    assert 'id' in data
    assert data['name'] == new_member_data['name']
    assert data['email'] == new_member_data['email']
    assert data['phone'] == new_member_data['phone']
    assert data['region_id'] == region

    # Verify in database (ensure connection is still set correctly)
    connection.set_tenant(test_tenant)
    created_member = Member.objects.get(id=data['id'])
    assert created_member.name == new_member_data['name']
    assert created_member.region_id == region
    connection.set_schema_to_public()

def test_create_member_invalid_data(tenant_client, test_tenant):
    """Test creating a member with invalid data (missing required fields)"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    list_url = members_url(domain, region)

    invalid_data = {
        # Missing required 'name' field
        "region_id": region,
        "email": "invalid@example.com",
        "phone": "555-555-5555"
    }

    response = tenant_client.post(
        list_url, # Use dynamic URL
        data=json.dumps(invalid_data),
        content_type='application/json'
    )

    # Our ValidationError handler maps invalid/missing fields to 400.
    assert response.status_code == 400

def test_get_member(tenant_client, test_tenant, member1):
    """Test retrieving a specific member"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    url = detail_url(domain, region, member1)

    response = tenant_client.get(url)
    data = response.json()

    assert response.status_code == 200
    assert data['id'] == member1.id
    assert data['name'] == member1.name
    assert data['email'] == member1.email
    assert data['phone'] == member1.phone
    assert data['region_id'] == region

def test_get_nonexistent_member(tenant_client, test_tenant):
    """Test retrieving a member that doesn't exist"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    nonexistent_url = f'{members_url(domain, region)}/{NONEXISTENT_ID}'

    response = tenant_client.get(nonexistent_url)
    # Ninja returns 404 when Member.DoesNotExist is caught by its handler
    assert response.status_code == 404

def test_update_member(tenant_client, test_tenant, member1):
    """Test updating a member"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    url = detail_url(domain, region, member1)

    update_data = {
        "name": "Updated Test User",
        "region_id": region,
        "email": "updated@example.com",
        "phone": "999-999-9999"
    }

    response = tenant_client.put(
        url,
        data=json.dumps(update_data),
        content_type='application/json'
    )
    data = response.json()

    assert response.status_code == 200
    assert data['name'] == update_data['name']
    assert data['email'] == update_data['email']
    assert data['phone'] == update_data['phone']

    # Verify in database
    connection.set_tenant(test_tenant)
    updated_member = Member.objects.get(id=member1.id)
    assert updated_member.name == update_data['name']
    assert updated_member.email == update_data['email']
    assert updated_member.phone == update_data['phone']
    connection.set_schema_to_public()

def test_update_nonexistent_member(tenant_client, test_tenant):
    """Test updating a member that doesn't exist"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    nonexistent_url = f'{members_url(domain, region)}/{NONEXISTENT_ID}'

    update_data = {
        "name": "This Won't Work",
        "region_id": region,
        "email": "wont@example.com",
        "phone": "000-000-0000"
    }

    response = tenant_client.put(
        nonexistent_url, # Use dynamic URL
        data=json.dumps(update_data),
        content_type='application/json'
    )
    assert response.status_code == 404

def test_update_member_invalid_data(tenant_client, test_tenant, member1):
    """Test updating a member with invalid data"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    url = detail_url(domain, region, member1)

    invalid_data = {
        # Missing required 'name' field in MemberUpdateSchema
        "region_id": region,
        "email": "stillneeded@example.com",
        "phone": "123-123-1234"
    }

    response = tenant_client.put(
        url,
        data=json.dumps(invalid_data),
        content_type='application/json'
    )
    assert response.status_code == 400 # Our ValidationError handler

def test_partial_update_member(tenant_client, test_tenant, member1):
    """
    Test partial update of a member. The PUT handler requires name + region_id;
    optional fields (email/phone) may be omitted.
    """
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    url = detail_url(domain, region, member1)

    update_data = {
        "name": "Partially Updated User",
        "region_id": region,
        # Omitting optional email/phone
    }

    response = tenant_client.put(
        url,
        data=json.dumps(update_data),
        content_type='application/json'
    )
    data = response.json()

    assert response.status_code == 200

    # Verify in database
    connection.set_tenant(test_tenant)
    updated_member = Member.objects.get(id=member1.id)
    assert updated_member.name == update_data['name']
    # email/phone remained unchanged (API only updates when provided)
    assert updated_member.email == member1.email
    assert updated_member.phone == member1.phone
    connection.set_schema_to_public()

def test_delete_member(tenant_client, test_tenant, member1):
    """Test deleting a member"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    url = detail_url(domain, region, member1)

    response = tenant_client.delete(url)
    assert response.status_code == 200

    # Verify member was deleted from database
    connection.set_tenant(test_tenant)
    with pytest.raises(Member.DoesNotExist):
        Member.objects.get(id=member1.id)
    connection.set_schema_to_public()

def test_delete_nonexistent_member(tenant_client, test_tenant):
    """Test deleting a member that doesn't exist"""
    domain = test_tenant.test_domain
    region = test_tenant.test_region
    nonexistent_url = f'{members_url(domain, region)}/{NONEXISTENT_ID}'

    response = tenant_client.delete(nonexistent_url)
    assert response.status_code == 404
