﻿"""Module containing filters to identify IFC elements of interest"""
from ifc2python import ifc2python

class Filter():
    """Base filter"""

    def __init__(self):
        pass

    def matches(self, ifcelement):
        """Check if element matches filter conditions"""
        raise NotImplementedError("Must overwride method 'matches'")

    def run(self):
        """Apply the Filter on IFC File"""
        raise NotImplementedError("Must overwride method 'matches'")

    def __repr__(self):
        return "<%s>"%(self.__class__.__name__)

class TypeFilter(Filter):
    """Filter for subsets of IFC types"""

    def __init__(self, ifc_types: list):
        super().__init__()
        self.ifc_types = ifc_types

    def matches(self, ifcelement):
        __doc__ = super().matches.__doc__
        return ifcelement.type in self.ifc_types #TODO: string based

    def run(self, ifc):
        __doc__ = super().run.__doc__
        elements = {}
        for ifc_type in self.ifc_types:
            e = ifc.by_type(ifc_type)
            if e:
                elements[ifc_type] = ifc.by_type(ifc_type)
        return elements

class TextFilter(Filter):
    """Filter for unknown properties by text fracments"""

    def __init__(self, ifc_types: list, text_fracments: dict, posible_locations: list):
        super().__init__()
        self.ifc_types = ifc_types
        self.text_fracments = text_fracments
        self.posible_locations = posible_locations

    def matches(self, ifcelement):
        __doc__ = super().matches.__doc__
        if ifcelement:
            #Pseudocode: check if element contains Text_fracments[ifc_property]
            element = None
            return element
        else:
            #Pseudocode: filter self.components for text in Text_Fracments[ifc_property]
            elements = None
            return elements

    def run(self, ifc):
        __doc__ = super().run.__doc__
        ifc_elements = []
        elements = {}
        element = None
        for ifc_type in self.ifc_types:
            ifc_elements.extend(ifc.by_type(ifc_type))
        for ifc_element in ifc_elements:
            for ifc_type, text_fracments in self.text_fracments.items():
                for text_fracment in text_fracments:
                    if text_fracment in ifc_element.Name:
                        element = ifc_element
                        break
                    for posible_location in self.posible_locations:
                        for text_fracment in text_fracments:
                            try:
                                #Skip Error if Property_Set dosen't exists
                                property = ifc2python.get_Property_Sets(posible_location, ifc_element) #ToDo: Must be a Str
                            except:
                                break
                            if text_fracment in property:
                                element = ifc_element
                                break
                if element:
                    if elements.get(ifc_type):
                        elements[ifc_type].append(element)
                    else:
                        elements[ifc_type] = [element]
                    element = None  #ToDo: Check if Element has >1 Types!!!
        return elements




class GeometricFilter(Filter):
    """Filter based on geometric position"""

    def __init__(self, 
            x_min: float = None, x_max: float = None, 
            y_min: float = None, y_max: float = None, 
            z_min: float = None, z_max: float = None):
        """None = unlimited"""
        super().__init__()

        assert any([not lim is None for lim in [x_min, x_max, y_min, y_max, z_min, z_max]]), \
            "Filter without limits has no effeckt."
        assert (x_min is None or x_max is None) or x_min < x_max, \
            "Invalid arguments for x_min and x_max"
        assert (y_min is None or y_max is None) or y_min < y_max, \
            "Invalid arguments for y_min and y_max"
        assert (z_min is None or z_max is None) or z_min < z_max, \
            "Invalid arguments for z_min and z_max"

        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.z_min = z_min
        self.z_max = z_max

    def matches(self, ifcelement):
        __doc__ = super().matches.__doc__
        raise NotImplementedError("ToDo") # TODO

class ZoneFilter(GeometricFilter):
    """Filter elements within given zone"""

    def __init__(self, zone):
        raise NotImplementedError("ToDo") # TODO
        #super().__init__(x_min, x_max, y_min, y_max, z_min, z_max)
