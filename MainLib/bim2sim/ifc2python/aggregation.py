﻿"""Module for aggregation and simplifying elements"""

import logging
import math
from collections import defaultdict

from bim2sim.ifc2python.element import BaseElement, BasePort


class AggregationPort(BasePort):
    """Port for Aggregation"""

    def __init__(self, original, *args, **kwargs):
        if 'guid' not in kwargs:
            kwargs['guid'] = self.get_id("AggPort")
        super().__init__(*args, **kwargs)
        self.original = original

    def calc_position(self):
        """Position of original port"""
        return self.original.position


class Aggregation(BaseElement):
    """Base aggregation of models"""

    def __init__(self, name, elements, *args, **kwargs):
        if 'guid' not in kwargs:
            #TODO: make guid reproducable unique for same aggregation elements
            # e.g. hash of all (ordered?) element guids?
            # Needed for save/load decisions on aggregations
            kwargs['guid'] = self.get_id("Agg")
        super().__init__(*args, **kwargs)
        self.name = name
        self.elements = elements
        for model in self.elements:
            model.aggregation = self

    def calc_position(self):
        """Position based on first and last element"""
        try:
            return (self.elements[0].position + self.elements[-1].position) / 2
        except:
            return None

    def __repr__(self):
        return "<%s '%s' (aggregation of %d elements)>" % (
            self.__class__.__name__, self.name, len(self.elements))


class PipeStrand(Aggregation):
    """Aggregates pipe strands"""
    aggregatable_elements = ['IfcPipeSegment', 'IfcPipeFitting']

    def __init__(self, name, elements, *args, **kwargs):
        super().__init__(name, elements, *args, **kwargs)
        edge_ports = self._get_start_and_end_ports()
        self.ports.append(AggregationPort(edge_ports[0], parent=self))
        self.ports.append(AggregationPort(edge_ports[1], parent=self))

        self._total_length = None
        self._avg_diameter = None

    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the pipestrand.

        Assumes all elements in are ordered as connected
        :return ports:
        """
        agg_ports = []
        # first port
        found_in = False
        found_out = False
        for port in self.elements[0].ports:
            if not port.connection:
                continue  # end node
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        # last port
        found_in = False
        found_out = False
        for port in self.elements[-1].ports:
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        return agg_ports

    def _calc_avg(self):
        """Calculates the total length and average diameter of all pipe-like
         elements."""
        self._total_length = 0
        self._avg_diameter = 0
        diameter_times_length = 0

        for pipe in self.elements:
            if hasattr(pipe, "diameter") and hasattr(pipe, "length"):
                length = pipe.length
                diameter = pipe.diameter
                if not (length and diameter):
                    self.logger.warning("Ignored '%s' in aggregation", pipe)
                    continue

                diameter_times_length += diameter*length
                self._total_length += length

            else:
                self.logger.warning("Ignored '%s' in aggregation", pipe)
        if self._total_length != 0:
            self._avg_diameter = diameter_times_length / self._total_length

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port:None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    @property
    def diameter(self):
        """Diameter of aggregated pipe"""
        if self._avg_diameter is None:
            self._calc_avg()
        return self._avg_diameter

    @property
    def length(self):
        """Length of aggregated pipe"""
        if self._total_length is None:
            self._calc_avg()
        return self._total_length


class UnderfloorHeating(Aggregation):
    """Aggregates UnderfloorHeating"""
    aggregatable_elements = ['IfcPipeSegment', 'IfcPipeFitting']

    def __init__(self, name, elements, *args, **kwargs):
        super().__init__(name, elements, *args, **kwargs)
        edge_ports = self._get_start_and_end_ports()
        self.ports.append(AggregationPort(edge_ports[0], parent=self))
        self.ports.append(AggregationPort(edge_ports[1], parent=self))

        self._total_length = None
        self._avg_diameter = None
        self._heating_area = None
        self._x_spacing = None
        self._y_spacing = None

    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the pipestrand.

        Assumes all elements in are ordered as connected
        :return ports:
        """
        agg_ports = []
        # first port
        found_in = False
        found_out = False
        for port in self.elements[0].ports:
            if not port.connection:
                continue  # end node
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        # last port
        found_in = False
        found_out = False
        for port in self.elements[-1].ports:
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        return agg_ports

    def _calc_avg(self):
        """Calculates the total length and average diameter of all pipe-like
         elements."""
        self._total_length = 0
        self._avg_diameter = 0
        diameter_times_length = 0

        for pipe in self.elements:
            if hasattr(pipe, "diameter") and hasattr(pipe, "length"):
                length = pipe.length
                diameter = pipe.diameter
                if not (length and diameter):
                    self.logger.warning("Ignored '%s' in aggregation", pipe)
                    continue

                diameter_times_length += diameter*length
                self._total_length += length

            else:
                self.logger.warning("Ignored '%s' in aggregation", pipe)
        if self._total_length != 0:
            self._avg_diameter = diameter_times_length / self._total_length

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port:None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    def _calc_properties(self):
        self._heating_area = 0
        self._x_spacing = 0
        self._y_spacing = 0
        z_coordinates = defaultdict(list)
        for element in self.elements:
            z_coordinates[element.position[2]].append(element)
        z_coordinate = []
        for coordinate in z_coordinates:
            n_pipe = 0
            for element in z_coordinates[coordinate]:
                if "PipeFitting" in str(element):
                    n_pipe += 1
            if n_pipe == 0 and (len(z_coordinates[coordinate]) > len(z_coordinate)):
                z_coordinate = z_coordinates[coordinate]
        z_coordinate = z_coordinate[0].position[2]

        min_x = float("inf")
        max_x = -float("inf")
        min_y = float("inf")
        max_y = -float("inf")
        x_orientation = []
        y_orientation = []
        for element in self.elements:
            if z_coordinate - 1 < element.position[2] < z_coordinate + 1:
                if element.position[0] < min_x:
                    min_x = element.position[0]
                if element.position[0] > max_x:
                    max_x = element.position[0]
                if element.position[1] < min_y:
                    min_y = element.position[1]
                if element.position[1] > max_y:
                    max_y = element.position[1]
                if abs(element.ports[0].position[0] - element.ports[1].position[0]) < 1:
                    y_orientation.append(element)
                if abs(element.ports[0].position[1] - element.ports[1].position[1]) < 1:
                    x_orientation.append(element)
        self._heating_area = (max_x - min_x) * (max_y - min_y)
        self._x_spacing = (max_x - min_x) / (len(y_orientation) - 1)
        self._y_spacing = (max_y - min_y) / (len(x_orientation) - 1)

    @property
    def diameter(self):
        """Diameter of aggregated pipe"""
        if self._avg_diameter is None:
            self._calc_avg()
        return self._avg_diameter

    @property
    def length(self):
        """Length of aggregated pipe"""
        if self._total_length is None:
            self._calc_avg()
        return self._total_length

    @property
    def heating_area(self):
        """Heating area"""
        if self._heating_area is None:
            self._calc_properties()
        return self._heating_area

    @property
    def x_spacing(self):
        """Spacing in x"""
        if self._x_spacing is None:
            self._calc_avg()
        return self._x_spacing

    @property
    def y_spacing(self):
        """Spacing in y """
        if self._y_spacing is None:
            self._calc_avg()
        return self._y_spacing

class ParallelPump(Aggregation):
    """Aggregates pumps in parallel"""
    aggregatable_elements = ['IfcPump']

    def __init__(self, name, elements, *args, **kwargs):
        super().__init__(name, elements, *args, **kwargs)
        edge_ports = self._get_start_and_end_ports()
        self.ports.append(AggregationPort(edge_ports[0], parent=self))
        self.ports.append(AggregationPort(edge_ports[1], parent=self))

        for ele in self.elements:
            ele.request('rated_power')
            ele.request('rated_height')
            ele.request('rated_volume_flow')
            ele.request('diameter')

        self._total_rated_power = None
        self._avg_rated_height = None
        self._total_rated_volume_flow = None
        self._total_diameter = None

    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the parallelpumps

        Assumes all elements in are ordered as connected
        :return ports:
        """
        agg_ports = []
        # first port
        found_in = False
        found_out = False
        for port in self.elements[0].ports:
            if not port.connection:
                continue  # end node
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        # last port
        found_in = False
        found_out = False
        for port in self.elements[-1].ports:
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        return agg_ports

    def _calc_avg(self):
        """Calculates the parameters of all pump-like elements."""
        self._total_rated_power = 0
        self._avg_rated_height = 0
        self._total_rated_volume_flow = 0
        self._total_diameter = 0

        for pump in self.elements:
            rated_power = getattr(pump, "rated_power")
            rated_height = getattr(pump, "rated_height")
            rated_volume_flow = getattr(pump, "rated_volume_flow")
            diameter = getattr(pump, "diameter")
            if not (rated_power and rated_height and rated_volume_flow and diameter):
                self.logger.warning("Ignored '%s' in aggregation", pump)
                continue

            self._total_rated_volume_flow += rated_volume_flow
            if self._avg_rated_height != 0:
                if rated_height < self._avg_rated_height:
                    self._avg_rated_height = rated_height
            else:
                self._avg_rated_height = rated_height

            self._total_diameter = self._total_diameter + diameter**2

        self._total_diameter = math.sqrt(self._total_diameter)
        g = 9.81
        rho = 1000
        self._total_rated_power = self.rated_volume_flow*self.rated_height*g*rho

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port:None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    @property
    def rated_power(self):
        """Length of aggregated pipe"""
        if self._total_rated_power is None:
            self._calc_avg()
        return self._total_rated_power

    @property
    def rated_height(self):
        """Length of aggregated pipe"""
        if self._avg_rated_height is None:
            self._calc_avg()
        return self._avg_rated_height

    @property
    def rated_volume_flow(self):
        """Length of aggregated pipe"""
        if self._total_rated_volume_flow is None:
            self._calc_avg()
        return self._total_rated_volume_flow

    @property
    def diameter(self):
        """Diameter of aggregated pipe"""
        if self._total_diameter is None:
            self._calc_avg()
        return self._total_diameter


# class ParallelStrand(Aggregation):
#     """Aggregates pipe strands in parallel"""
#
#     def __init__(self, name, elements, parameter, nodes, index,  *args, **kwargs):
#         self.parameter = parameter
#         self.nodes = nodes
#         self.index = index
#         super().__init__(name, elements, *args, **kwargs)
#         edge_ports = self._get_start_and_end_ports()
#         self.ports.append(AggregationPort(edge_ports[0], parent=self))
#         self.ports.append(AggregationPort(edge_ports[1], parent=self))
#         self._total_diameter = None
#         self._avg_length = None
#
#     def _get_start_and_end_ports(self):
#         """
#         Finds and sets the first and last port of the pipestrand.
#
#         Assumes all elements in are ordered as connected
#         :return ports:
#         """
#         agg_ports = []
#
#             # first port
#         if self.parameter == "first":
#             for port in self.elements[0].ports:
#                 if port not in self.nodes:
#                     agg_ports.append(port)
#             # for element in
#             for element in self.elements[self.index-1:self.index+1]:
#                 for port in element.ports:
#
#
#                     # agg_ports.append(port)
#                 # last port
#
#         return agg_ports
#
#     def _calc_avg(self):
#         """Calculates the total length and average diameter of all pipe-like
#          elements."""
#         self._total_diameter = 0
#         self._avg_length = 0
#         diameter_times_length = 0
#
#         for pipe in self.elements:
#             if hasattr(pipe, "diameter") and hasattr(pipe, "length"):
#                 length = pipe.length
#                 diameter = pipe.diameter
#                 if not (length and diameter):
#                     self.logger.warning("Ignored '%s' in aggregation", pipe)
#                     continue
#
#                 diameter_times_length += diameter*length
#                 self._total_diameter = self._total_diameter + diameter ** 2
#
#             else:
#                 self.logger.warning("Ignored '%s' in aggregation", pipe)
#         self._total_diameter = math.sqrt(self._total_diameter)
#         self._avg_length = diameter_times_length / self._total_diameter
#
#     def get_replacement_mapping(self):
#         """Returns dict with original ports as values and their aggregated replacement as keys."""
#         mapping = {port:None for element in self.elements
#                    for port in element.ports}
#         for port in self.ports:
#             mapping[port.original] = port
#         return mapping
#
#     @property
#     def diameter(self):
#         """Diameter of aggregated pipe"""
#         if self._total_diameter is None:
#             self._calc_avg()
#         return self._total_diameter
#
#     @property
#     def length(self):
#         """Length of aggregated pipe"""
#         if self._avg_length is None:
#             self._calc_avg()
#         return self._avg_length
