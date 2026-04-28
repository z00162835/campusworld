from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    type: str = Field(default="about:blank")
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None


class PageMeta(BaseModel):
    total: int
    offset: int
    limit: int


class NodeTypeIn(BaseModel):
    type_code: str
    type_name: str
    typeclass: str
    classname: str
    module_path: str
    parent_type_code: Optional[str] = None
    description: Optional[str] = None
    schema_definition: Dict[str, Any] = Field(default_factory=dict)
    schema_default: Dict[str, Any] = Field(default_factory=dict)
    inferred_rules: Dict[str, Any] = Field(default_factory=dict)
    ui_config: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    trait_class: str = "UNKNOWN"
    trait_mask: int = 0
    is_active: bool = True


class NodeTypeOut(NodeTypeIn):
    id: int
    status: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RelationshipTypeIn(BaseModel):
    type_code: str
    type_name: str
    typeclass: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    schema_definition: Dict[str, Any] = Field(default_factory=dict)
    inferred_rules: Dict[str, Any] = Field(default_factory=dict)
    ui_config: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    trait_class: str = "UNKNOWN"
    trait_mask: int = 0
    is_directed: bool = True
    is_symmetric: bool = False
    is_transitive: bool = False
    is_active: bool = True


class RelationshipTypeOut(RelationshipTypeIn):
    id: int
    status: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NodeIn(BaseModel):
    type_code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True
    is_public: bool = True
    access_level: str = "normal"
    trait_class: str = "UNKNOWN"
    trait_mask: int = 0
    location_id: Optional[int] = None
    home_id: Optional[int] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class NodeOut(NodeIn):
    id: int
    uuid: str
    type_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RelationshipIn(BaseModel):
    type_code: str
    source_id: int
    target_id: int
    source_role: Optional[str] = None
    target_role: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True
    weight: int = 1
    trait_class: str = "UNKNOWN"
    trait_mask: int = 0


class RelationshipOut(RelationshipIn):
    id: int
    uuid: str
    type_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ListResponse(BaseModel):
    items: List[Dict[str, Any]]
    page: PageMeta
