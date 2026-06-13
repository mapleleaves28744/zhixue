from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PetNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID | None = None
    notification_type: str
    title: str
    reason: str | None = None
    source_type: str
    source_id: UUID | None = None
    action_url: str
    is_read: bool
    created_at: datetime


class PetPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    study_reminders_enabled: bool
    interval_hours: Literal[1, 2, 4]
    quiet_start: time
    quiet_end: time


class PetPreferenceUpdate(BaseModel):
    study_reminders_enabled: bool | None = None
    interval_hours: Literal[1, 2, 4] | None = None
    quiet_start: time | None = None
    quiet_end: time | None = None
