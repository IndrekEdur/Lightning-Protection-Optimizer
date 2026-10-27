"""Small synthetic STEP IFC solids; not client BIM reference validation."""
import numpy as np
import ifcopenshell
import ifcopenshell.guid


def write_fixture(path,schema='IFC4',millimetres=False,offset=(700000,6500000,10),equipment=True,slope=0):
    f=ifcopenshell.file(schema=schema);scale=.001 if millimetres else 1.
    def point(coords):return f.create_entity('IfcCartesianPoint',Coordinates=tuple(float(v/scale) for v in coords))
    def axis(coords=(0,0,0),tilt=0):return f.create_entity('IfcAxis2Placement3D',Location=point(coords),Axis=f.create_entity('IfcDirection',DirectionRatios=(0.,-float(np.sin(tilt)),float(np.cos(tilt)))),RefDirection=f.create_entity('IfcDirection',DirectionRatios=(1.,0.,0.)))
    unit=f.create_entity('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE',Prefix='MILLI' if millimetres else None)
    assignment=f.create_entity('IfcUnitAssignment',Units=[unit])
    context=f.create_entity('IfcGeometricRepresentationContext',ContextType='Model',CoordinateSpaceDimension=3,Precision=1e-7,WorldCoordinateSystem=axis())
    f.create_entity('IfcProject',GlobalId=ifcopenshell.guid.new(),Name='Synthetic placement/unit reference',UnitsInContext=assignment,RepresentationContexts=[context])
    def solid(kind,name,size,position,tilt=0):
        w,d,h=size
        profile=f.create_entity('IfcRectangleProfileDef',ProfileType='AREA',XDim=w/scale,YDim=d/scale,Position=f.create_entity('IfcAxis2Placement2D',Location=point((w/2,d/2))))
        extrusion=f.create_entity('IfcExtrudedAreaSolid',SweptArea=profile,Position=axis(),ExtrudedDirection=f.create_entity('IfcDirection',DirectionRatios=(0.,0.,1.)),Depth=h/scale)
        rep=f.create_entity('IfcShapeRepresentation',ContextOfItems=context,RepresentationIdentifier='Body',RepresentationType='SweptSolid',Items=[extrusion])
        shape=f.create_entity('IfcProductDefinitionShape',Representations=[rep])
        obj=f.create_entity(kind,GlobalId=ifcopenshell.guid.new(),Name=name,ObjectPlacement=f.create_entity('IfcLocalPlacement',RelativePlacement=axis(position,tilt)),Representation=shape)
        if kind=='IfcSlab':obj.PredefinedType='ROOF'
        return obj
    roof=solid('IfcSlab','Real-format synthetic roof',(10,20,.2),offset,slope)
    if equipment:
        solid('IfcBuildingElementProxy','Ventilation reference',(2,3,2),(offset[0]+2,offset[1]+3,offset[2]+.2))
    f.write(str(path));return f,roof
