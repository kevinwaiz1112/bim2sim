"""Module contains the different classes for all HVAC elements"""
import inspect
import logging
import math
import re
import sys
from datetime import date
from typing import Set, List

import ifcopenshell
import ifcopenshell.geom
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.BRepLib import BRepLib_FuseEdges
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GProp import GProp_GProps
from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Face
from OCC.Core._Geom import Handle_Geom_Plane_DownCast
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_XYZ, gp_Dir, gp_Ax1, gp_Pnt, \
    gp_Mat, gp_Quaternion

from bim2sim.decorators import cached_property
from bim2sim.kernel import element, attribute, condition
from bim2sim.kernel.units import ureg
from bim2sim.task.common.inner_loop_remover import remove_inner_loops
from bim2sim.utilities.common_functions import vector_angle, angle_equivalent
from bim2sim.utilities.pyocc_tools import PyOCCTools

logger = logging.getLogger(__name__)
settings_products = ifcopenshell.geom.main.settings()
settings_products.set(settings_products.USE_PYTHON_OPENCASCADE, True)


# todo @ veronika: convert all attributes regarding SB
#  which can't come from ifc to cached_property


class BPSProduct(element.ProductBased):
    domain = 'BPS'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thermal_zones = []
        self.space_boundaries = []
        self.storeys = []
        self.material = None

    def get_bound_area(self, name) -> ureg.Quantity:
        """ get gross bound area (including opening areas) of the element"""
        return sum(sb.bound_area for sb in self.sbs_without_corresponding)

    def get_net_bound_area(self, name) -> ureg.Quantity:
        """get net area (including opening areas) of the element"""
        return self.gross_area - self.opening_area

    def get_top_bottom(self, name) -> list:
        """get the top_bottom function, determines if a horizontal element
        normal points up (bottom) or points down (top)"""
        return list(
            set([sb.top_bottom for sb in self.sbs_without_corresponding]))

    @cached_property
    def is_external(self) -> bool or None:
        """Checks if the corresponding element has contact with external
        environment (e.g. ground, roof, wall)"""
        if hasattr(self, 'parent'):
            return self.parent.is_external
        elif hasattr(self, 'ifc'):
            if hasattr(self.ifc, 'ProvidesBoundaries'):
                if len(self.ifc.ProvidesBoundaries) > 0:
                    ext_int = list(
                        set([boundary.InternalOrExternalBoundary for boundary
                             in self.ifc.ProvidesBoundaries]))
                    if len(ext_int) == 1:
                        if ext_int[0].lower() == 'external':
                            return True
                        if ext_int[0].lower() == 'internal':
                            return False
                    else:
                        return ext_int
        return None

    def calc_cost_group(self) -> int:
        """Default cost group for building elements is 300"""
        return 300

    gross_area = attribute.Attribute(
        functions=[get_bound_area],
        unit=ureg.meter ** 2
    )
    net_area = attribute.Attribute(
        functions=[get_net_bound_area],
        unit=ureg.meter ** 2
    )

    @cached_property
    def sbs_without_corresponding(self):
        """get a list with only not duplicated space boundaries"""
        sbs_without_corresponding = list(self.space_boundaries)
        for sb in self.space_boundaries:
            if sb in sbs_without_corresponding:
                if sb.related_bound and sb.related_bound in \
                        sbs_without_corresponding:
                    sbs_without_corresponding.remove(sb.related_bound)
        return sbs_without_corresponding

    top_bottom = attribute.Attribute(
        functions=[get_top_bottom],
    )

    @cached_property
    def opening_area(self):
        """get sum of opening areas of the element"""
        return sum(sb.opening_area for sb in self.sbs_without_corresponding)

    def calc_orientation(self) -> float:
        """Calculate the orientation of the bps product based on SB direction.

        For buildings elements we can use the more reliable space boundaries
        normal vector to calculate the orientation if the space boundaries
        exists. Otherwise the base calc_orientation of IFCBased will be used.

        Returns:
            Orientation angle between 0 and 360.
            (0 : north, 90: east, 180: south, 270: west)
        """
        true_north = self.get_true_north()
        if len(self.space_boundaries):
            new_orientation = self.group_orientation(
                [vector_angle(space_boundary.bound_normal.Coord())
                 for space_boundary in self.space_boundaries])
            if new_orientation is not None:
                return int(angle_equivalent(new_orientation + true_north))
        # return int(angle_equivalent(super().calc_orientation() + true_north))
        return None

    @staticmethod
    def group_orientation(orientations: list):
        dict_orientations = {}
        for orientation in orientations:
            rounded_orientation = round(orientation)
            if rounded_orientation not in dict_orientations:
                dict_orientations[rounded_orientation] = 0
            dict_orientations[rounded_orientation] += 1
        if len(dict_orientations):
            return max(dict_orientations, key=dict_orientations.get)
        return None

    @cached_property
    def volume(self):
        if hasattr(self, "net_volume"):
            if self.net_volume:
                vol = self.net_volume
                return vol
        vol = self.calc_volume_from_ifc_shape()
        return vol

    def calc_volume_from_ifc_shape(self):
        # todo use more efficient iterator to calc all shapes at once
        #  with multiple cores:
        #  https://wiki.osarch.org/index.php?title=IfcOpenShell_code_examples
        if hasattr(self.ifc, 'Representation'):
            try:
                shape = ifcopenshell.geom.create_shape(
                            settings_products, self.ifc).geometry
                vol = PyOCCTools.get_shape_volume(shape)
                vol = vol * ureg.meter ** 3
                return vol
            except:
                logger.warning(f"No calculation of geometric volume possible "
                               f"for {self.ifc}.")


class ThermalZone(BPSProduct):
    ifc_types = {
        "IfcSpace":
            ['*', 'SPACE', 'PARKING', 'GFA', 'INTERNAL', 'EXTERNAL']
    }

    pattern_ifc_type = [
        re.compile('Space', flags=re.IGNORECASE),
        re.compile('Zone', flags=re.IGNORECASE)
    ]

    @cached_property
    def outer_walls(self) -> list:
        """List of all outer wall instances bounded to the thermal zone"""
        return [
            ele for ele in self.bound_elements if isinstance(ele, OuterWall)]

    @cached_property
    def windows(self) -> list:
        """List of all window instances bounded to the thermal zone"""
        return [ele for ele in self.bound_elements if isinstance(ele, Window)]

    @cached_property
    def is_external(self) -> bool:
        """determines if a thermal zone is external or internal based on the
        presence of outer walls"""
        return len(self.outer_walls) > 0

    @cached_property
    def external_orientation(self) -> str or float:
        """determines the orientation of the thermal zone based on its elements
        it can be a corner (list of 2 angles) or an edge (1 angle)"""
        if self.is_external is True:
            orientations = [ele.orientation for ele in self.outer_walls]
            calc_temp = list(set(orientations))
            sum_or = sum(calc_temp)
            if 0 in calc_temp:
                if sum_or > 180:
                    sum_or += 360
            return sum_or / len(calc_temp)
        return 'Internal'

    @cached_property
    def glass_percentage(self) -> float or ureg.Quantity:
        """determines the glass area/facade area ratio for all the windows in
        the space in one of the 4 following ranges
        0%-30%: 15
        30%-50%: 40
        50%-70%: 60
        70%-100%: 85"""
        glass_area = sum(wi.gross_area for wi in self.windows)
        facade_area = sum(wa.gross_area for wa in self.outer_walls)
        if facade_area > 0:
            return 100 * (glass_area / (facade_area + glass_area)).m
        else:
            return 'Internal'

    @cached_property
    def space_neighbors(self):
        """determines the neighbors of the thermal zone"""
        neighbors = []
        for sb in self.space_boundaries:
            if sb.related_bound is not None:
                tz = sb.related_bound.bound_thermal_zone
                # todo: check if computation of neighbors works as expected
                # what if boundary has no related bound but still has a
                # neighbor?
                # hint: neighbors != related bounds
                if (tz is not self) and (tz not in neighbors):
                    neighbors.append(tz)
        return neighbors

    @cached_property
    def space_shape(self):
        """returns topods shape of the IfcSpace"""
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        return ifcopenshell.geom.create_shape(settings, self.ifc).geometry

    @cached_property
    def space_center(self):
        """
        This function returns the center of the bounding box of an ifc space
        shape
        :return: center of space bounding box (gp_Pnt)
        """
        bbox = Bnd_Box()
        brepbndlib_Add(self.space_shape, bbox)
        bbox_center = ifcopenshell.geom.utils.get_bounding_box_center(bbox)
        return bbox_center

    def get_space_shape_volume(self, name):
        """
        This function returns the volume of a space shape
        """
        return PyOCCTools.get_shape_volume(self.space_shape)

    def get_volume_geometric(self, name):
        """
        This function returns the volume of a space geometrically
        """
        return self.gross_area * self.height

    def _get_usage(self, name):
        """
        This function returns the usage of a space
        """
        if self.zone_name is not None:
            usage = self.zone_name
        elif self.ifc.LongName is not None and \
                "oldSpaceGuids_" not in self.ifc.LongName:
            # todo oldSpaceGuids_ is hardcode for erics tool
            usage = self.ifc.LongName
        else:
            usage = self.name
        return usage

    def _get_name(self, name):
        """
        This function returns the name of a space
        """
        if self.zone_name:
            space_name = self.zone_name
        else:
            space_name = self.ifc.Name
        return space_name

    def get_bound_floor_area(self, name):
        """Get bound floor area of zone. This is currently set by sum of all
        horizontal gross area and take half of it due to issues with
        TOP BOTTOM"""
        leveled_areas = {}
        for height, sbs in self.horizontal_sbs.items():
            if height not in leveled_areas:
                leveled_areas[height] = 0
            leveled_areas[height] += sum([sb.bound_area for sb in sbs])

        return sum(leveled_areas.values()) / 2

    def get_net_bound_floor_area(self, name):
        """Get net bound floor area of zone. This is currently set by sum of all
        horizonal net area and take half of it due to issues with TOP BOTTOM."""
        leveled_areas = {}
        for height, sbs in self.horizontal_sbs.items():
            if height not in leveled_areas:
                leveled_areas[height] = 0
            leveled_areas[height] += sum([sb.net_bound_area for sb in sbs])

        return sum(leveled_areas.values() / 2)

    @cached_property
    def horizontal_sbs(self):
        """get all horizonal SBs in a zone and convert them into a dict with
         key z-height in room and the SB as value."""
        # todo: use only bottom when TOP bottom is working correctly
        valid = ['TOP', 'BOTTOM']
        leveled_sbs = {}
        for sb in self.sbs_without_corresponding:
            if sb.top_bottom in valid:
                pos = round(sb.position[2], 1)
                if pos not in leveled_sbs:
                    leveled_sbs[pos] = []
                leveled_sbs[pos].append(sb)

        return leveled_sbs

    zone_name = attribute.Attribute(
        default_ps=("Pset_SpaceCommon", "Reference")
    )

    name = attribute.Attribute(
        functions=[_get_name]
    )

    usage = attribute.Attribute(
        default_ps=("Pset_SpaceOccupancyRequirements", "OccupancyType"),
        functions=[_get_usage]
    )

    t_set_heat = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMin"),
        unit=ureg.degC,
    )

    t_set_cool = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMax"),
        unit=ureg.degC,
    )

    t_ground = attribute.Attribute(
        unit=ureg.degC,
        default=13,
    )

    max_humidity = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceHumidityMax"),
        unit=ureg.dimensionless,
    )

    min_humidity = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceHumidityMin"),
        unit=ureg.dimensionless,
    )

    natural_ventilation = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "NaturalVentilation"),
    )

    natural_ventilation_rate = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "NaturalVentilationRate"),
        unit=1 / ureg.hour,
    )

    mechanical_ventilation_rate = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements",
                    "MechanicalVentilationRate"),
        unit=1 / ureg.hour,
    )

    with_ahu = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "AirConditioning"),
    )

    central_ahu = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "AirConditioningCentral"),
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "GrossFloorArea"),
        functions=[get_bound_floor_area],
        unit=ureg.meter ** 2
    )
    net_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetFloorArea"),
        functions=[get_net_bound_floor_area],
        unit=ureg.meter ** 2
    )

    net_wall_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetWallArea"),
        unit=ureg.meter ** 2
    )

    net_ceiling_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetCeilingArea"),
        unit=ureg.meter ** 2
    )

    net_volume = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetVolume"),
        functions=[get_space_shape_volume, get_volume_geometric],
        unit=ureg.meter ** 3,
    )
    gross_volume = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "GrossVolume"),
        functions=[get_volume_geometric],
        unit=ureg.meter ** 3,
    )
    height = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Height"),
        unit=ureg.meter,
    )
    length = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Length"),
        unit=ureg.meter,
    )
    width = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Width"),
        unit=ureg.m
    )
    AreaPerOccupant = attribute.Attribute(
        default_ps=("Pset_SpaceOccupancyRequirements", "AreaPerOccupant"),
        unit=ureg.meter ** 2
    )

    space_shape_volume = attribute.Attribute(
        functions=[get_space_shape_volume],
        unit=ureg.meter ** 3,
    )

    def _get_heating_profile(self, name) -> list:
        """returns a heating profile using the heat temperature in the IFC"""
        # todo make this "dynamic" with a night set back
        return [self.t_set_heat.to(ureg.kelvin).m] * 24

    def _get_cooling_profile(self, name) -> list:
        """returns a cooling profile using the cool temperature in the IFC"""
        # todo make this "dynamic" with a night set back
        return [self.t_set_cool.to(ureg.kelvin).m] * 24

    heating_profile = attribute.Attribute(
        functions=[_get_heating_profile],
        dependant_attributes=['t_set_heat']
    )
    cooling_profile = attribute.Attribute(
        functions=[_get_cooling_profile],
        dependant_attributes=['t_set_cool']
    )

    def _get_persons(self, name):
        return 1 / self.AreaPerOccupant

    persons = attribute.Attribute(
        functions=[_get_persons],
        dependant_attributes=['AreaPerOccupant']
    )
    # use conditions
    with_cooling = attribute.Attribute(
    )
    with_heating = attribute.Attribute(
    )
    typical_length = attribute.Attribute(
    )
    typical_width = attribute.Attribute(
    )
    T_threshold_heating = attribute.Attribute(
    )
    activity_degree_persons = attribute.Attribute(
    )
    fixed_heat_flow_rate_persons = attribute.Attribute(
        default_ps=("Pset_SpaceThermalLoad", "People"),
        unit=ureg.W,
    )
    internal_gains_moisture_no_people = attribute.Attribute(
    )
    T_threshold_cooling = attribute.Attribute(
    )
    ratio_conv_rad_persons = attribute.Attribute(
        default=0.5,
    )
    ratio_conv_rad_machines = attribute.Attribute(
        default=0.5,
    )
    ratio_conv_rad_lighting = attribute.Attribute(
        default=0.5,
    )
    machines = attribute.Attribute(
        default_ps=("Pset_SpaceThermalLoad", "EquipmentSensible"),
        unit=ureg.watt,
    )
    lighting_power = attribute.Attribute(
        default_ps=("Pset_SpaceThermalLoad", "Lighting"),
        unit=ureg.W,
    )
    use_constant_infiltration = attribute.Attribute(
    )
    infiltration_rate = attribute.Attribute(
    )
    max_user_infiltration = attribute.Attribute(
    )
    max_overheating_infiltration = attribute.Attribute(
    )
    max_summer_infiltration = attribute.Attribute(
    )
    winter_reduction_infiltration = attribute.Attribute(
    )
    min_ahu = attribute.Attribute(
    )
    max_ahu = attribute.Attribute(
        default_ps=("Pset_AirSideSystemInformation", "TotalAirflow"),
        unit=ureg.meter ** 3 / ureg.s
    )
    with_ideal_thresholds = attribute.Attribute(
    )
    persons_profile = attribute.Attribute(
    )
    machines_profile = attribute.Attribute(
    )
    lighting_profile = attribute.Attribute(
    )

    def __init__(self, *args, **kwargs):
        """thermalzone __init__ function"""
        self.bound_elements = kwargs.pop('bound_elements', [])  # todo workaround
        super().__init__(*args, **kwargs)

    def get__elements_by_type(self, type):
        raise NotImplementedError


class ExternalSpatialElement(ThermalZone):
    ifc_types = {
        "IfcExternalSpatialElement":
            ['*']
    }


class SpaceBoundary(element.RelationBased):
    ifc_types = {'IfcRelSpaceBoundary': ['*']}

    def __init__(self, *args, instances: dict, **kwargs):
        """spaceboundary __init__ function"""
        super().__init__(*args, **kwargs)
        self.disaggregation = []
        self.bound_instance = None
        self.bound_thermal_zone = None
        self._instances = instances

    def calc_orientation(self):
        """
        calculates the orientation of the spaceboundary, using the relative
        position of resultant disaggregation
        """
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement,
                   'BasisSurface'):
            axis = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement. \
                BasisSurface.Position.Axis.DirectionRatios
        else:
            axis = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement. \
                Position.Axis.DirectionRatios

        return vector_angle(axis)

    def calc_position(self):
        """
        calculates the position of the spaceboundary, using the relative
        position of resultant disaggregation
        """
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement,
                   'BasisSurface'):
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement. \
                BasisSurface.Position.Location.Coordinates
        else:
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement. \
                Position.Location.Coordinates

        return position

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        return True

    def validate_creation(self) -> bool:
        if self.bound_area and self.bound_area < 1e-2 * ureg.meter ** 2:
            return True
        return False

    @cached_property
    def bound_neighbors(self) -> list:
        """
        returns the neighbors of the spaceboundary
        """
        neighbors = []
        space_bounds = []
        if not hasattr(self.bound_thermal_zone, 'space_boundaries'):
            return None
        if len(self.bound_thermal_zone.space_boundaries) == 0:
            for obj in self.bound_thermal_zone.objects:
                this_obj = self.bound_thermal_zone.objects[obj]
                if not isinstance(this_obj, SpaceBoundary):
                    continue
                if this_obj.bound_thermal_zone.ifc.GlobalId != \
                        self.bound_thermal_zone.ifc.GlobalId:
                    continue
                space_bounds.append(this_obj)
        else:
            space_bounds = self.bound_thermal_zone.space_boundaries
        for bound in space_bounds:
            if bound.ifc.GlobalId == self.ifc.GlobalId:
                continue
            distance = BRepExtrema_DistShapeShape(bound.bound_shape,
                                                  self.bound_shape,
                                                  Extrema_ExtFlag_MIN).Value()
            if distance == 0:
                neighbors.append(bound)
        return neighbors

    def get_bound_area(self) -> ureg.Quantity:
        """compute area of a space boundary"""
        bound_prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, bound_prop)
        area = bound_prop.Mass()
        return area * ureg.meter ** 2

    @cached_property
    def bound_area(self) -> ureg.Quantity:
        return self.get_bound_area()

    @cached_property
    def top_bottom(self):
        """
        This function computes, if the center of a space boundary
        is below (bottom) or above (top) the center of a space.^^
        This function is used to distinguish floors and ceilings (IfcSlab)
        :return: top_bottom ("TOP", "BOTTOM")
        """
        top_bottom = None
        vertical = gp_XYZ(0.0, 0.0, 1.0)
        # only assign top and bottom for elements, whose
        # surface normals are not perpendicular to a vertical
        if -1e-3 < self.bound_normal.Dot(vertical) < 1e-3:
            top_bottom = "VERTICAL"
        elif self.related_bound != None:
            if (self.bound_center.Z() - self.related_bound.bound_center.Z()) \
                    > 1e-2:
                top_bottom = "BOTTOM"
            elif (self.bound_center.Z() - self.related_bound.bound_center.Z()) \
                    < -1e-2:
                top_bottom = "TOP"
            else:
                if vertical.Dot(self.bound_normal) < -0.8:
                    top_bottom = "BOTTOM"
                elif vertical.Dot(self.bound_normal) > 0.8:
                    top_bottom = "TOP"
        elif self.related_adb_bound is not None:
            if self.bound_center.Z() > self.related_adb_bound.bound_center.Z():
                top_bottom = "BOTTOM"
            else:
                top_bottom = "TOP"
        else:
            # direct = self.bound_center.Z() - self.thermal_zones[0].space_center.Z()
            # if direct < 0 and SpaceBoundary.compare_direction_of_normals(self.bound_normal, vertical):
            if vertical.Dot(self.bound_normal) < -0.8:
                top_bottom = "BOTTOM"
            elif vertical.Dot(self.bound_normal) > 0.8:
                top_bottom = "TOP"
        return top_bottom

    # @staticmethod
    # def compare_direction_of_normals(normal1, normal2):
    #     """
    #     Compare the direction of two surface normals (vectors).
    #     True, if direction is same or reversed
    #     :param normal1: first normal (gp_Pnt)
    #     :param normal2: second normal (gp_Pnt)
    #     :return: True/False
    #     """
    #     dotp = normal1.Dot(normal2)
    #     check = False
    #     if 1-1e-2 < dotp ** 2 < 1+1e-2:
    #         check = True
    #     return check

    def get_bound_center(self):
        """ compute center of the bounding box of a space boundary"""
        p = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, p)
        return p.CentreOfMass().XYZ()

    @cached_property
    def bound_center(self):
        return self.get_bound_center()

    @cached_property
    def related_bound(self):
        """
        Get corresponding space boundary in another space,
        ensuring that corresponding space boundaries have a matching number of
        vertices.
        """
        if hasattr(self.ifc, 'CorrespondingBoundary') and \
                self.ifc.CorrespondingBoundary is not None:
            corr_bound = self._instances.get(
                self.ifc.CorrespondingBoundary.GlobalId)
            if corr_bound:
                nb_vert_this = PyOCCTools.get_number_of_vertices(
                    self.bound_shape)
                nb_vert_other = PyOCCTools.get_number_of_vertices(
                    corr_bound.bound_shape)
                # if not nb_vert_this == nb_vert_other:
                #     print("NO VERT MATCH!:", nb_vert_this, nb_vert_other)
                if nb_vert_this == nb_vert_other:
                    return corr_bound
        if self.bound_instance is None:
            # return None
            # check for virtual bounds
            if not self.physical:
                corr_bound = None
                # cover virtual space boundaries without related IfcVirtualElement
                if not self.ifc.RelatedBuildingElement:
                    vbs = [b for b in self._instances.values() if
                           isinstance(b, SpaceBoundary) and not
                           b.ifc.RelatedBuildingElement]
                    for b in vbs:
                        if b is self:
                            continue
                        if b.ifc.RelatingSpace == self.ifc.RelatingSpace:
                            continue
                        if not (b.bound_area.m - self.bound_area.m) ** 2 < 1e-2:
                            continue
                        center_dist = gp_Pnt(self.bound_center).Distance(
                            gp_Pnt(b.bound_center)) ** 2
                        if center_dist > 0.5:
                            continue
                        corr_bound = b
                        return corr_bound
                    return None
                # cover virtual space boundaries related to an IfcVirtualElement
                if self.ifc.RelatedBuildingElement.is_a('IfcVirtualElement'):
                    if len(self.ifc.RelatedBuildingElement.ProvidesBoundaries) == 2:
                        for bound in self.ifc.RelatedBuildingElement.ProvidesBoundaries:
                            if bound.GlobalId != self.ifc.GlobalId:
                                corr_bound = self._instances[bound.GlobalId]
                                return corr_bound
        elif len(self.bound_instance.space_boundaries) == 1:
            return None
        elif len(self.bound_instance.space_boundaries) >= 2:
            own_space_id = self.bound_thermal_zone.ifc.GlobalId
            min_dist = 1000
            corr_bound = None
            for bound in self.bound_instance.space_boundaries:
                if bound.level_description != "2a":
                    continue
                if bound is self:
                    continue
                # if bound.bound_normal.Dot(self.bound_normal) != -1:
                #     continue
                other_area = bound.bound_area
                if (other_area.m - self.bound_area.m) ** 2 > 1e-1:
                    continue
                center_dist = gp_Pnt(self.bound_center).Distance(
                    gp_Pnt(bound.bound_center)) ** 2
                if abs(center_dist) > 0.5:
                    continue
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    self.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if distance > min_dist:
                    continue
                min_dist = abs(center_dist)
                # self.check_for_vertex_duplicates(bound)
                nb_vert_this = PyOCCTools.get_number_of_vertices(
                    self.bound_shape)
                nb_vert_other = PyOCCTools.get_number_of_vertices(
                    bound.bound_shape)
                # if not nb_vert_this == nb_vert_other:
                #     print("NO VERT MATCH!:", nb_vert_this, nb_vert_other)
                if nb_vert_this == nb_vert_other:
                    corr_bound = bound
            return corr_bound
        else:
            return None

    @cached_property
    def related_adb_bound(self):
        adb_bound = None
        if self.bound_instance is None:
            return None
            # check for visual bounds
        if not self.physical:
            return None
        if self.related_bound:
            if self.bound_thermal_zone == self.related_bound.bound_thermal_zone:
                adb_bound = self.related_bound
            return adb_bound
        for bound in self.bound_instance.space_boundaries:
            if bound == self:
                continue
            if not bound.bound_thermal_zone == self.bound_thermal_zone:
                continue
            if abs(bound.bound_area.m - self.bound_area.m) > 1e-3:
                continue
            if all([abs(i) < 1e-3 for i in
                    ((self.bound_normal - bound.bound_normal).Coord())]):
                continue
            if gp_Pnt(bound.bound_center).Distance(
                    gp_Pnt(self.bound_center)) < 0.4:
                adb_bound = bound
        return adb_bound

    @staticmethod
    def move_bound_in_direction_of_normal(shape, normal, move_dist,
                                          reversed=False):
        prod_vec = []
        move_dir = normal.Coord()
        if reversed:
            move_dir = normal.Reversed().Coord()
        for i in move_dir:
            prod_vec.append(move_dist * i)

        # move bound in direction of bound normal by move_dist
        trsf = gp_Trsf()
        coord = gp_XYZ(*prod_vec)
        vec = gp_Vec(coord)
        trsf.SetTranslation(vec)
        moved_shape = BRepBuilderAPI_Transform(shape, trsf).Shape()

        return moved_shape

    @cached_property
    def bound_shape(self):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)

        try:
            sore = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement
            # if sore.get_info()["InnerBoundaries"] is None:
            shape = ifcopenshell.geom.create_shape(settings, sore)

            if sore.InnerBoundaries:
                # shape = remove_inner_loops(shape)  # todo: return None if not horizontal shape
                # if not shape:
                if self.bound_instance.ifc.is_a(
                        'IfcWall'):  # todo: remove this hotfix (generalize)
                    ifc_new = ifcopenshell.file()
                    temp_sore = ifc_new.create_entity('IfcCurveBoundedPlane',
                                                      OuterBoundary=sore.OuterBoundary,
                                                      BasisSurface=sore.BasisSurface)
                    temp_sore.InnerBoundaries = ()
                    shape = ifcopenshell.geom.create_shape(settings, temp_sore)
                else:
                    shape = remove_inner_loops(shape)
            if not (sore.InnerBoundaries and not self.bound_instance.ifc.is_a(
                    'IfcWall')):
                faces = PyOCCTools.get_faces_from_shape(shape)
                if len(faces) > 1:
                    unify = ShapeUpgrade_UnifySameDomain()
                    unify.Initialize(shape)
                    unify.Build()
                    shape = unify.Shape()
                    faces = PyOCCTools.get_faces_from_shape(shape)
                    if len(faces) > 1:
                        print('hold')
                face = faces[0]
                face = PyOCCTools.remove_coincident_and_collinear_points_from_face(
                    face)
                shape = face


        except:
            try:
                sore = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement
                ifc_new = ifcopenshell.file()
                temp_sore = ifc_new.create_entity('IfcCurveBoundedPlane',
                                                  OuterBoundary=sore.OuterBoundary,
                                                  BasisSurface=sore.BasisSurface)
                temp_sore.InnerBoundaries = ()
                shape = ifcopenshell.geom.create_shape(settings, temp_sore)
            except:
                poly = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Points
                pnts = []
                for p in poly:
                    p.Coordinates = (p.Coordinates[0], p.Coordinates[1], 0.0)
                    pnts.append((p.Coordinates[:]))
                shape = PyOCCTools.make_faces_from_pnts(pnts)
        shape = BRepLib_FuseEdges(shape).Shape()

        if self.ifc.RelatingSpace.ObjectPlacement:
            lp = PyOCCTools.local_placement(
                self.ifc.RelatingSpace.ObjectPlacement).tolist()
            mat = gp_Mat(lp[0][0], lp[0][1], lp[0][2], lp[1][0], lp[1][1],
                         lp[1][2], lp[2][0], lp[2][1], lp[2][2])
            vec = gp_Vec(lp[0][3], lp[1][3], lp[2][3])
            trsf = gp_Trsf()
            trsf.SetTransformation(gp_Quaternion(mat), vec)
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape()

        # shape = shape.Reversed()
        unify = ShapeUpgrade_UnifySameDomain()
        unify.Initialize(shape)
        unify.Build()
        shape = unify.Shape()

        if self.bound_instance is not None:
            bi = self.bound_instance
            if not hasattr(bi, "related_openings"):
                return shape
            if len(bi.related_openings) == 0:
                return shape
        shape = PyOCCTools.get_face_from_shape(shape)
        return shape

    def get_transformed_shape(self, shape):
        """transform TOPODS_Shape of each space boundary to correct position"""
        zone = self.bound_thermal_zone
        zone_position = gp_XYZ(zone.position[0], zone.position[1],
                               zone.position[2])
        trsf1 = gp_Trsf()
        trsf2 = gp_Trsf()
        if zone.orientation == None:
            zone.orientation = 0
        trsf2.SetRotation(gp_Ax1(gp_Pnt(zone_position), gp_Dir(0, 0, 1)),
                          -zone.orientation * math.pi / 180)
        trsf1.SetTranslation(gp_Vec(
            gp_XYZ(zone.position[0], zone.position[1], zone.position[2])))
        try:
            shape = BRepBuilderAPI_Transform(shape, trsf1).Shape()
            shape = BRepBuilderAPI_Transform(shape, trsf2).Shape()
        except:
            pass
        return shape.Reversed()

    def compute_surface_normals_in_space(self, name):
        """
        This function returns the face normal of the boundary
        pointing outwarts the center of the space.
        Additionally, the area of the boundary is computed
        :return: face normal (gp_XYZ)
        """
        bbox_center = self.bound_thermal_zone.space_center
        an_exp = TopExp_Explorer(self.bound_shape, TopAbs_FACE)
        a_face = an_exp.Current()
        try:
            face = topods_Face(a_face)
        except:
            pnts = PyOCCTools.get_points_of_face(a_face)
            # pnts.append(pnts[0])
            face = PyOCCTools.make_faces_from_pnts(pnts)
        surf = BRep_Tool.Surface(face)
        obj = surf
        assert obj.DynamicType().Name() == "Geom_Plane"
        plane = Handle_Geom_Plane_DownCast(surf)
        # face_bbox = Bnd_Box()
        # brepbndlib_Add(face, face_bbox)
        # face_center = ifcopenshell.geom.utils.get_bounding_box_center(face_bbox).XYZ()
        face_prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, face_prop)
        area = face_prop.Mass()
        face_normal = plane.Axis().Direction().XYZ()
        if face.Orientation() == 1:
            face_normal = face_normal.Reversed()
        face_towards_center = bbox_center.XYZ() - self.bound_center
        face_towards_center.Normalize()

        dot = face_towards_center.Dot(face_normal)

        # check if surface normal points into direction of space center
        # Transform surface normals to be pointing outwards
        # For faces without reversed surface normal, reverse the orientation of the face itself
        # if dot > 0:
        #    face_normal = face_normal.Reversed()
        #     self.bound_shape = self.bound_shape.Reversed()
        # else:
        #     self.bound_shape = self.bound_shape.Reversed()

        return face_normal

    @cached_property
    def storeys(self) -> list:
        """
        This function returns the storeys associated to the spaceboundary
        """
        return self.bound_thermal_zone.storeys

    def get_level_description(self, name) -> str:
        """
        This function returns the level description of the spaceboundary
        """
        return self.ifc.Description

    @cached_property
    def is_external(self) -> bool:
        """
        This function returns True if the spaceboundary is external
        """
        return not self.ifc.InternalOrExternalBoundary.lower() == 'internal'

    @cached_property
    def physical(self) -> bool:
        """
        This function returns True if the spaceboundary is physical
        """
        return self.ifc.PhysicalOrVirtualBoundary.lower() == 'physical'

    @cached_property
    def opening_area(self):
        """
        This function returns the opening area of the spaceboundary
        """
        if self.opening_bounds:
            return sum(opening_boundary.bound_area for opening_boundary
                       in self.opening_bounds)
        return 0

    @cached_property
    def net_bound_area(self):
        """
        This function returns the net bound area of the spaceboundary
        """
        return self.bound_area - self.opening_area

    @cached_property
    def bound_normal(self):
        """
        This function returns the normal vector of the spaceboundary
        """
        return PyOCCTools.simple_face_normal(self.bound_shape)

    level_description = attribute.Attribute(
        functions=[get_level_description],
        # Todo this should be removed in near future. We should either 
        # find # a way to distinguish the level of SB by something 
        # different or should check this during the creation of SBs 
        # and throw an error if the level is not defined.
        default='2a'
        # HACK: Rou's Model has 2a boundaries but, the description is None,
        # default set to 2a to temporary solve this problem
    )

    @cached_property
    def opening_bounds(self):
        """
        This function returns the opening bounds of the spaceboundary
        """
        return list()

    @cached_property
    def parent_bound(self):
        """
        This function returns the parent bound of the space boundary. Only
        available for space boundary of openings. The parent boundary of an
        opening boundary is the boundary of the wall which surrounds the
        opening.
        """
        return None


class ExtSpatialSpaceBoundary(SpaceBoundary):
    """describes all space boundaries related to an IfcExternalSpatialElement instead of an IfcSpace"""
    pass


class SpaceBoundary2B(SpaceBoundary):
    """describes all newly created space boundaries of type 2b to fill gaps within spaces"""

    def __init__(self, *args, instances=None, **kwargs):
        super(SpaceBoundary2B, self).__init__(*args, instances=None, **kwargs)
        self.ifc = ifcopenshell.create_entity('IfcRelSpaceBoundary')
        self.guid = None
        self.bound_shape = None
        self.thermal_zones = []
        self.bound_instance = None
        self.physical = True
        self.is_external = False
        self.related_bound = None
        self.related_adb_bound = None
        self.level_description = '2b'


class BPSProductWithLayers(BPSProduct):
    ifc_types = {}

    def __init__(self, *args, **kwargs):
        """BPSProductWithLayers __init__ function"""
        super().__init__(*args, **kwargs)
        self.layerset = None

    def get_u_value(self, name):
        """wall get_u_value function"""
        layers_r = 0
        for layer in self.layerset.layers:
            if layer.thickness:
                if layer.material.thermal_conduc and \
                        layer.material.thermal_conduc > 0:
                    layers_r += layer.thickness / layer.material.thermal_conduc

        if layers_r > 0:
            return 1 / layers_r
        return None

    def get_thickness_by_layers(self, name):
        """calculate the total thickness of the product based on the thickness
        of each layer."""
        thickness = 0
        for layer in self.layerset.layers:
            if layer.thickness:
                thickness += layer.thickness
        return thickness


class Wall(BPSProductWithLayers):
    ifc_types = {
        "IfcWall":
            ['*', 'MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL',
             'SHEAR', 'SOLIDWALL', 'POLYGONAL', 'DOOR', 'GATE', 'TRAPDOOR'],
        "IfcWallStandardCase":
            ['*', 'MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL',
             'SHEAR', 'SOLIDWALL', 'POLYGONAL', 'DOOR', 'GATE', 'TRAPDOOR'],
        # "IfcElementedCase": "?"  # TODO
    }

    conditions = [
        condition.RangeCondition('u_value',
                                 0 * ureg.W / ureg.K / ureg.meter ** 2,
                                 5 * ureg.W / ureg.K / ureg.meter ** 2,
                                 critical_for_creation=False),
        condition.UValueCondition('u_value',
                                  threshold=0.2,
                                  critical_for_creation=False),
    ]

    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
    ]

    def __init__(self, *args, **kwargs):
        """wall __init__ function"""
        super().__init__(*args, **kwargs)

    def get_better_subclass(self):
        return OuterWall if self.is_external else InnerWall

    net_area = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "NetSideArea"),
        functions=[BPSProduct.get_net_bound_area],
        unit=ureg.meter ** 2
    )
    gross_area = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "GrossSideArea"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )
    tilt = attribute.Attribute(
        default=90
    )

    u_value = attribute.Attribute(
        default_ps=("Pset_WallCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )
    width = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "Width"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )
    inner_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        default=0.6
    )

    is_load_bearing = attribute.Attribute(
        default_ps=("Pset_WallCommon", "LoadBearing"),
    )
    net_volume = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "NetVolume"),
        unit=ureg.meter ** 3
    )

    gross_volume = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "GrossVolume")
    )


class Layer(BPSProduct):
    """Represents the IfcMaterialLayer class."""
    ifc_types = {
        "IfcMaterialLayer": ["*"],
    }

    conditions = [
        condition.RangeCondition('thickness',
                                 0 * ureg.m,
                                 10 * ureg.m,
                                 critical_for_creation=False, incl_edges=False)
    ]

    def __init__(self,  *args, **kwargs):
        """layer __init__ function"""
        super().__init__(*args, **kwargs)
        self.to_layerset: List[LayerSet] = []
        self.parent = None
        self.material = None

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        return True

    def validate_creation(self) -> bool:
        return True

    def get_thickness(self, name):
        """layer thickness function"""
        if hasattr(self.ifc, 'LayerThickness'):
            return self.ifc.LayerThickness * ureg.meter
        else:
            return float('nan') * ureg.meter

    thickness = attribute.Attribute(
        unit=ureg.m,
        functions=[get_thickness]
    )

    @cached_property
    def is_ventilated(self):
        if hasattr(self.ifc, 'IsVentilated'):
            return self.ifc.IsVentilated

    @cached_property
    def description(self):
        if hasattr(self.ifc, 'Description'):
            return self.ifc.Description

    @cached_property
    def category(self):
        """needs usage. This can be one of [LoadBearing, Insulation,
        Inner finish, Outer finish] due to IFC4_1 schema."""
        if hasattr(self.ifc, 'Category'):
            return self.ifc.Category

    def __repr__(self):
        return "<%s (material: %s>" \
               % (self.__class__.__name__, self.material)


class LayerSet(BPSProduct):

    ifc_types = {
        "IfcMaterialLayerSet": ["*"],
    }

    conditions = [
        condition.ListCondition('layers',
                                critical_for_creation=False),
        condition.ThicknessCondition('total_thickness',
                                     threshold=0.2,
                                     critical_for_creation=False),
    ]

    def __init__(self, *args, **kwargs):
        """layerset __init__ function"""
        super().__init__(*args, **kwargs)
        self.parents: List[BPSProductWithLayers] = []
        self.layers: List[Layer] = []

    def get_total_thickness(self, name):
        if hasattr(self.ifc, 'TotalThickness'):
            if self.ifc.TotalThickness:
                return self.ifc.TotalThickness * ureg.m
        return sum(layer.thickness for layer in self.layers)

    thickness = attribute.Attribute(
        unit=ureg.m,
        functions=[get_total_thickness],
    )

    @cached_property
    def name(self):
        if hasattr(self.ifc, 'LayerSetName'):
            return self.ifc.LayerSetName

    @cached_property
    def volume(self):
        if hasattr(self, "net_volume"):
            if self.net_volume:
                vol = self.net_volume
                return vol
            # TODO This is not working currently, because with multiple parents
            #  we dont know the area or width of the parent
            # elif self.parent.width:
            #     vol = self.parent.volume * self.parent.width / self.thickness
            else:
                vol = float('nan') * ureg.meter ** 3
        # TODO see above
        # elif self.parent.width:
        #     vol = self.parent.volume * self.parent.width / self.thickness
        else:
            vol = float('nan') * ureg.meter ** 3
        return vol

    def __repr__(self):
        if self.name:
            return "<%s (name: %s, layers: %d)>" \
                   % (self.__class__.__name__, self.name, len(self.layers))
        else:
            return "<%s (layers: %d)>" % (self.__class__.__name__, len(self.layers))


class OuterWall(Wall):
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for OuterWall

        Load bearing outer walls: 331
        Not load bearing outer walls: 332
        Rest: 330
        """

        if self.is_load_bearing:
            return 331
        elif not self.is_load_bearing:
            return 332
        else:
            return 330


class InnerWall(Wall):
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for InnerWall

        Load bearing inner walls: 341
        Not load bearing inner walls: 342
        Rest: 340
        """

        if self.is_load_bearing:
            return 341
        elif not self.is_load_bearing:
            return 342
        else:
            return 340


class Window(BPSProductWithLayers):
    ifc_types = {"IfcWindow": ['*', 'WINDOW', 'SKYLIGHT', 'LIGHTDOME']}

    pattern_ifc_type = [
        re.compile('Window', flags=re.IGNORECASE),
        re.compile('Fenster', flags=re.IGNORECASE)
    ]

    def get_glazing_area(self, name):
        """returns only the glazing area of the windows"""
        if self.glazing_ratio:
            return self.gross_area * self.glazing_ratio
        return self.opening_area

    def calc_cost_group(self) -> int:
        """Calc cost group for Windows

        Outer door: 334
        """

        return 334

    net_area = attribute.Attribute(
        functions=[get_glazing_area],
        unit=ureg.meter ** 2,
        dependant_attributes=['glazing_ratio', 'gross_area', 'opening_area']
    )
    gross_area = attribute.Attribute(
        default_ps=("Qto_WindowBaseQuantities", "Area"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )
    glazing_ratio = attribute.Attribute(
        default_ps=("Pset_WindowCommon", "GlazingAreaFraction"),
    )
    width = attribute.Attribute(
        default_ps=("Qto_WindowBaseQuantities", "Depth"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )
    u_value = attribute.Attribute(
        default_ps=("Pset_WallCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )
    g_value = attribute.Attribute(  # material
    )
    a_conv = attribute.Attribute(
    )
    shading_g_total = attribute.Attribute(
    )
    shading_max_irr = attribute.Attribute(
    )
    inner_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    inner_radiation = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    outer_radiation = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    outer_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )


class Door(BPSProductWithLayers):
    ifc_types = {"IfcDoor": ['*', 'DOOR', 'GATE', 'TRAPDOOR']}

    pattern_ifc_type = [
        re.compile('Door', flags=re.IGNORECASE),
        re.compile('Tuer', flags=re.IGNORECASE)
    ]

    conditions = [
        condition.RangeCondition('glazing_ratio',
                                 0 * ureg.dimensionless,
                                 1 * ureg.dimensionless, True,
                                 critical_for_creation=False),
    ]

    def get_better_subclass(self):
        return OuterDoor if self.is_external else InnerDoor

    def get_net_area(self, name):
        if self.glazing_ratio:
            return self.gross_area * (1 - self.glazing_ratio)
        return self.gross_area - self.opening_area

    net_area = attribute.Attribute(
        functions=[get_net_area, ],
        unit=ureg.meter ** 2,
    )
    gross_area = attribute.Attribute(
        default_ps=("Qto_DoorBaseQuantities", "Area"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )
    glazing_ratio = attribute.Attribute(
        default_ps=("Pset_DoorCommon", "GlazingAreaFraction"),
    )

    width = attribute.Attribute(
        default_ps=("Qto_DoorBaseQuantities", "Width"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )
    u_value = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )
    inner_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        default=0.6
    )
    inner_radiation = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    outer_radiation = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    outer_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )


class InnerDoor(Door):
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for Innerdoors

        Inner door: 344
        """

        return 344


class OuterDoor(Door):
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for Outerdoors

        Outer door: 334
        """

        return 334


class Plate(BPSProductWithLayers):
    ifc_types = {"IfcPlate": ['*', 'CURTAIN_PANEL', 'SHEET']}

    def calc_cost_group(self) -> int:
        """Calc cost group for Plates

        External: 337
        Internal: 346
        """
        if self.is_external:
            return 337
        elif not self.is_external:
            return 346
        else:
            return 300

    width = attribute.Attribute(
        default_ps=("Qto_PlateBaseQuantities", "Width"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )

    net_volume = attribute.Attribute(
        default_ps=("Qto_PlateBaseQuantities", "NetVolume"),
        unit=ureg.m **3
    )

    gross_volume = attribute.Attribute(
        default_ps=("Qto_PlateBaseQuantities", "GrossVolume"),
        unit=ureg.m **3
    )

    net_area = attribute.Attribute(
        default_ps=("Qto_PlateBaseQuantities", "NetArea"),
        unit=ureg.m **3
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_PlateBaseQuantities", "GrossArea"),
        unit=ureg.m **3
    )
    net_weight = attribute.Attribute(
        default_ps=("Qto_PlateBaseQuantities", "NetWeight"),
        unit=ureg.m **3
    )

    gross_weight = attribute.Attribute(
        default_ps=("Qto_PlateBaseQuantities", "GrossWeight"),
        unit=ureg.m **3
    )

    is_load_bearing = attribute.Attribute(
        default_ps=("Pset_PlateCommon", "LoadBearing"),
    )
    u_value = attribute.Attribute(
        default_ps=("Pset_PlateCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )


class Slab(BPSProductWithLayers):
    ifc_types = {
        "IfcSlab": ['*', 'LANDING']
    }

    def __init__(self, *args, **kwargs):
        """slab __init__ function"""
        super().__init__(*args, **kwargs)

    @cached_property
    def orientation(self) -> float:
        """Returns the orientation of the slab"""
        return -1

    net_area = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "NetArea"),
        functions=[BPSProduct.get_net_bound_area],
        unit=ureg.meter ** 2
    )
    gross_area = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "GrossArea"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )
    width = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "Width"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )
    u_value = attribute.Attribute(
        default_ps=("Pset_SlabCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )
    net_volume = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "NetVolume"),
        unit=ureg.meter ** 3
    )
    is_load_bearing = attribute.Attribute(
        default_ps=("Pset_SlabCommon", "LoadBearing"),
    )


class Roof(Slab):
    # todo decomposed roofs dont have materials, layers etc. because these
    #  information are stored in the slab itself and not the decomposition
    is_external = True
    ifc_types = {
        "IfcRoof":
            ['*', 'FLAT_ROOF', 'SHED_ROOF', 'GABLE_ROOF', 'HIP_ROOF',
             'HIPPED_GABLE_ROOF', 'GAMBREL_ROOF', 'MANSARD_ROOF',
             'BARREL_ROOF', 'RAINBOW_ROOF', 'BUTTERFLY_ROOF', 'PAVILION_ROOF',
             'DOME_ROOF', 'FREEFORM'],
        "IfcSlab": ['ROOF']
    }

    @cached_property
    def orientation(self) -> float:
        """Returns the orientation of the roof"""
        return -1
    def calc_cost_group(self) -> int:
        """Calc cost group for Roofs


        Load bearing: 361
        Not load bearing: 363
        """
        if self.is_load_bearing:
            return 361
        elif not self.is_load_bearing:
            return 363
        else:
            return 300


class Floor(Slab):
    ifc_types = {
        "IfcSlab": ['FLOOR']
    }

    @cached_property
    def orientation(self) -> float:
        """Returns the orientation of the floor"""
        return -2

    def calc_cost_group(self) -> int:
        """Calc cost group for Floors

        Floor: 351
        """
        return 351


class GroundFloor(Slab):
    is_external = True  # todo to be removed
    ifc_types = {
        "IfcSlab": ['BASESLAB']
    }

    def calc_cost_group(self) -> int:
        """Calc cost group for groundfloors

        groundfloors: 322
        """

        return 322

    # pattern_ifc_type = [
    #     re.compile('Bodenplatte', flags=re.IGNORECASE),
    #     re.compile('')
    # ]

    @cached_property
    def orientation(self) -> float:
        """Returns the orientation of the ground-floor"""
        return -2


class Site(BPSProduct):
    ifc_types = {"IfcSite": ['*']}

    gross_area = attribute.Attribute(
        default_ps=("Qto_SiteBaseQuantities", "GrossArea"),
        unit=ureg.meter ** 2
    )


class Building(BPSProduct):
    ifc_types = {"IfcBuilding": ['*']}

    conditions = [
        condition.RangeCondition('year_of_construction',
                                 1900 * ureg.year,
                                 date.today().year * ureg.year,
                                 critical_for_creation=False),
    ]

    def _get_building_name(self, name):
        """get building name"""
        bldg_name = self.get_ifc_attribute('Name')
        if bldg_name:
            return bldg_name
        else:
            # todo needs to be adjusted for multiple buildings #165
            bldg_name = 'Building'
        return bldg_name

    bldg_name = attribute.Attribute(
        functions=[_get_building_name],
    )
    year_of_construction = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "YearOfConstruction"),
        unit=ureg.year
    )
    gross_area = attribute.Attribute(
        default_ps=("Qto_BuildingBaseQuantities", "GrossFloorArea"),
        unit=ureg.meter ** 2
    )
    net_area = attribute.Attribute(
        default_ps=("Qto_BuildingBaseQuantities", "NetFloorArea"),
        unit=ureg.meter ** 2
    )

    def _get_number_of_storeys(self, name):
        return len(self.storeys)

    number_of_storeys = attribute.Attribute(
        unit=ureg.dimensionless,
        functions=[_get_number_of_storeys]
    )
    occupancy_type = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "OccupancyType"),
    )


class Storey(BPSProduct):
    ifc_types = {'IfcBuildingStorey': ['*']}

    def __init__(self, *args, **kwargs):
        """storey __init__ function"""
        super().__init__(*args, **kwargs)
        self.storey_instances = []

    spec_machines_internal_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria",
                    "ReceptacleLoadIntensity"),
        unit=ureg.kilowatt / (ureg.meter ** 2)
    )

    spec_lighting_internal_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria", "LightingLoadIntensity"),
        unit=ureg.kilowatt / (ureg.meter ** 2)
    )

    cooling_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadAggregate", "TotalCoolingLoad"),
        unit=ureg.kilowatt
    )

    heating_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadAggregate", "TotalHeatingLoad"),
        unit=ureg.kilowatt
    )

    air_per_person = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria", "OutsideAirPerPerson"),
        unit=ureg.meter ** 3 / ureg.hour
    )

    percent_load_to_radiant = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria",
                    "AppliancePercentLoadToRadiant"),
        unit=ureg.percent
    )

    gross_floor_area = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "GrossFloorArea"),
        unit=ureg.meter ** 2
    )
    # todo make the lookup for height hierarchical
    net_height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "NetHeight"),
        unit=ureg.meter
    )
    gross_height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "GrossHeight"),
        unit=ureg.meter
    )
    height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "Height"),
        unit=ureg.meter
    )


class SpaceBoundaryRepresentation(BPSProduct):
    """describes the geometric representation of space boundaries which are
    created by the webtool to allow the """
    ifc_types = {
        "IFCBUILDINGELEMENTPROXY":
            ['USERDEFINED']
    }
    pattern_ifc_type = [
        re.compile('ProxyBound', flags=re.IGNORECASE)
    ]

    # todo look at #201


class Covering(BPSProduct):
    # todo connect covering with element via CoversElements and CoversSpaces
    ifc_types = {'IfcCovering': [
        'CEILING',
        'FLOORING',
        'CLADDING',
        'ROOFING',
        'MODLING',
        'SKIRTINGBOARD'
    ]
    }

    def __init__(self, *args, **kwargs):
        """Covering __init__ function"""
        super().__init__(*args, **kwargs)

    def calc_cost_group(self) -> int:
        """Calc cost group for Coverings
        """

        if self.predefined_type == "CEILING":
            return 354
        elif self.predefined_type == "ROOFING":
            return 364
        elif self.predefined_type == "FLOORING":
            return 353
        elif self.predefined_type == "CLADDING" and self.is_external:
            return 335
        elif self.predefined_type == "ROOFING" and not self.is_external:
            return 336
        elif self.predefined_type == "MOLDING" and self.is_external:
            return 339
        elif self.predefined_type == "MOLDING" and not self.is_external:
            return 349
        elif self.predefined_type == "SKIRTINGBOARD" and not self.is_external:
            return 349
        elif self.is_external:
            return 330
        elif not self.is_external:
            return 340
        else:
            return 300

    width = attribute.Attribute(
        default_ps=("Qto_CoveringBaseQuantities", "Width"),
        unit=ureg.m
     )
    gross_area = attribute.Attribute(
        default_ps=("Qto_CoveringBaseQuantities", "GrossArea"),
        unit=ureg.meter ** 2
    )
    net_area = attribute.Attribute(
        default_ps=("Qto_CoveringBaseQuantities", "NetArea"),
        unit=ureg.meter ** 2
    )


class Insulation(Covering):
    ifc_types = {'IfcCovering': ['INSULATION']}
    pattern_ifc_type = [
        re.compile('Dämmung', flags=re.IGNORECASE),
        re.compile('Isolierung', flags=re.IGNORECASE),
        re.compile('Isolation', flags=re.IGNORECASE),
        re.compile('Insulation', flags=re.IGNORECASE),
    ]

    def __init__(self, *args, **kwargs):
        """Insulation __init__ function"""
        super().__init__(*args, **kwargs)

    def calc_cost_group(self) -> int:
        """Calc cost group for Insulations

        External: 330
        Internal: 340
        """
        if self.is_external:
            return 330
        elif not self.is_external:
            return 340
        else:
            return 300


# collect all domain classes
items: Set[BPSProduct] = set()
for name, cls in inspect.getmembers(
        sys.modules[__name__],
        lambda member: inspect.isclass(member)  # class at all
        and issubclass(member, BPSProduct)  # domain subclass
        and member is not BPSProduct  # but not base class
        and member.__module__ == __name__):  # declared here
    items.add(cls)
