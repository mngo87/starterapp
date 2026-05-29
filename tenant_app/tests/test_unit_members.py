import pytest
from tenant_app.api import MemberUpdateSchema, list_members, create_member, get_member, update_member, delete_member
from tenant_app.models import Member
from shared_app.regions import RegionForbidden

# Constants used in tests
NONEXISTENT_ID = 9999
REGION = 'us-east'

# --- Unit Tests ---
def test_unit_list_members(mocker, mock_request, member1_unit_data, member2_unit_data):
    """Test listing all members (unit) - scoped to the request region"""
    mock_filter = mocker.patch('tenant_app.api.Member.objects.filter')
    mock_filter.return_value = [member1_unit_data, member2_unit_data]

    result = list_members(mock_request)

    assert len(result) == 2
    assert result[0].id == 1
    assert result[0].name == "Test User 1"
    assert result[1].id == 2
    mock_filter.assert_called_once_with(region_id=REGION)

def test_unit_create_member(mocker, mock_request):
    """Test creating a new member (unit)"""
    mock_create = mocker.patch('tenant_app.api.Member.objects.create')
    created_instance = Member(id=3, name="New Test User", region_id=REGION,
                              email="new@example.com", phone="555-555-5555")
    mock_create.return_value = created_instance

    payload = MemberUpdateSchema(
        name="New Test User",
        region_id=REGION,
        email="new@example.com",
        phone="555-555-5555"
    )

    result = create_member(mock_request, payload)

    assert result.id == 3
    assert result.name == "New Test User"
    assert result.region_id == REGION
    mock_create.assert_called_once_with(
        name="New Test User",
        region_id=REGION,
        email="new@example.com",
        phone="555-555-5555"
    )

def test_unit_create_member_region_mismatch(mocker, mock_request):
    """Creating a member for a different region raises RegionForbidden (-> 400)"""
    mock_create = mocker.patch('tenant_app.api.Member.objects.create')

    payload = MemberUpdateSchema(
        name="Wrong Region User",
        region_id="us-west",  # differs from mock_request.region_id ('us-east')
        email="wrong@example.com",
        phone="555-555-5555"
    )

    with pytest.raises(RegionForbidden):
        create_member(mock_request, payload)

    mock_create.assert_not_called()

def test_unit_get_member(mocker, mock_request, member1_unit_data):
    """Test retrieving a specific member (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.return_value = member1_unit_data

    result = get_member(mock_request, 1)

    assert result.id == 1
    assert result.name == "Test User 1"
    mock_get.assert_called_once_with(id=1, region_id=REGION)

def test_unit_get_nonexistent_member(mocker, mock_request):
    """Test retrieving a member that doesn't exist (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.side_effect = Member.DoesNotExist

    with pytest.raises(Member.DoesNotExist):
        get_member(mock_request, NONEXISTENT_ID)

    mock_get.assert_called_once_with(id=NONEXISTENT_ID, region_id=REGION)

def test_unit_update_member(mocker, mock_request):
    """Test updating a member (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_member_instance = mocker.MagicMock(spec=Member)
    mock_member_instance.id = 1
    mock_member_instance.name = "Original Name"
    mock_member_instance.email = "original@example.com"
    mock_member_instance.phone = "111-111-1111"
    mock_get.return_value = mock_member_instance

    payload = MemberUpdateSchema(
        name="Updated Test User",
        region_id=REGION,
        email="updated@example.com",
        phone="999-999-9999"
    )

    result = update_member(mock_request, 1, payload)

    mock_get.assert_called_once_with(id=1, region_id=REGION)
    assert mock_member_instance.name == "Updated Test User"
    assert mock_member_instance.email == "updated@example.com"
    assert mock_member_instance.phone == "999-999-9999"
    mock_member_instance.save.assert_called_once()
    assert result == mock_member_instance

def test_unit_update_nonexistent_member(mocker, mock_request):
    """Test updating a member that doesn't exist (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.side_effect = Member.DoesNotExist

    payload = MemberUpdateSchema(
        name="This Won't Work",
        region_id=REGION,
        email="wont@example.com",
        phone="000-000-0000"
    )

    with pytest.raises(Member.DoesNotExist):
        update_member(mock_request, NONEXISTENT_ID, payload)

    mock_get.assert_called_once_with(id=NONEXISTENT_ID, region_id=REGION)

def test_unit_partial_update_member(mocker, mock_request):
    """Test partially updating a member (unit) - based on current API logic"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_member_instance = mocker.MagicMock(spec=Member)
    mock_member_instance.id = 1
    mock_member_instance.name = "Original Name"
    mock_member_instance.email = "original@example.com"
    mock_member_instance.phone = "111-111-1111"
    mock_get.return_value = mock_member_instance

    # name + region_id required; email/phone optional (None => unchanged)
    payload = MemberUpdateSchema(
        name="Partially Updated User",
        region_id=REGION,
        email=None,
        phone=None
    )

    result = update_member(mock_request, 1, payload)

    mock_get.assert_called_once_with(id=1, region_id=REGION)
    assert mock_member_instance.name == "Partially Updated User"
    assert mock_member_instance.email == "original@example.com"
    assert mock_member_instance.phone == "111-111-1111"
    mock_member_instance.save.assert_called_once()
    assert result == mock_member_instance

def test_unit_delete_member(mocker, mock_request):
    """Test deleting a member (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_member_instance = mocker.MagicMock(spec=Member)
    mock_member_instance.id = 1
    mock_get.return_value = mock_member_instance

    result = delete_member(mock_request, 1)

    mock_get.assert_called_once_with(id=1, region_id=REGION)
    mock_member_instance.delete.assert_called_once()
    assert result == 200

def test_unit_delete_nonexistent_member(mocker, mock_request):
    """Test deleting a member that doesn't exist (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.side_effect = Member.DoesNotExist

    with pytest.raises(Member.DoesNotExist):
        delete_member(mock_request, NONEXISTENT_ID)

    mock_get.assert_called_once_with(id=NONEXISTENT_ID, region_id=REGION)
