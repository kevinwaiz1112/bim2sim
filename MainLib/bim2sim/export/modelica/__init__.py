﻿"""Package for Modelica export"""

import os
import logging

import codecs
from mako.template import Template

from bim2sim.ifc2python import element as elem
from bim2sim.decision import RealDecision

TEMPLATEPATH = os.path.join(os.path.dirname(__file__), 'tmplModel.txt')
# prevent mako newline bug by reading file seperatly
with open(TEMPLATEPATH) as f:
    templateStr = f.read()
templ = Template(templateStr)


class ModelError(Exception):
    pass
class FactoryError(Exception):
    pass

class Model():
    """Modelica model"""

    def __init__(self, name, comment, instances: list, connections: dict):

        self.logger = logging.getLogger(__name__)

        self.name = name
        self.comment = comment
        self.instances = instances
        self.connections = connections

    def code(self):
        """returns Modelica code"""
        return templ.render(model=self)

    def save(self, path: str):
        """Save model as Modelica file"""
        _path = os.path.normpath(path)
        if os.path.isdir(_path):
            _path = os.path.join(_path, self.name)

        if not path.endswith(".mo"):
            _path += ".mo"

        data = self.code()

        self.logger.info("Saving '%s' to '%s'", self.name, _path)
        with codecs.open(_path, "w", "utf-8") as file:
            file.write(data)


class Instance():
    """Modelica model instance"""

    library = None
    version = None
    path = None
    represents = None
    lookup = {}
    dummy = None
    _initialized = False

    def __init__(self, element):

        self.element = element

        self.name = element.__class__.__name__.lower()
        self.guid = getattr(element, "guid", "").replace("$", "_")
        if self.guid:
            self.name = self.name + "_" + self.guid
        self.params = {}
        self.get_params()
        self.comment = self.get_comment()
        self.connections = []

    @staticmethod
    def _lookup_add(key, value):
        """Adds key and value to Instance.lookup. Returns conflict"""
        if key in Instance.lookup:
            logger.error("Conflicting representations (%s) in '%s' and '%s'", \
                key, value.__name__, Instance.lookup[key].__name__)
            return True
        else:
            Instance.lookup[key] = value
            return False

    @staticmethod
    def init_factory(libraries):
        """initialize lookup for factory"""
        logger = logging.getLogger(__name__)
        conflict = False

        Instance.dummy = Dummy

        for library in libraries:
            if not Instance in library.__bases__:
                logger.warning("Got Library not directly inheriting from Instance.")
            if library.library:
                logger.info("Got library '%s'", library.library)
            else:
                logger.error("Attribute library not set for '%s'", library.__name__)
                raise AssertionError("Library not defined")
            for cls in library.__subclasses__():
                if cls.represents is None:
                    logger.warning("'%s' represents no model and can't be used", cls.__name__)
                    continue

                if isinstance(cls.represents, (list, set)):
                    for rep in cls.represents:
                        confl = Instance._lookup_add(rep, cls)
                        if confl: conflict = True
                else:
                    confl = Instance._lookup_add(cls.represents, cls)
                    if confl: conflict = True

        if conflict:
            raise AssertionError("Conflict(s) in Models. (See log for details).")

        Instance._initialized = True

        models = set(Instance.lookup.values())
        models_txt = "\n".join(sorted([" - %s"%(inst.path) for inst in models]))
        logger.debug("Modelica libraries intitialized with %d models:\n%s", len(models), models_txt)

    @staticmethod
    def factory(element):
        """Create model depending on ifc_element"""

        if not Instance._initialized:
            raise FactoryError("Factory not initialized.")

        cls = Instance.lookup.get(element.__class__, Instance.dummy)
        return cls(element)

    def manage_param(self, name:str, value, check):
        """Managing for parameters
        
        adds parameter with name to self.params if check is successfull
        else the paramter gets managed by the decision system an is later added to self.params"""

        if check(value):
            self.params[name] = value
        else:
            RealDecision(
                question="Please enter parameter for %s"%(self.name + "." + name), 
                validate_func=self.check_power,
                output=self.params, 
                output_key=name, 
                global_key=self.name + "." + name,
                collect=True,
                allow_load=True,
                allow_save=True,
                allow_skip=True,
            )

    def get_params(self):
        return {}

    def get_comment(self):
        return self.element.name
        #return "Autogenerated by BIM2SIM"

    @property
    def path(self):
        return self.__class__.path

    def get_port_name(self, port):
        return "port_unknown"

    def get_full_port_name(self, port):
        return "%s.%s"%(self.name, self.get_port_name(port))

    @staticmethod
    def check_numeric(min_value=None, max_value=None):
        """Generic check function generator
        
        returns check function"""

        def inner_check(value):
            if not isinstance(value, (int, float)):
                return False
            if min_value is None and max_value is None:
                return True
            if not min_value is None and max_value is None:
                return min_value <= value
            if not max_value is None:
                return value <= max_value
            return min_value <= value <= max_value

        return inner_check

    def __repr__(self):
        return "<%s %s>"%(self.path, self.name)


class Dummy(Instance):
    path = "Path.to.Dummy"
    represents = elem.Dummy

if __name__ == "__main__":

    class Radiator(Instance):
        path = "Heating.Consumers.Radiators.Radiator"

    par = {
        "redeclare package Medium" : "Modelica.Media.Water.ConstantPropertyLiquidWater",
        "Q_flow_nominal" : 4e3,
        "n" : 1.3,
        "Type" : "HKESim.Heating.Consumers.Radiators.BaseClasses.ThermostaticRadiatorValves.Types.radiatorCalculationTypes.proportional",
        "k" : 1.5
    }

    conns = {"radiator1.port_a": "radiator2.port_b"}

    inst1 = Instance("radiator1", {})
    inst2 = Instance("radiator2", par)

    model = Model("System", "Test", [inst1, inst2], conns)

    print(model.code())
    #model.save(r"C:\Entwicklung\temp")
