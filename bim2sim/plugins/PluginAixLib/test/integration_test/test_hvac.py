import unittest
from collections import Counter

from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.export.modelica import Instance
from bim2sim.kernel.aggregation import ConsumerHeatingDistributorModule
from bim2sim.utilities.test import IntegrationBase


class IntegrationBaseAixLib(IntegrationBase):
    def tearDown(self):
        Instance.lookup = {}
        super().tearDown()

    def model_domain_path(self) -> str:
        return 'HVAC'


class TestIntegrationAixLib(IntegrationBaseAixLib, unittest.TestCase):

    def test_vereinshaus1_aixlib(self):
        """Run project with
        KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
        project = self.create_project(ifc, 'aixlib')
        answers = ('HVAC-HeatPump', 'HVAC-Storage', 'HVAC-Storage',
                   '2lU4kSSzH16v7KPrwcL7KZ', '0t2j$jKmf74PQpOI0ZmPCc',
                   # 1x expansion tank and 17x dead end
                   *(True,)*18,
                   # boiler efficiency
                   0.9,
                   # boiler power
                   150,
                   # current, height, voltage, vol_flow of pump
                   *(2, 5, 230, 1) * 2,
                   # power of space heaters
                   *(1,) * 11)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_b03_heating(self):
        """Run project with 2022_11_21_update_B03_Heating_ownCells"""
        ifc = '2022_11_21_update_B03_Heating_ownCells.ifc'
        project = self.create_project(ifc, 'aixlib')
        project.workflow.aggregations = [
            'UnderfloorHeating',
            'Consumer',
            'PipeStrand',
            'ParallelPump',
            'ConsumerHeatingDistributorModule',
        ]
        answers = (None, 'HVAC-PipeFitting', 'HVAC-Distributor',
                   'HVAC-ThreeWayValve',
                   # 7 dead ends
                   *(True,)*7,
                   # boiler efficiency, flow temp, power consumption,
                   #  return temp
                   0.95, 70, 79, 50,
                   # rated_mass_flow for boiler pump, rated dp of boiler pump
                   0.9, 4500,
                   # body mass and heat capacity for all space heaters
                   *(500,) * 7
                   )
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_b03_heating_all_aggregations(self):
        """Run project with 2022_11_21_update_B03_Heating_ownCells"""
        ifc = '2022_11_21_update_B03_Heating_ownCells.ifc'
        project = self.create_project(ifc, 'aixlib')
        answers = (None, 'HVAC-PipeFitting', 'HVAC-Distributor',
                   'HVAC-ThreeWayValve',
                   # 6 dead ends
                   *(True,) * 6,
                   # boiler efficiency, flow temp, power consumption,
                   #  return temp
                   0.95, 70, 79, 50,
                   # heat capacity for all space heaters
                   *(500,) * 7,
                   )
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        graph = project.playground.state['graph']
        aggregated = Counter((type(item) for item in graph.element_graph.nodes))
        # TODO check generator
        self.assertIn(ConsumerHeatingDistributorModule, aggregated)
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    # def test_run_digitalhub_hvac(self):
    #     """Run project with FM_HZG_DigitalHub.ifc"""
    #     ifc = 'FM_HZG_DigitalHub.ifc'
    #     project = self.create_project(ifc, 'aixlib')
    #     answers = (('HVAC-ThreeWayValve')*3, ('HVAC-PipeFitting')*19,   *(None,)*100,)
    #     handler = DebugDecisionHandler(answers)
    #     project.workflow.fuzzy_threshold = 0.5
    #     for decision, answer in handler.decision_answer_mapping(project.run()):
    #         decision.value = answer
    #     print('test')
