from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class DataCatalogBase(BaseModel):
    catalog_code: Optional[str] = None
    catalog_name: Optional[str] = None
    data_type: str = "vehicle_realtime"
    data_source: str = "manual"
    description: Optional[str] = None
    storage_location: Optional[str] = None
    storage_format: str = "database"
    data_size: int = 0
    record_count: int = 0
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    data_owner: str = "system"
    access_level: str = "internal"
    encryption_enabled: bool = False
    desensitization_enabled: bool = True
    desensitization_rules: Optional[Dict[str, Any]] = None
    backup_enabled: bool = True
    retention_period: Optional[int] = None
    data_schema: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None
    update_frequency: str = "on_demand"
    last_updated: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    status: str = "active"
    tags: Optional[List[str]] = None

    @field_validator("access_level")
    @classmethod
    def validate_access_level(cls, v: str) -> str:
        valid_levels = ["public", "internal", "confidential", "restricted"]
        if v.lower() not in valid_levels:
            raise ValueError(f"访问级别必须是: {', '.join(valid_levels)}")
        return v.lower()

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("质量分数应在 0-100 之间")
        return v


class DataCatalogCreate(DataCatalogBase):
    pass


class DataCatalogUpdate(BaseModel):
    catalog_code: Optional[str] = None
    catalog_name: Optional[str] = None
    data_type: Optional[str] = None
    data_source: Optional[str] = None
    description: Optional[str] = None
    storage_location: Optional[str] = None
    storage_format: Optional[str] = None
    data_size: Optional[int] = None
    record_count: Optional[int] = None
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    data_owner: Optional[str] = None
    access_level: Optional[str] = None
    encryption_enabled: Optional[bool] = None
    desensitization_enabled: Optional[bool] = None
    desensitization_rules: Optional[Dict[str, Any]] = None
    backup_enabled: Optional[bool] = None
    retention_period: Optional[int] = None
    data_schema: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None
    update_frequency: Optional[str] = None
    last_updated: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: Optional[int] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("access_level")
    @classmethod
    def validate_access_level(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_levels = ["public", "internal", "confidential", "restricted"]
        if v.lower() not in valid_levels:
            raise ValueError(f"访问级别必须是: {', '.join(valid_levels)}")
        return v.lower()

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("质量分数应在 0-100 之间")
        return v


class DataCatalogResponse(DataCatalogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DesensitizationRule(BaseModel):
    field_name: str
    rule_type: str
    rule_params: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, v: str) -> str:
        valid_types = [
            "masking", "hashing", "encryption", "replacement",
            "truncation", "rounding", "generalization", "randomization"
        ]
        if v.lower() not in valid_types:
            raise ValueError(f"脱敏规则类型必须是: {', '.join(valid_types)}")
        return v.lower()

    class Config:
        from_attributes = True


class DataDesensitizationConfig(BaseModel):
    data_catalog_id: int
    enabled: bool
    rules: List[DesensitizationRule]
    last_applied: Optional[datetime] = None
    applied_by: Optional[str] = None

    class Config:
        from_attributes = True
