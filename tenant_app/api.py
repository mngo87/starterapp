from ninja import NinjaAPI, Schema
from typing import List, Optional
from .models import Member
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from ninja.errors import ValidationError

from shared_app.regions import RegionError, require_matching_region

api = NinjaAPI(title="Tenant API", urls_namespace="tenant_api")

class MemberUpdateSchema(Schema):
    name: str
    region_id: str
    phone: Optional[str] = None
    email: Optional[str] = None

class MemberResponseSchema(Schema):
    id: int
    name: str
    region_id: str
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime

class ErrorSchema(Schema):
    detail: str

@api.exception_handler(ObjectDoesNotExist)
def object_does_not_exist_handler(request, exc):
    return api.create_response(
        request,
        {"detail": "Object not found."},
        status=404
    )

@api.exception_handler(ValidationError)
def validation_error_handler(request, exc):
    # Missing/invalid request fields (including region_id) are bad requests.
    return api.create_response(
        request,
        {"detail": "Invalid request."},
        status=400
    )

@api.exception_handler(RegionError)
def region_error_handler(request, exc):
    # RegionNotFound / RegionForbidden both surface as 400.
    return api.create_response(
        request,
        {"detail": "Region not allowed."},
        status=400
    )

@api.get("/members", response=List[MemberResponseSchema])
def list_members(request):
    # Scoped to the request's region; out-of-region members are not accessible.
    return Member.objects.filter(region_id=request.region_id)

@api.post("/members", response=MemberResponseSchema)
def create_member(request, payload: MemberUpdateSchema):
    require_matching_region(request.region_id, payload.region_id)
    member = Member.objects.create(
        name=payload.name,
        region_id=request.region_id,
        phone=payload.phone,
        email=payload.email
    )
    return member

@api.get("/members/{member_id}", response=MemberResponseSchema)
def get_member(request, member_id: int):
    member = Member.objects.get(id=member_id, region_id=request.region_id)
    return member

@api.put("/members/{member_id}", response=MemberResponseSchema)
def update_member(request, member_id: int, payload: MemberUpdateSchema):
    require_matching_region(request.region_id, payload.region_id)
    member = Member.objects.get(id=member_id, region_id=request.region_id)
    member.name = payload.name
    if payload.phone is not None:
        member.phone = payload.phone
    if payload.email is not None:
        member.email = payload.email
    member.save()
    return member

@api.delete("/members/{member_id}", response={200: None})
def delete_member(request, member_id: int):
    member = Member.objects.get(id=member_id, region_id=request.region_id)
    member.delete()
    return 200
