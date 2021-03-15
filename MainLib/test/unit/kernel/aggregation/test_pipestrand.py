import unittest

from bim2sim.kernel import aggregation
from bim2sim.kernel.element import Port
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.kernel.units import ureg

from test.unit.kernel.helper import SetupHelper


class StrandHelper(SetupHelper):

    def get_setup_strand1(self):
        """simple strait strand"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            strand = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(10)]

        # connect
        self.connect_strait(strand)

        # full system
        gen_circuit = [
            *strand
        ]

        flags['connect'] = [strand[0], strand[-1]]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_strand2(self):
        """simple strait strand with various diameters"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            strand1 = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(2)]
            strand2 = [self.element_generator(
                elements.Pipe, length=200, diameter=50) for i in range(2)]
            strand3 = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(2)]
            strand4 = [self.element_generator(
                elements.Pipe, length=50, diameter=15) for i in range(2)]

        strand = [*strand1, *strand2, *strand3, *strand4]
        # connect
        self.connect_strait(strand)

        # full system
        gen_circuit = [
            *strand
        ]

        flags['connect'] = [strand[0], strand[-1]]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_strait_with_valve(self):
        """simple strait strand with valve"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            strand1 = [self.element_generator(
                elements.Pipe, flags=['pipes'], length=100, diameter=30) for i in range(3)]
            strand2 = [self.element_generator(
                elements.Pipe, flags=['pipes'], length=100, diameter=30) for i in range(3)]
            valve = self.element_generator(elements.Valve, flags=['valve'], diameter=30)

        strand = [*strand1, valve, *strand2]
        # connect
        self.connect_strait(strand)

        # full system
        gen_circuit = [
            *strand
        ]

        flags['connect'] = [strand[0], strand[-1]]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_straits_with_distributor(self):
        """distributor wit two connected straits"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            strand1 = [self.element_generator(
                elements.Pipe, length=100, diameter=30) for i in range(2)]
            strand2 = [self.element_generator(
                elements.Pipe, length=200, diameter=50) for i in range(2)]
            distributor = self.element_generator(elements.Distributor, flags=['distributor'])

        # connect
        self.connect_strait([*strand1, distributor, *strand2])

        # full system
        gen_circuit = [
            *strand1,
            distributor,
            *strand2
        ]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_cross(self):
        """two crossing strands"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            strand1 = [self.element_generator(
                elements.Pipe, flags=['strand1'], length=100, diameter=30) for i in range(4)]
            strand2 = [self.element_generator(
                elements.Pipe, flags=['strand2'], length=100, diameter=30) for i in range(4)]
            strand3 = [self.element_generator(
                elements.Pipe, flags=['strand3'], length=100, diameter=30) for i in range(4)]
            strand4 = [self.element_generator(
                elements.Pipe, flags=['strand4'], length=100, diameter=30) for i in range(4)]
            cross = self.element_generator(elements.PipeFitting, n_ports=4, flags='cross')

        # connect
        self.connect_strait(strand1)
        self.connect_strait(strand2)
        self.connect_strait(strand3)
        self.connect_strait(strand4)

        cross.ports[0].connect(strand1[0].ports[0])
        cross.ports[1].connect(strand2[0].ports[0])
        cross.ports[2].connect(strand3[0].ports[0])
        cross.ports[3].connect(strand4[0].ports[0])

        # full system
        gen_circuit = [
            *strand1,
            *strand2,
            *strand3,
            *strand4,
            cross
        ]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_system(self):
        """System (Kessel - Pumpe - Heizung - Absperrventil - T-Stück - Druckausgleichgefäß)"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boiler = self.element_generator(elements.Boiler, rated_power=200)
            strand1 = [self.element_generator(elements.Pipe, flags=['strand1'], length=100, diameter=40) for i in range(3)]
            h_pump = self.element_generator(elements.Pump, rated_power=2.2, rated_height=12, rated_volume_flow=8)
            strand2 = [self.element_generator(elements.Pipe, flags=['strand2'], length=100, diameter=40) for i in range(5)]
            spaceheater = self.element_generator(elements.SpaceHeater, flags=['spaceheater'])  # , volume=80
            strand3a = [self.element_generator(elements.Pipe, flags=['strand3'], length=100, diameter=40) for i in range(4)]
            valve = self.element_generator(elements.Valve, flags=['valve'])
            strand3b = [self.element_generator(elements.Pipe, flags=['strand3'], length=100, diameter=40) for i in range(4)]
            fitting = self.element_generator(elements.PipeFitting, n_ports=3, diameter=40, length=60)
            strand4 = [self.element_generator(elements.Pipe, flags=['strand4'], length=100, diameter=40) for i in range(4)]
            strand5 = [
                self.element_generator(elements.Pipe, flags=['strand5'], length=100, diameter=40) for i in range(4)]
            tank = self.element_generator(elements.Storage, n_ports=1)

        # connect
        circuit = [
            boiler, *strand1, h_pump, *strand2, spaceheater,
            *strand3a, valve, *strand3b, fitting, *strand4, boiler
        ]
        self.connect_strait(circuit)
        self.connect_strait([*strand5, tank])
        fitting.ports[2].connect(strand5[0].ports[0])

        # full system
        gen_circuit = [
            *circuit, *strand5, tank
        ]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags

    def get_setup_loop(self):
        """Circular strand with diagonal connected strand"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            strand1 = [self.element_generator(
                elements.Pipe, flags=['strand1'], length=100, diameter=30) for i in range(6)]
            strand2 = [self.element_generator(
                elements.Pipe, flags=['strand2'], length=100, diameter=30) for i in range(6)]
            strand3 = [self.element_generator(
                elements.Pipe, flags=['strand3'], length=100, diameter=30) for i in range(4)]
            cross1 = self.element_generator(elements.PipeFitting, n_ports=3, flags='cross')
            cross2 = self.element_generator(elements.PipeFitting, n_ports=3, flags='cross')

        # connect
        self.connect_strait([cross1, *strand1, cross2])
        self.connect_strait([cross2, *strand2, cross1])
        self.connect_strait(strand3)
        cross1.ports[2].connect(strand3[0].ports[0])
        cross2.ports[2].connect(strand3[-1].ports[1])

        # full system
        gen_circuit = [
            *strand1,
            *strand2,
            *strand3,
            cross1,
            cross2
        ]

        graph = HvacGraph(gen_circuit)
        # graph.plot(r'c:\temp')
        return graph, flags


class TestPipeStrand(unittest.TestCase):

    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = StrandHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_strait_strand(self):
        """Test calculation of aggregated length"""
        graph, flags = self.helper.get_setup_strand1()
        ele = graph.elements

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(1, len(matches))
        agg = aggregation.PipeStrand("Test strait strand", matches[0], **meta[0])

        exp_length = sum([e.length for e in ele])
        self.assertAlmostEqual(exp_length, agg.length)

        self.assertAlmostEqual(30 * ureg.millimeter, agg.diameter)

    def test_strait_strand_variable(self):
        """Test calculation of aggregated length and diameter"""
        graph, flags = self.helper.get_setup_strand2()
        ele = graph.elements

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(1, len(matches))
        agg = aggregation.PipeStrand("Test strait strand variable", matches[0], **meta[0])

        exp_length = sum([e.length for e in ele])
        self.assertAlmostEqual(exp_length, agg.length)

        exp_diameter = sum([e.length * e.diameter for e in ele]) / exp_length
        self.assertAlmostEqual(exp_diameter, agg.diameter)

    def test_distributor_with_strands(self):
        """Test calculation of aggregated length and diameter"""
        graph, flags = self.helper.get_setup_straits_with_distributor()

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(2, len(matches))

        with self.assertRaises(AssertionError, msg="Pipestrand aggregation over a distributor should fail"):
            # pass full graph
            agg = aggregation.PipeStrand("Test distributor with strands", graph, **{})

    @unittest.skip("PipeStrand aggregation with inert elements not implemented")
    def test_strait_strand_valve(self):
        """Test calculation of aggregated length and diameter"""
        graph, flags = self.helper.get_setup_strait_with_valve()
        ele = graph.elements

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(1, len(matches))
        agg = aggregation.PipeStrand("Test strait strand with valve", matches[0], **meta[0])

        exp_length = sum([e.length for e in flags['pipes']])
        self.assertAlmostEqual(exp_length, agg.length)

        self.assertAlmostEqual(30 * ureg.millimeter, agg.diameter)

    def test_filter_strand(self):
        """Test filter for strait strand"""
        graph, flags = self.helper.get_setup_strand1()
        ele = graph.elements

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(1, len(matches))

        self.assertSetEqual(set(ele), set(matches[0].nodes))

    def test_filter_cross(self):
        """Test filter for crossing strands"""
        graph, flags = self.helper.get_setup_cross()
        ele = flags['strand1'] + flags['strand2'] + flags['strand3'] + flags['strand4']

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(4, len(matches))

        self.assertSetEqual(set(ele), set(sum([list(m.nodes) for m in matches], [])))

    def test_filter_system(self):
        """Test filter for crossing strands"""
        graph, flags = self.helper.get_setup_system()
        ele = flags['strand1'] + flags['strand2'] + flags['strand3'] + flags['strand4'] + flags['strand5'] \
              + flags['valve']

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(5, len(matches))

        self.assertSetEqual(set(ele), set(sum([list(m.nodes) for m in matches], [])))

    def test_filter_circular(self):
        """Test filter for crossing strands"""
        graph, flags = self.helper.get_setup_loop()
        ele = flags['strand1'] + flags['strand2'] + flags['strand3']

        matches, meta = aggregation.PipeStrand.find_matches(graph)
        self.assertEqual(len(matches), 3)

        self.assertSetEqual(set(ele), set(sum([list(m.nodes) for m in matches], [])))

    def test_pipestrand1(self):
        """Test calculation of aggregated length and diameter"""
        graph, flags = self.helper.get_setup_simple_boiler()
        elements = flags['strand1']
        match_graph = graph.subgraph((port for ele in elements for port in ele.ports))

        matches, meta = aggregation.PipeStrand.find_matches(match_graph)
        self.assertEqual(1, len(matches))
        agg = aggregation.PipeStrand("Test 1", matches[0], **meta[0])

        exp_length = sum([e.length for e in elements])
        self.assertAlmostEqual(agg.length, exp_length)

        self.assertAlmostEqual(40 * ureg.millimeter, agg.diameter)

    def test_pipestrand2(self):
        """Test calculation of aggregated length and diameter"""

        graph, flags = self.helper.get_setup_simple_boiler()
        elements = flags['strand2']
        match_graph = graph.subgraph((port for ele in elements for port in ele.ports))

        matches, meta = aggregation.PipeStrand.find_matches(match_graph)
        self.assertEqual(1, len(matches))
        agg = aggregation.PipeStrand("Test 2", matches[0], **meta[0])

        exp_length = sum([e.length for e in elements])
        self.assertAlmostEqual(exp_length, agg.length)

        self.assertAlmostEqual(15 * ureg.millimeter, agg.diameter)

    def test_basics(self):
        graph, flags = self.helper.get_setup_simple_boiler()
        elements = flags['strand1']
        match = graph.element_graph.subgraph(elements)

        agg = aggregation.PipeStrand("Test", match)

        self.assertTrue(self.helper.elements_in_agg(agg))

    def test_detection(self):
        graph, flags = self.helper.get_setup_simple_boiler()

        matches, meta = aggregation.PipeStrand.find_matches(graph)

        self.assertEqual(
            len(matches), 5,
            "There are 5 cases for PipeStrand but 'find_matches' returned %d" % len(matches)
        )


if __name__ == '__main__':
    unittest.main()
