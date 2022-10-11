from typing import Union

from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import get_usage_dict, get_pattern_usage
from bim2sim.decision import ListDecision, DecisionBunch, BoolDecision
from bim2sim.workflow import Workflow
from bim2sim.kernel.elements.bps import ThermalZone


class EnrichUseConditions(ITask):
    """Enriches Use Conditions of thermal zones
    based on decisions and translation of zone names"""

    reads = ('tz_instances',)
    touches = ('enriched_tz',)

    def __init__(self):
        super().__init__()
        self.enriched_tz = []
        self.use_conditions = {}

    def run(self, workflow: Workflow, tz_instances: dict):
        self.logger.info("enriches thermal zones usage")
        self.use_conditions = get_usage_dict(self.prj_name)

        # case no thermal zones found
        if len(tz_instances) == 0:
            self.logger.warning("Found no spaces to enrich")
        else:
            yield from self.enrich_usages(tz_instances)
            self.logger.info("obtained %d thermal zones", len(self.enriched_tz))

        return self.enriched_tz,

    def enrich_usages(self, thermal_zones: dict):
        """Sets the usage of the given thermal_zones and enriches them.

        Looks for fitting usages in assets/enrichment/usage based on the given
        usage of a zone in the IFC. The way the usage is obtained is described
        in the ThermalZone classes attribute "usage".
        The following data is taken into account:
            commonUsages.json: typical translations for the existing usage data
            customUsages<prj_name>.json: project specific translations that can
                be stored for easier simulation.

        Args:
            thermal_zones: dict with tz instances guid as key and the instance
            itself as value
        """
        selected_usage = {}
        final_usages = {}
        pattern_usage = get_pattern_usage(self.prj_name)
        for tz in list(thermal_zones.values()):
            if tz.usage in selected_usage:
                tz.usage = selected_usage[tz.usage]
            else:
                orig_usage = str(tz.usage)
                if orig_usage not in pattern_usage:
                    matches = []
                    list_org = tz.usage.replace(' (', ' ').replace(')', ' '). \
                        replace(' -', ' ').replace(', ', ' ').split()
                    for usage in pattern_usage.keys():
                        # check custom first
                        if "custom" in pattern_usage[usage]:
                            for cus_usage in pattern_usage[usage]["custom"]:
                                if cus_usage == tz.usage:
                                    if usage not in matches:
                                        matches.append(usage)
                        # if not found in custom, continue with common
                        if len(matches) == 0:
                            for i in pattern_usage[usage]["common"]:
                                for i_name in list_org:
                                    if i.match(i_name):
                                        if usage not in matches:
                                            matches.append(usage)
                    # if just a match given
                    if len(matches) == 1:
                        # case its an office
                        if 'office_function' == matches[0]:
                            office_use = self.office_usage(tz)
                            if isinstance(office_use, list):
                                final_usages[tz] = self.list_decision_usage(
                                    tz, office_use)
                            else:
                                final_usages[tz] = office_use
                        # other zone usage
                        else:
                            final_usages[tz] = matches[0]
                    # if no matches given forward all (for decision)
                    elif len(matches) == 0:
                        matches = list(pattern_usage.keys())
                    if len(matches) > 1:
                        final_usages[tz] = self.list_decision_usage(
                            tz, matches)
                    selected_usage[orig_usage] = tz.usage
        # answers decisions
        usage_dec_bunch = DecisionBunch()
        for tz, use_or_dec in final_usages.items():
            if isinstance(use_or_dec, ListDecision):
                usage_dec_bunch.append(use_or_dec)
        yield usage_dec_bunch
        answers = usage_dec_bunch.to_answer_dict()
        # update usages
        for tz, dec_answer in answers.items():
            final_usages[tz] = dec_answer
        # set usages
        for tz, usage in final_usages.items():
            tz.usage = usage
            self.load_usage(tz)
            self.enriched_tz.append(tz)

    # def one_zone_usage(self, thermal_zones: dict):
    #     """defines an usage to all the building - since its a singular zone"""
    #     usage_decision = ListDecision("Which usage does the one_zone_building"
    #                                   " %s have?",
    #                                   choices=list(UseConditions.keys()),
    #                                   global_key="one_zone_usage",
    #                                   allow_skip=False,
    #                                   allow_load=True,
    #                                   allow_save=True,
    #                                   quick_decide=not True)
    #     usage_decision.decide()
    #     for tz in list(thermal_zones.values()):
    #         tz.usage = usage_decision.value
    #         self.enriched_tz.append(tz)

    def office_usage(self, tz: ThermalZone) -> Union[str, list]:
        """function to determine which office corresponds based on the area of
        the thermal zone and the table on:
        https://skepp.com/en/blog/office-tips/this-is-how-many-square-meters-of
        -office-space-you-need-per-person

        Args:
            tz: bim2sim thermalzone instance
        Returns
            matching usage as string or a list of str of no fitting
            usage could be found
        """

        default_matches = ["Single office",
                           "Group Office (between 2 and 6 employees)",
                           "Open-plan Office (7 or more employees)"]
        if tz.gross_area:
            area = tz.gross_area.m
            if area <= 7:
                return default_matches[0]
            elif 7 < area <= 42:
                return default_matches[1]
            else:
                return default_matches[2]
            # case area not available
        else:
            return default_matches

    @staticmethod
    def list_decision_usage(tz: ThermalZone, choices: list) -> ListDecision:
        """decision to select an usage that matches the zone name

        Args:
            tz: bim2sim ThermalZone instance
            choices: list of possible answers
        Returns:
            usage_decision: ListDecision to find the correct usage
            """
        usage_decision = ListDecision("Which usage does the Space %s have?" %
                                      (str(tz.usage)),
                                      choices=choices,
                                      key=tz,
                                      global_key="%s_%s.BpsUsage" %
                                                 (type(tz).__name__, tz.guid),
                                      allow_skip=False,
                                      live_search=True)
        return usage_decision

    def load_usage(self, tz: ThermalZone):
        """loads the usage of the corresponding ThermalZone.

        Loads the usage from the statistical data in assets/enrichment/usage.

        Args:
            tz: bim2sim ThermalZone instance
        """
        use_condition = self.use_conditions[tz.usage]
        for attr, value in use_condition.items():
            # avoid to overwrite attrs present on the instance
            if getattr(tz, attr) is None:
                value = self.value_processing(value)
                setattr(tz, attr, value)

    @staticmethod
    def value_processing(value):
        """"""
        if isinstance(value, dict):
            values = next(iter(value.values()))
            return values[0]/values[1]
        else:
            return value
