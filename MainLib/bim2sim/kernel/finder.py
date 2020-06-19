﻿"""Finders are used to get properties from ifc which do not use the default PropertySets"""

import os
import json

from bim2sim.kernel import ifc2python


DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets\\finder')


class Finder:

    def find(self, element, property_name):
        raise NotImplementedError()


class TemplateFinder(Finder):
    """TemplateFinder works like a multi key diktonary.

    Use it for tool dependent property usage. 
    E.g. Revit stores length of IfcPipeSegment in PropertySet 'Abmessungen' with name 'Länge'
    """
    prefix = "template_"

    def __init__(self):
        super().__init__()
        #{tool: {Element class name: {parameter: (Pset name, property name)}}}
        self.templates = {}

    def load(self, path):
        """loads templates from given path. Each *.json file is interpretet as tool with name *
        also searches default templates"""

        # search in project folder
        for filename in os.listdir(path):
            if filename.lower().startswith(TemplateFinder.prefix) and filename.lower().endswith(".json"):
                tool = filename[len(TemplateFinder.prefix):-5]
                try:
                    with open(os.path.join(path, filename)) as file:
                        self.templates[tool] = json.load(file)
                except (IOError, json.JSONDecodeError) as ex:
                    continue

        # search for default finder templates
        for filename in os.listdir(DEFAULT_PATH):
            if filename.lower().startswith(TemplateFinder.prefix) and filename.lower().endswith(".json"):
                tool = filename[len(TemplateFinder.prefix):-5]
                if tool in self.templates:
                    # not overwrite project templates
                    continue
                try:
                    with open(os.path.join(path, filename)) as file:
                        self.templates[tool] = json.load(file)
                except (IOError, json.JSONDecodeError) as ex:
                    continue

    def save(self, path):
        """Save templates to path. One file for each tool in templates"""

        for tool, element_dict in self.templates.items():
            full_path = os.path.join(path, TemplateFinder.prefix + tool + '.json')
            with open(full_path, 'w') as file:
                json.dump(element_dict, file, indent=2)

    def set(self, tool, element, parameter, property_set_name, property_name):
        """Internally saves property_set_name ans property_name as lookup source 
        for tool, element and parameter"""

        element_dict = self.templates.get(tool)
        if not element_dict:
            element_dict = {}
            self.templates[tool] = element_dict

        if isinstance(element, str):
            element_name = element #string
        elif isinstance(element.__class__, type):
            element_name = element.ifc_type #class
        else:
            element_name = element.__class__.ifc_type #instance
        parameter_dict = element_dict.get(element_name)
        if not parameter_dict:
            parameter_dict = {}
            element_dict[element_name] = parameter_dict

        value = [property_set_name, property_name]
        parameter_dict[parameter] = value

    def find(self, element, property_name):
        """Tries to find the required property
        
        :return: value of property or None if propertyset or property is not available
        :raises: AttributeError if TemplateFinder does not know about given input"""

        key1 = element.source_tool
        key2 = element.ifc_type
        # problem with ifcwall list
        if isinstance(key2, list):
            key2 = key2[0]
        key3 = property_name
        try:
            res = self.templates[key1][key2][key3]
        except KeyError:
            raise AttributeError("%s does not know where to look for %s"%(
                self.__class__.__name__, (key1, key2, key3)))

        try:
            pset = ifc2python.get_Property_Set(res[0], element.ifc)
        except AttributeError:
            raise AttributeError("Can't find property as defined by template.")
        return pset.get(res[1])

