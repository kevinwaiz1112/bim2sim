from bim2sim.ifc2python.element import Element
import ifcopenshell
import ifcopenshell.geom
import math
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point


def find_building_polygon(slabs):

    settings = ifcopenshell.geom.settings()
    area_slab = 0
    slab_big = 0
    slab_rep = 0
    for slab in slabs:
        representation = Element.factory(slab)
        area_element = representation.area
        if area_element > area_slab:
            area_slab = area_element
            slab_big = slab
            slab_rep = representation

    shape = ifcopenshell.geom.create_shape(settings, slab_big)
    vertices = []
    i = 0
    while i < len(shape.geometry.verts):
        vertices.append(shape.geometry.verts[i:i + 2])
        i += 3

    p1 = [float("inf"), 0]
    p3 = [-float("inf"), 0]
    p4 = [0, float("inf")]
    p2 = [0, -float("inf")]

    for element in vertices:

        if element[0] < p1[0]:
            p1 = [element[0], element[1]]
        if element[0] > p3[0]:
            p3 = [element[0], element[1]]
        if element[1] < p4[1]:
            p4 = [element[0], element[1]]
        if element[1] > p2[1]:
            p2 = [element[0], element[1]]

    p1[0] = p1[0] + slab_rep.position[0]
    p3[0] = p3[0] + slab_rep.position[0]
    p4[0] = p4[0] + slab_rep.position[0]
    p2[0] = p2[0] + slab_rep.position[0]
    p1[1] = p1[1] + slab_rep.position[1]
    p3[1] = p3[1] + slab_rep.position[1]
    p4[1] = p4[1] + slab_rep.position[1]
    p2[1] = p2[1] + slab_rep.position[1]

    slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
    if 0.4 > slope > -0.4:
        cardinal_direction = ['E', 'W', 'N', 'S']
    elif 2.4 > slope > 0.4:
        cardinal_direction = ['NE', 'SW', 'NW', 'SE']
    elif -0.4 > slope > -2.4:
        cardinal_direction = ['SE', 'NW', 'SW', 'NE']
    else:
        cardinal_direction = []

    return p1, p2, p3, p4, cardinal_direction


def find_building_envelope(p1, p2, p3, p4):

    building_envelope = []
    tolerance = 4

    slope = abs((p2[1] - p1[1]) / (p2[0] - p1[0]))
    tolerance_x = tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p1[0] - tolerance_x, p1[1] + 2 * tolerance_y),
                                      (p2[0] + tolerance_x, p2[1] + 2 * tolerance_y),
                                      (p2[0] + tolerance_x, p2[1] - tolerance_y),
                                      (p1[0] - tolerance_x, p1[1] - tolerance_y)]))

    slope = abs((p3[1] - p2[1]) / (p3[0] - p2[0]))
    tolerance_x = 2 * tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p3[0] - tolerance_x, p3[1] - tolerance_y),
                                      (p2[0] - tolerance_x, p2[1] + tolerance_y),
                                      (p2[0] + 2 * tolerance_x, p2[1] + tolerance_y),
                                      (p3[0] + 2 * tolerance_x, p3[1] - tolerance_y)]))

    slope = abs((p4[1] - p3[1]) / (p4[0] - p3[0]))
    tolerance_x = tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p3[0] + tolerance_x, p3[1] - 2 * tolerance_y),
                                      (p4[0] - tolerance_x, p4[1] - 2 * tolerance_y),
                                      (p4[0] - tolerance_x, p4[1] + tolerance_y),
                                      (p3[0] + tolerance_x, p3[1] + tolerance_y)]))

    slope = abs((p1[1] - p4[1]) / (p1[0] - p4[0]))
    tolerance_x = 2 * tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p1[0] + tolerance_x, p1[1] + tolerance_y),
                                      (p4[0] + tolerance_x, p4[1] - tolerance_y),
                                      (p4[0] - 2 * tolerance_x, p4[1] - tolerance_y),
                                      (p1[0] - 2 * tolerance_x, p1[1] + tolerance_y)]))

    return building_envelope


def get_orientation(building_envelope, centroid, cardinal_direction):
    orientation = "Intern"
    if building_envelope[1].contains(centroid):
        orientation = cardinal_direction[0]
    elif building_envelope[3].contains(centroid):
        orientation = cardinal_direction[1]
    elif building_envelope[0].contains(centroid):
        orientation = cardinal_direction[2]
    elif building_envelope[2].contains(centroid):
        orientation = cardinal_direction[3]
    return orientation#
