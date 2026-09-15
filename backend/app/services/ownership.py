from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Farm, Field, Device, User

def get_farm_owned(db: Session, user: User, farm_id: int) -> Farm:
    obj = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.owner_id == user.id))
    if not obj: raise HTTPException(404, "Farm not found")
    return obj

def get_field_owned(db: Session, user: User, field_id: int) -> Field:
    obj = db.scalar(select(Field).join(Farm).where(Field.id == field_id, Farm.owner_id == user.id))
    if not obj: raise HTTPException(404, "Field not found")
    return obj

def get_device_owned(db: Session, user: User, device_id: int) -> Device:
    obj = db.scalar(select(Device).join(Field).join(Farm).where(Device.id == device_id, Farm.owner_id == user.id))
    if not obj: raise HTTPException(404, "Device not found")
    return obj
