﻿"""Testing Finders
"""

import unittest
import os
import tempfile
import shutil

import bim2sim
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python import element, elements
from bim2sim.ifc2python.finder import TemplateFinder

IFC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(bim2sim.__file__), '../..', 
    r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))

class Test_TemplateFinder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory(prefix='bim2sim_')
        os.mkdir(os.path.join(cls.root.name, 'templates'))
        cls.ifc = ifc2python.load_ifc(IFC_PATH)
        pipefittings = Test_TemplateFinder.ifc.by_type("IfcPipeFitting")
        pipes = Test_TemplateFinder.ifc.by_type("IfcPipeSegment")

        cls.pipe1 = elements.Pipe(pipes[0])
        cls.pipe2 = elements.Pipe(pipes[1])
        cls.pipefitting1 = elements.PipeFitting(pipefittings[0])
        cls.pipefitting2 = elements.PipeFitting(pipefittings[1])


    @classmethod
    def tearDownClass(cls):
        cls.root.cleanup()

    def setUp(self):
        self.finder = TemplateFinder()
        self.backup = element.Element.finder
        element.Element.finder = self.finder

    def tearDown(self):
        del self.finder
        element.Element.finder = None

    def test_set_find(self):
        cls = self.__class__
        tool = cls.pipe1.source_tool

        self.finder.set(tool, elements.Pipe, 'length', 'Abmessungen', 'Länge')
        self.finder.set(tool, cls.pipe1, 'diameter', 'Abmessungen', 'Innendurchmesser')
        self.finder.set(tool, 'IfcPipeFitting', 'diameter', 'Abmessungen', 'Nenndurchmesser')

        l1 = self.finder.find(cls.pipe1, 'length')
        d1 = self.finder.find(cls.pipe1, 'diameter')
        l2 = self.finder.find(cls.pipe2, 'length')
        d2 = self.finder.find(cls.pipe2, 'diameter')
        d3 = self.finder.find(cls.pipefitting1, 'diameter')

        with self.assertRaises(AttributeError):
            self.finder.find(cls.pipefitting1, 'length')

    def test_save_load(self):
        cls = self.__class__
        tool = cls.pipe1.source_tool
        self.finder.set(tool, elements.Pipe, 'length', 'Abmessungen', 'Länge')
        self.finder.set(tool, elements.Pipe, 'diameter', 'Abmessungen', 'Innendurchmesser')
        self.finder.set(tool, 'IfcPipeFitting', 'diameter', 'Abmessungen', 'Nenndurchmesser')

        data = self.finder.templates.copy()

        path = os.path.join(cls.root.name, 'templates')
        self.finder.save(path)

        self.finder.templates.clear()

        self.finder.load(path)

        self.assertDictEqual(data, self.finder.templates)

if __name__ == '__main__':
    unittest.main()
