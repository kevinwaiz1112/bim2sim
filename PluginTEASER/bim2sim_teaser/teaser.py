
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.task import bps
from bim2sim.task.sub_tasks import tz_detection


class TEASERManager(BIM2SIMManager):

    def __init__(self, workflow):
        super().__init__(workflow)

    def run(self):
        # prepare = bps.Prepare()
        # prepare.run(bps.IFC_TYPES)
        #
        # inspect = bps.Inspect()
        # if not inspect.load(PROJECT.workflow):
        #     inspect.run(self.ifc, bps.IFC_TYPES)
        #     inspect.save(PROJECT.workflow)
        #
        ### Thermalzones
        bps_inspect = bps.Inspect(self.workflow)
        bps_inspect.run(self.ifc)
        tz_inspect = tz_detection.Inspect(bps_inspect)
        tz_inspect.run(self.ifc)
        pass


        # libraries = (standardlibrary.StandardLibrary, HKESim)
        # export = bps.Export()
        # export.run(libraries, reduce.reduced_instances, reduce.connections)



