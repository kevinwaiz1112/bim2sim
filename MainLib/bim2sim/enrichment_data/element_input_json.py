from bim2sim.decision import BoolDecision, ListDecision


def load_element_ifc(element, ele_ifc, enrich_parameter, parameter_value, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the ifc type and year.
    """
    binding = dataclass.element_bind
    for a in binding:
        if binding[a]["ifc_type"] == ele_ifc:
            for b in binding[a][enrich_parameter]:
                if b == str(parameter_value):
                    for c in binding[a][enrich_parameter][b]:
                        setattr(element, str(c),
                                binding[a][enrich_parameter][b][c])


def load_element_class(instance, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the class, parameter and parameter value.
    """

    ele_class = str(instance.__class__)[
                str(instance.__class__).rfind(".") + 1:str(instance.__class__).rfind("'")]
    binding = dict(dataclass.element_bind)
    if ele_class in binding:
        attrs_enrich = dict(binding[ele_class])
        del attrs_enrich["class"]
    else:
        return {}

    # check if element has enrich parameter-value?
    for enrich_parameter in attrs_enrich:
        if hasattr(instance, enrich_parameter):
            if getattr(instance, enrich_parameter) in attrs_enrich[enrich_parameter]:
                return attrs_enrich[enrich_parameter][str(getattr(instance, enrich_parameter))]

    return attrs_enrich

    # # 4. ask for enrichment parameter and values
    # options = {}
    # options_enrich_parameter = list(attrs_enrich.keys())
    # # no enrichment exists
    # if len(options_enrich_parameter) < 1:
    #     return {}
    # # only one enrich_parameter
    # elif len(options_enrich_parameter) == 1:
    #     options_parameter_value = list(attrs_enrich[options_enrich_parameter[0]])
    #     if len(options_parameter_value) == 1:
    #         return attrs_enrich[options_enrich_parameter[0]][options_parameter_value[0]]
    #     else:
    #         decision = ListDecision("Multiple possibilities found",
    #                                 choices=options_parameter_value,
    #                                 global_key="%s_%s.Enrich_Parameter" % (instance.ifc_type, instance.guid),
    #                                 allow_skip=True, allow_load=True, allow_save=True,
    #                                 collect=False, quick_decide=not True)
    #         decision.decide()
    #         return attrs_enrich[options_enrich_parameter[0]][str(decision.value)]
    # # many enrich parameter
    # else:
    #     decision1 = ListDecision("Multiple possibilities found",
    #                              choices=options_enrich_parameter,
    #                              global_key="%s_%s.Enrich_Parameter" % (instance.ifc_type, instance.guid),
    #                              allow_skip=True, allow_load=True, allow_save=True,
    #                              collect=False, quick_decide=not True)
    #     decision1.decide()
    #     decision1.collection.clear()
    #     decision1.stored_decisions.clear()
    #     options_parameter_value = list(attrs_enrich[decision1.value])
    #     # one parameter value
    #     if len(options_parameter_value) == 1:
    #         return attrs_enrich[decision1.value][options_parameter_value[0]]
    #     # many parameter values
    #     else:
    #         decision2 = ListDecision("Multiple possibilities found",
    #                                  choices=options_parameter_value,
    #                                  global_key="%s_%s.Parameter_Value" % (instance.ifc_type, instance.guid),
    #                                  allow_skip=True, allow_load=True, allow_save=True,
    #                                  collect=False, quick_decide=not True)
    #         decision2.decide()
    #         return attrs_enrich[str(decision1.value)][str(decision2.value)]

