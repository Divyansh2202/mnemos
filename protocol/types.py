from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class MemoryType(str, Enum):
    SEMANTIC   = "semantic"
    EPISODIC   = "episodic"
    PROCEDURAL = "procedural"


class PrivacyLevel(str, Enum):
    PRIVATE    = "private"
    APP_SHARED = "app_shared"
    GLOBAL     = "global"


class Memory(BaseModel):
    id:            str          = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    content:       str
    type:          MemoryType   = MemoryType.SEMANTIC
    entity:        str          = "user"
    confidence:    float        = 0.8
    privacy:       PrivacyLevel = PrivacyLevel.GLOBAL
    app_id:        str          = "unknown"
    tags:          list[str]    = []
    created_at:    datetime     = Field(default_factory=datetime.utcnow)
    last_accessed: datetime     = Field(default_factory=datetime.utcnow)
    access_count:  int          = 0
    expires_at:    Optional[datetime] = None
    metadata:      dict         = {}


class StoreRequest(BaseModel):
    content:    str
    type:       MemoryType   = MemoryType.SEMANTIC
    confidence: float        = 0.8
    privacy:    PrivacyLevel = PrivacyLevel.GLOBAL
    tags:       list[str]    = []
    app_id:     str          = "unknown"
    entity:     str          = "user"
    user_id:    str          = "default"


class MemoryQuery(BaseModel):
    query:          str
    context:        str          = ""
    limit:          int          = 5
    min_confidence: float        = 0.5
    app_id:         str          = "unknown"
    user_id:        str          = "default"
    types:          list[MemoryType] = []


class LearnRequest(BaseModel):
    messages: list[dict]
    app_id:   str = "unknown"
    user_id:  str = "default"
