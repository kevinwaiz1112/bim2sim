﻿"""Package for Python representations of HKESim models"""

from bim2sim.export import modelica
from bim2sim.ifc2python import elements
from bim2sim.ifc2python.aggregation import PipeStrand

from bim2sim.export.modelica import standardlibrary # impor necessary for model detection

class AixLib(modelica.Instance):
    library = "AixLib"


class Boiler(AixLib):
    path = "AixLib.FastHVAC.Components.HeatGenerators.Boiler.Boiler"
    represents = elements.Boiler

    def __init__(self, element):
        self.check_power = self.check_numeric(min_value=0) #TODO: Checking System
        super().__init__(element)

    def get_params(self):
        self.manage_param("nominal_power", self.element.rated_power,
                          self.check_power)



