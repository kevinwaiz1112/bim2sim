import unittest
import os
import warnings

from pathlib import Path

from bim2sim import workflow
from bim2sim.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase


class IntegrationBaseCFD(IntegrationBase):
    def tearDown(self):
        super().tearDown()

    def model_path(self) -> Path:
        return Path(__file__).parent.parent.parent / 'test/TestModels/BPS'


class TestIntegrationCFD(IntegrationBaseCFD, unittest.TestCase):

    # @unittest.skip("")
    def test_run_kitfzkhaus_spaces_low_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        if os.name == 'posix':  # only linux
            ifc = 'AC20-FZK-Haus.ifc'
            used_workflow = workflow.CFDWorkflow()
            project = self.create_project(ifc, 'CFD', used_workflow)
            answers = ("--cfd", 8)
            handler = DebugDecisionHandler(answers)
            for decision, answer in handler.decision_answer_mapping(
                    project.run()):
                decision.value = answer
            self.assertEqual(0, handler.return_value,
                             "Project did not finish successfully.")
        else:
            warnings.warn("Current OS not linux. This test will be skipped.")
