from typing import Literal
from pydantic import BaseModel, Field, model_validator

class FiniteModel(BaseModel):
    model_config = {"allow_inf_nan": False}

class RodType(FiniteModel):
    model_config = {"allow_inf_nan": False}
    name: str
    height: float = Field(gt=0, le=30)
    price: float = Field(gt=0, le=1e7)

class Rect(FiniteModel):
    x: float
    y: float
    width: float = Field(gt=0)
    depth: float = Field(gt=0)

class Rod(FiniteModel):
    base_z: float | None = None
    x: float
    y: float
    type_index: int = Field(ge=0)

class IfcMetadata(FiniteModel):
    filename: str
    height_min_m: float | None = None
    height_max_m: float | None = None
    schema_name: str
    source_sha256: str
    length_unit_scale_to_m: float
    source_units: list[dict] = Field(default_factory=list)
    coordinate_reference: str = 'IFC placement/world coordinates in metres; map conversion retained as metadata'
    map_conversions: list[dict] = Field(default_factory=list)
    bounds_m: list[list[float]]
    diagnostics: dict = Field(default_factory=dict)
    failures: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class IfcSource(IfcMetadata):
    source_id: str

class MeshObject(FiniteModel):
    name: str
    role: Literal['protected','obstacle','air_terminal','excluded'] = 'protected'
    ifc_source_id: str | None = None
    ifc_guid: str | None = None
    ifc_class: str | None = None
    ifc_name: str | None = None
    source_unit_scale_to_m: float | None = None
    import_diagnostics: dict = Field(default_factory=dict)
    vertices: list[tuple[float,float,float]] = Field(max_length=100000)
    faces: list[tuple[int,int,int]] = Field(max_length=200000)

class Equipment(FiniteModel):
    name: str = 'Ventilation'
    x: float = 10
    y: float = 10
    z: float = 10
    width: float = Field(default=3, gt=0)
    depth: float = Field(default=3, gt=0)
    height: float = Field(default=2, gt=0)
    role: Literal['protected','obstacle','air_terminal','excluded'] = 'protected'

class Project(FiniteModel):
    model_config = {"allow_inf_nan": False}
    geometry_source: Literal['parametric','ifc'] = 'parametric'
    ifc_metadata: IfcMetadata | None = None
    ifc_sources: list[IfcSource] = Field(default_factory=list, max_length=20)
    reference_surface_confirmed: bool = False
    ifc_review_confirmed: bool = False
    acknowledged_ifc_omissions: list[str] = Field(default_factory=list)
    units: Literal['m'] = 'm'
    meshes: list[MeshObject] = Field(default_factory=list, max_length=1000)
    equipment: list[Equipment] = Field(default_factory=list, max_length=30)
    min_mount_normal_z: float = Field(default=0.5, gt=0, le=1)
    candidate_surfaces: list[str] = Field(default_factory=lambda: ['Roof'], max_length=1000)
    ground_z: float = 0
    sphere_tolerance: float = Field(default=0.001, ge=1e-6, le=0.05)
    sphere_refinement: int = Field(default=2, ge=0, le=4)
    name: str = '30 × 40 m demonstration'
    width: float = Field(default=30, gt=0, le=200)
    depth: float = Field(default=40, gt=0, le=200)
    roof_height: float = Field(default=10, ge=0, le=300)
    spacing: float = Field(default=5, ge=1, le=50)
    sample_spacing: float = Field(default=2.5, ge=0.5, le=20)
    lps: Literal['I','II','III','IV'] = 'III'
    edition: str = 'IEC 62305-3:2024 (normative data not loaded)'
    method: Literal['demo_angle','protection_angle','rolling_sphere'] = 'demo_angle'
    demo_angle_deg: float = Field(default=60, gt=0, lt=85)
    objective: Literal['cost','count','manual'] = 'cost'
    catalogue: list[RodType] = Field(default_factory=lambda: [RodType(name='A',height=2.5,price=100),RodType(name='B',height=5,price=180)], min_length=1, max_length=8)
    protected: list[Rect] = Field(default_factory=list)
    permitted: list[Rect] = Field(default_factory=list)
    prohibited: list[Rect] = Field(default_factory=list)
    rods: list[Rod] = Field(default_factory=list, max_length=1000)

    @model_validator(mode='after')
    def valid_rods(self):
        if any(r.type_index >= len(self.catalogue) for r in self.rods):
            raise ValueError('Rod type is absent from catalogue')
        ids=[source.source_id for source in self.ifc_sources]
        if len(ids)!=len(set(ids)):raise ValueError('IFC source IDs must be unique')
        if ids and any(m.ifc_source_id is not None and m.ifc_source_id not in ids for m in self.meshes):raise ValueError('Mesh references an unknown IFC source')
        names=['Roof']+[o.name for o in self.equipment]+[o.name for o in self.meshes]
        if len(names)!=len(set(names)):
            raise ValueError('Every geometry object must have a unique name; Roof is reserved')
        if len({r.name for r in self.catalogue})!=len(self.catalogue):
            raise ValueError('Rod catalogue names must be unique')
        if any(name not in names for name in self.candidate_surfaces):
            raise ValueError('Unknown candidate mounting surface')
        return self
