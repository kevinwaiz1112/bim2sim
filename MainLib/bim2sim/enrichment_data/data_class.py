import os
import sys
import json
from bim2sim.project import PROJECT as project

v = sys.version_info
if v >= (2, 7):
    try:
        FileNotFoundError
    except:
        FileNotFoundError = IOError

# elements_data = inspect.getmembers(elements)


class DataClass(object):
    """
    Class for Enrichment method, that loads the enrichment data from a
    file (source_path), it can support various enrichment parameters
    """

    def __init__(self, used_param='1'):

        self.used_parameters = used_param
        self.element_bind = None
        if self.used_parameters == '1':
            self.path_te = os.path.join(project.source, 'assets', 'enrichment',
                                        'TypeBuildingElements.json')
            self.load_te_binding()
        elif self.used_parameters is None:
            self.element_bind = None

    def load_te_binding(self):
        """
        binding from the enrichment data, it can support various formats
        te: Type element
        """

        if self.path_te.endswith("json"):
                try:
                    with open(self.path_te, 'r+') as f:
                        self.element_bind = json.load(f)
                except json.decoder.JSONDecodeError:
                    print("Your TypeElements file seems to be broken.")
        else:
            print("Your TypeElements file has the wrong format.")

