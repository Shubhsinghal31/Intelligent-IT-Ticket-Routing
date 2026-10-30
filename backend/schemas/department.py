"""
Department-related Pydantic schemas (DTOs for API I/O).
"""

from pydantic import BaseModel, ConfigDict


class DepartmentResponse(BaseModel):
    """Minimal department info — used to populate pickers (e.g. the admin
    Add User form's department dropdown). Departments are seed-managed
    data (see database/seeds/002_seed_departments.sql), not user-editable
    through the API yet, so this schema is read-only by design — no
    DepartmentCreate/DepartmentUpdate exists."""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
