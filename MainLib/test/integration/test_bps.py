import unittest

import bim2sim


# ------------------------------------------------------------------------------
# WARNING: run only one test per interpreter Instance.
# To use tests uncomment line below und run single test
# ------------------------------------------------------------------------------
# raise unittest.SkipTest("Integration tests not reliable for automated use")


class TestIntegrationTEASER(IntegrationBase, unittest.TestCase):

    def test_run_kitfzkhaus_spaces_low_layers_low(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        answers = (True, True, 'Living', 'heavy', 'EnEv')
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'TEASER')
        self.assertEqual(0, return_code, "Project did not finish successfully.")

    def test_run_kitoffice_spaces_low_layers_low(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        answers = (True, True, 'Open-plan Office (7 or more employees)', 2015, 'heavy', 'EnEv')
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'TEASER')
        self.assertEqual(0, return_code, "Project did not finish successfully.")

    # def test_run_kitfzkhaus_spaces_medium_layers_low(self):
    #     """Run project with AC20-FZK-Haus.ifc"""
    #     ifc = 'AC20-FZK-Haus.ifc'
    #     answers = (True, True, 'Kitchen - preparations, storage', 'heavy', 'EnEv', False)
    #     with bim2sim.decision.Decision.debug_answer(answers, multi=True):
    #         return_code = self.run_project(ifc, 'TEASER')
    #     self.assertEqual(0, return_code, "Project did not finish successfully.")

    # def test_run_kitoffice_spaces_medium_layers_low(self):
    #     """Run project with AC20-Institute-Var-2.ifc"""
    #     ifc = 'AC20-Institute-Var-2.ifc'
    #     answers = (True, True, 2015, 'heavy', 'EnEv', False)
    #     with bim2sim.decision.Decision.debug_answer(answers, multi=True):
    #         return_code = self.run_project(ifc, 'TEASER')
    #     self.assertEqual(0, return_code, "Project did not finish successfully.")

    # def test_run_kitfzkhaus_spaces_medium_layers_full(self):
    #     """Run project with AC20-FZK-Haus.ifc"""
    #     ifc = 'AC20-FZK-Haus.ifc'
    #     answers = (True, True, 'Kitchen - preparations, storage', True, 'Concrete_DK', True, 'hardwood', True,
    #                'Light_Concrete_DK', True, 'solid_brick_a', 'heavy', 1, 'Brick', 'brick_H', 'EnEv', 1, 'Glas',
    #                'glas_generic', False)
    #     # test -> spaces-full, layer-full
    #     # answers = ()
    #     with bim2sim.decision.Decision.debug_answer(answers, multi=True):
    #         return_code = self.run_project(ifc, 'TEASER')
    #     self.assertEqual(0, return_code, "Project did not finish successfully.")

    # def test_run_kitoffice_spaces_medium_layers_full(self):
    #     """Run project with AC20-Institute-Var-2.ifc"""
    #     ifc = 'AC20-Institute-Var-2.ifc'
    #     answers = (True, True, True, 'belgian_brick', 'Glas', True, 'glas_generic', 500, 1.5, 0.2, True, 'air_layer',
    #                0.1, True, 'Concrete_DK', 2015, 'heavy', 1, 'Beton', 'Light_Concrete_DK', 1, 'Beton', 1, 'Door', 1,
    #                'Beton', False)
    #     with bim2sim.decision.Decision.debug_answer(answers, multi=True):
    #         return_code = self.run_project(ifc, 'TEASER')
    #     self.assertEqual(0, return_code, "Project did not finish successfully.")

    # def test_run_kitfzkhaus_spaces_full_layers_full(self):
    #     """Run project with AC20-FZK-Haus.ifc"""
    #     ifc = 'AC20-FZK-Haus.ifc'
    #     answers = (True, True, 'Kitchen - preparations, storage', True, 'Concrete_DK', True, 'hardwood', True,
    #                'Light_Concrete_DK', True, 'solid_brick_a', 'heavy', 1, 'Brick', 'brick_H', 'EnEv', 1, 'Glas',
    #                'glas_generic')
    #     with bim2sim.decision.Decision.debug_answer(answers, multi=True):
    #         return_code = self.run_project(ifc, 'TEASER')
    #     self.assertEqual(0, return_code, "Project did not finish successfully.")

    # def test_run_kitoffice_spaces_full_layers_full(self):
    #     """Run project with AC20-Institute-Var-2.ifc"""
    #     ifc = 'AC20-Institute-Var-2.ifc'
    #     answers = (True, True, True, 'belgian_brick', 'Glas', True, 'glas_generic', 500, 1.5, 0.2, True, 'air_layer',
    #                0.1, True, 'Concrete_DK', 2015, 'heavy', 1, 'Beton', 'Light_Concrete_DK', 1, 'Beton', 1, 'Door', 1,
    #                'Beton')
    #     with bim2sim.decision.Decision.debug_answer(answers, multi=True):
    #         return_code = self.run_project(ifc, 'TEASER')
    #     self.assertEqual(0, return_code, "Project did not finish successfully.")


class TestIntegrationAixLib(unittest.TestCase):
    pass