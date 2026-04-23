from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class BatchBase(BaseModel):
    name: str

class BatchCreate(BatchBase):
    pass

class BatchResponse(BatchBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
