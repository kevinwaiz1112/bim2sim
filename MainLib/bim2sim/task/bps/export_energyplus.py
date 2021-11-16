# todo delete this after seperating energyplus tasks into single tasks
"""This module holds tasks related to bps"""
import subprocess

import ifcopenshell

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.gp import gp_Pnt
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps

from bim2sim.task.base import ITask
from bim2sim.decision import BoolDecision, DecisionBunch
# todo new name :)
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim_energyplus.utils import PostprocessingUtils


class ExportEP(ITask):
    """Exports an EnergyPlus model based on IFC information"""

    reads = ('instances', 'ifc', 'idf',)
    final = True

    def run(self, workflow, instances, ifc, idf):
        # self._get_neighbor_bounds(instances)
        # self._compute_2b_bound_gaps(instances) # todo: fix
        pass

    @staticmethod
    def _get_neighbor_bounds(instances):
        for inst in instances:
            this_obj = instances[inst]
            if not this_obj.ifc.is_a('IfcRelSpaceBoundary'):
                continue
            neighbors = this_obj.bound_neighbors

    def _compute_2b_bound_gaps(self, instances):
        self.logger.info("Generate space boundaries of type 2B")
        inst_2b = dict()
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space_obj = instances[inst]
            space_obj.b_bound_shape = space_obj.space_shape
            for bound in space_obj.space_boundaries:
                if bound.bound_area.m == 0:
                    continue
                bound_prop = GProp_GProps()
                brepgprop_SurfaceProperties(space_obj.b_bound_shape, bound_prop)
                b_bound_area = bound_prop.Mass()
                if b_bound_area == 0:
                    continue
                distance = BRepExtrema_DistShapeShape(
                    space_obj.b_bound_shape,
                    bound.bound_shape,
                    Extrema_ExtFlag_MIN).Value()
                if distance > 1e-6:
                    continue
                space_obj.b_bound_shape = BRepAlgoAPI_Cut(space_obj.b_bound_shape, bound.bound_shape).Shape()
            faces = PyOCCTools.get_faces_from_shape(space_obj.b_bound_shape)
            inst_2b.update(self.create_2B_space_boundaries(faces, space_obj))
        instances.update(inst_2b)

    def create_2B_space_boundaries(self, faces, space_obj):
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        inst_2b = dict()
        space_obj.space_boundaries_2B = []
        bound_obj = []
        for bound in space_obj.space_boundaries:
            if bound.bound_instance is not None:
                bi = bound.bound_instance.ifc
                bound.bound_instance.shape = ifcopenshell.geom.create_shape(settings, bi).geometry
                bound_obj.append(bound.bound_instance)
        for i, face in enumerate(faces):
            b_bound = SpaceBoundary2B()
            b_bound.bound_shape = face
            if b_bound.bound_area.m < 1e-6:
                continue
            b_bound.guid = space_obj.guid + "_2B_" + str("%003.f" % (i + 1))
            b_bound.thermal_zones.append(space_obj)
            for instance in bound_obj:
                if hasattr(instance, 'related_parent'):
                    continue
                center_shape = BRepBuilderAPI_MakeVertex(gp_Pnt(b_bound.bound_center)).Shape()
                distance = BRepExtrema_DistShapeShape(center_shape, instance.shape, Extrema_ExtFlag_MIN).Value()
                if distance < 1e-3:
                    b_bound.bound_instance = instance
                    break
            space_obj.space_boundaries_2B.append(b_bound)
            inst_2b[b_bound.guid] = b_bound
            for bound in space_obj.space_boundaries:
                distance = BRepExtrema_DistShapeShape(bound.bound_shape, b_bound.bound_shape,
                                                      Extrema_ExtFlag_MIN).Value()
                if distance == 0:
                    b_bound.bound_neighbors.append(bound)
                    if not hasattr(bound, 'bound_neighbors_2b'):
                        bound.bound_neighbors_2b = []
                    bound.bound_neighbors_2b.append(b_bound)
        return inst_2b


class RunEnergyPlusSimulation(ITask):
    reads = ('idf', )

    def run(self, workflow, idf):
        subprocess.run(['energyplus', '-x', '-c', '--convert-only', '-d', self.paths.export, idf.idfname])
        run_decision = BoolDecision(
            question="Do you want to run the full energyplus simulation"
                     " (annual, readvars)?",
            global_key='EnergyPlus.FullRun')
        yield DecisionBunch([run_decision])
        ep_full = run_decision.value
        design_day = False
        if not ep_full:
            design_day = True
        output_string = str(self.paths.export / 'EP-results/')
        idf.run(output_directory=output_string, readvars=ep_full, annual=ep_full, design_day=design_day)
        # if ep_full:
        #     PostprocessingUtils._visualize_results(csv_name=self.paths.export / 'EP-results/eplusout.csv')
