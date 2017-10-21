# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>


"""The NeuroBlender materials module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements the manipulation of materials.
"""


import os
from glob import glob
import random
import numpy as np
import mathutils

import bpy


# =========================================================================== #
# material assignment
# =========================================================================== #


def materialise(ob, colourtype='primary6',
                colourpicker=(1, 1, 1), trans=1,
                name_pf='', idx=-1):
    """Attach material to an object."""

    if ob is None:
        info = "no object to materialise"
        return info

    scn = bpy.context.scene
    nb = scn.nb

    primary6_colours = [[1, 0, 0], [0, 1, 0], [0, 0, 1],
                        [1, 1, 0], [1, 0, 1], [0, 1, 1]]

    ob.show_transparent = True

    matname = ob.name + name_pf

    diffcol = [1, 1, 1]
    mix = 0.05
    diff_rn = 0.1

    if idx < 0:
        idx = eval("nb.index_%s" % nb.objecttype)
    if colourtype == "none":
        mix = 0.0
        diff_rn = 0.0
        trans = 1.0
    elif colourtype == "golden_angle":
        diffcol = get_golden_angle_colour(idx)
    elif colourtype == "primary6":
        diffcol = primary6_colours[idx % len(primary6_colours)]
    elif colourtype == "pick":
        diffcol = list(colourpicker)
    elif colourtype == "random":
        diffcol = [random.random() for _ in range(3)]

    diffcol.append(trans)

    if ob.type == "CURVE":
        ob.data.use_uv_as_generated = True
        group = make_nodegroup_dirtracts()
    elif ob.type == "MESH":
        group = make_nodegroup_dirsurfaces()

    mat = make_cr_mat_basic(matname, diffcol, mix, diff_rn, group)

    link_innode(mat, colourtype)

    set_materials(ob.data, mat)

    infostring = "material: "
    infostring += "type='{}'; "
    infostring += "colour=[{:.1f}, {:.1f}, {:.1f}, {:.1f}];"
    info = infostring.format(colourtype, *diffcol)

    return info


def link_innode(mat, colourtype):

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    diff = nodes["Diffuse BSDF"]
    emit = nodes["Emission"]

    if colourtype == "directional":
        inp = nodes["diff_ingroup"]
    else:
        inp = nodes["RGB"]

    links.new(inp.outputs["Color"], diff.inputs["Color"])
    links.new(inp.outputs["Color"], emit.inputs["Color"])


def switch_mode_mat(mat, newmode):
    """Connect either emitter (scientific) or shader (artistic)."""

    # TODO: better handle materials that do not have Emission and MixDiffGlos
    if mat.node_tree is None:
        return

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    out = nodes["Material Output"]

    if newmode == "scientific":
        try:
            output = nodes["Emission"].outputs["Emission"]
        except:
            pass
        else:
            links.new(output, out.inputs["Surface"])
    elif newmode == "artistic":
        try:
            output = nodes["MixDiffGlos"].outputs["Shader"]
        except:
            pass
        else:
            links.new(output, out.inputs["Surface"])


def set_materials(me, mat):
    """Attach a material to a mesh.

    TODO: make sure shifting the material slots around
          does not conflict with per-vertex material assignment
    """

    if isinstance(mat, bpy.types.Material):
        mats = [mat for mat in me.materials]
        mats.insert(0, mat)
        me.materials.clear()
        for mat in mats:
            me.materials.append(mat)


def get_golden_angle_colour(i):
    """Return the golden angle colour from an integer number of steps."""

    c = mathutils.Color()
    h = divmod(111.25/360 * i, 1)[1]
    c.hsv = h, 1, 1

    return list(c)


def CR2BR(mat):
    """Copy Cycles settings to Blender Render material."""

    mat.use_nodes = False

    try:
        rgb = mat.node_tree.nodes["RGB"]
    except (KeyError, AttributeError):
        pass
    else:
        mat.diffuse_color = rgb.outputs[0].default_value[0:3]

    try:
        trans = mat.node_tree.nodes["Transparency"]
    except (KeyError, AttributeError):
        pass
    else:
        mat.use_transparency = True
        mat.alpha = trans.outputs[0].default_value


def BR2CR(mat):
    """Copy Blender Render settings to Cycles material."""

    mat.use_nodes = True

    try:
        rgb = mat.node_tree.nodes["RGB"]
    except KeyError:
        pass
    else:
        rgb.outputs[0].default_value[0:3] = mat.diffuse_color

    try:
        trans = mat.node_tree.nodes["Transparency"]
    except KeyError:
        pass
    else:
        mat.use_transparency = True
        trans.outputs[0].default_value = mat.alpha


# ========================================================================== #
# mapping properties to vertices
# ========================================================================== #


def set_vertex_group(ob, name, label=None, scalars=None):
    """Create a vertex group.

    For labels, a vertex subset is included with weight 1.
    For scalars, the full vertex set is included
    with weights set to the scalar values.
    TODO: decide whether to switch to weight paint mode
        bpy.context.scene.objects.active = ob
        ob.select = True
        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    """

    # NOTE: do not use the more pythonic 'label = []' => 'if label:'
    # it selects all vertices when there are empty labels in the labelgroup
    if label is None:
        label = range(len(ob.data.vertices))

    if scalars is None:
        scalars = [1] * len(label)

    vg = ob.vertex_groups.new(name)
    for i, l in enumerate(list(label)):
        vg.add([int(l)], scalars[i], "REPLACE")
    vg.lock_weight = True

    ob.vertex_groups.active_index = vg.index

    return vg


def set_materials_to_vertexgroups(ob, vgs, mats):
    """Attach materials to vertexgroups."""

    if vgs is None:
        set_materials(ob.data, mats[0])
    else:
        mat_idxs = []
        for mat in mats:
            ob.data.materials.append(mat)
            mat_idxs.append(len(ob.data.materials) - 1)

        assign_materialslots_to_faces(ob, vgs, mat_idxs)


def assign_materialslots_to_faces(ob, vgs=None, mat_idxs=[]):
    """Assign a material slot to faces in associated with a vertexgroup."""

    idx_lookup = {g.index: mat_idx for g, mat_idx in zip(vgs, mat_idxs)}
    me = ob.data
    for poly in me.polygons:
        loop_mat_idxs = []
        for vi in poly.vertices:
            allgroups = [g.group for g in me.vertices[vi].groups]
            if len(allgroups) == 1:
                loop_mat_idxs.append(idx_lookup[allgroups[0]])
            elif len(allgroups) > 1:
                loop_mat_idxs.append(idx_lookup[allgroups[0]])
                # TODO: multi-group membership?
        if loop_mat_idxs:
            mat_idx = max(set(loop_mat_idxs), key=loop_mat_idxs.count)
            poly.material_index = mat_idx

    me.update()

    return ob


def reset_materialslots(ob, slot=0):
    """Reset material slots for every polygon to the first."""

    me = ob.data
    for poly in me.polygons:
        poly.material_index = slot
    me.update()

    return ob


def set_materials_to_polygonlayers(ob, pl, mats):
    """Attach materials to polygons in polygonlayers."""

    if pl is None:
        set_materials(ob.data, mats[0])
        return

    mat_idxs = []
    for mat in mats:
        ob.data.materials.append(mat)
        mat_idxs.append(len(ob.data.materials) - 1)

    assign_materialslots_to_faces_pls(ob, pl, mat_idxs)


def assign_materialslots_to_faces_pls(ob, pl=None, mat_idxs=[]):
    """Assign a material slot to faces according to polygon_layer."""

    me = ob.data
    for poly in me.polygons:
        poly.material_index = mat_idxs[pl.data[poly.index].value]
    me.update()

    return ob


def assign_vc(ob, vertexcolours, vgs, labelgroup=None, colour=[0, 0, 0]):
    """Assign RGB values to the vertex_colors attribute.

    TODO: find better ways to handle multiple assignments to vertexgroups
    """

    me = ob.data

    if labelgroup is not None:
        vgs_idxs = set([g.index for g in vgs])
        C = []
        for v in me.vertices:
            vgroups = set([g.group for g in v.groups])
            lgroup = vgroups & vgs_idxs
            try:
                idx = list(lgroup)[0]
            except IndexError:
                C.append(colour)
            else:
                idx = labelgroup.labels.find(ob.vertex_groups[idx].name)
                C.append(labelgroup.labels[idx].colour[0:3])
    else:
        # linear to sRGB
        gindex = vgs[0].index  # FIXME: assuming single vertex group here
        W = np.array([v.groups[gindex].weight for v in me.vertices])
        m = W > 0.00313066844250063
        W[m] = 1.055 * (np.power(W[m], (1.0 / 2.4))) - 0.055
        W[~m] = 12.92 * W[~m]
        C = np.transpose(np.tile(W, [3, 1]))

    for poly in me.polygons:
        for idx, vi in zip(poly.loop_indices, poly.vertices):
            vertexcolours.data[idx].color = C[vi]

    me.update()

    return ob


def load_surface_textures(name, directory, nframes):
    """Load and switch to a NeuroBlender surface texture."""

    try:
        mat = bpy.data.materials[name]
    except KeyError:
        pass
    else:
        absdir = bpy.path.abspath(directory)
        try:
            fpath = glob(os.path.join(absdir, '*.png'))[0]
        except IndexError:
            pass
        else:
            bpy.data.images.load(fpath, check_existing=False)
            fname = os.path.basename(fpath)
            img = bpy.data.images[fname]
            img.source = 'SEQUENCE'

            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            itex = nodes["Image Texture"]
            srgb = nodes["Separate RGB"]
            # TODO: cyclic timeseries
#             itex.image_user.use_cyclic = True
            itex.image_user.use_auto_refresh = True
            itex.image_user.frame_duration = nframes
            itex.image = img
            links.new(itex.outputs["Color"], srgb.inputs["Image"])


# ========================================================================== #
# cycles node generation
# ========================================================================== #


def make_cr_mat_basic(name, diff_col, mix=0.04,
                      diff_rn=0.1, diff_ingroup=None):
    """Create a Cycles material (basic).

    The material mixes difffuse, transparent and glossy.
    """

    diffuse = {'colour': diff_col, 'roughness': diff_rn}
    glossy = {'colour': (1.0, 1.0, 1.0, 1.0), 'roughness': 0.1}

    scn = bpy.context.scene
    nb = scn.nb

    engine = scn.render.engine
    if not engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 600, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "MixDiffGlos"
    mix1.name = prefix + "MixDiffGlos"
    mix1.inputs[0].default_value = mix
    mix1.location = 400, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = prefix + "Glossy BSDF"
    glos.inputs[0].default_value = glossy['colour']
    glos.inputs[1].default_value = glossy['roughness']
    glos.distribution = "BECKMANN"
    glos.location = 200, -100

    emit = nodes.new("ShaderNodeEmission")
    emit.label = "Emission"
    emit.name = prefix + "Emission"
    emit.location = 400, 200

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "MixDiffTrans"
    mix2.name = prefix + "MixDiffTrans"
    mix2.inputs[0].default_value = diffuse['colour'][3]
    mix2.location = 200, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = prefix + "Transparent BSDF"
    trans.location = 0, 0

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = prefix + "Diffuse BSDF"
    diff.inputs[0].default_value = diffuse['colour']
    diff.inputs[1].default_value = diffuse['roughness']
    diff.location = 0, -100

    rgb = nodes.new("ShaderNodeRGB")
    rgb.label = "RGB"
    rgb.name = prefix + "RGB"
    rgb.outputs[0].default_value = diffuse['colour']
    rgb.location = -200, 300

    tval = nodes.new("ShaderNodeValue")
    tval.label = "Transparency"
    tval.name = prefix + "Transparency"
    tval.outputs[0].default_value = 1.0
    tval.location = -200, 100
    # TODO: set min/max to 0/1

    if nb.settingprops.mode == "scientific":
        links.new(emit.outputs["Emission"], out.inputs["Surface"])
    elif nb.settingprops.mode == "artistic":
        links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(mix2.outputs["Shader"], mix1.inputs[1])
    links.new(mix2.outputs["Shader"], emit.inputs["Color"])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
#     links.new(rgb.outputs[0], mix2.inputs[0])
    links.new(trans.outputs["BSDF"], mix2.inputs[1])
    links.new(diff.outputs["BSDF"], mix2.inputs[2])
    links.new(tval.outputs["Value"], mix2.inputs["Fac"])
    links.new(tval.outputs["Value"], emit.inputs["Strength"])
    links.new(rgb.outputs["Color"], emit.inputs["Color"])
    links.new(rgb.outputs["Color"], diff.inputs["Color"])

    if diff_ingroup is not None:
        in_node = nodes.new("ShaderNodeGroup")
        in_node.location = -200, 0
        in_node.name = "diff_ingroup"
        in_node.label = "diff_ingroup"
        in_node.node_tree = diff_ingroup

    # for switching to Blender Render
    mat.diffuse_color = rgb.outputs["Color"].default_value[0:3]
    mat.use_transparency = True
    mat.alpha = tval.outputs["Value"].default_value

    scn.render.engine = engine
    mat.use_nodes = scn.render.engine == "CYCLES"

    return mat


def make_material_emit_cycles(name, emission):
    """Create a Cycles emitter material for lighting."""

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    emit = nodes.new("ShaderNodeEmission")
    emit.label = "Emission"
    emit.name = prefix + "Emission"
    emit.inputs[0].default_value = emission['colour']
    emit.inputs[1].default_value = emission['strength']
    emit.location = 600, -100

    links.new(emit.outputs["Emission"], out.inputs["Surface"])

    return mat


def make_nodegroup_dirtracts(name="DirTractsGroup"):
    """Create a nodegroup for directional (tangent) tract colour.

    # http://blender.stackexchange.com/questions/43102
    """

    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    group.outputs.new("NodeSocketColor", "Color")

    nodes = group.nodes
    links = group.links

    nodes.clear()
    prefix = ""

    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (-200, 0)

    crgb = nodes.new("ShaderNodeCombineRGB")
    crgb.label = "Combine RGB"
    crgb.name = prefix + "Combine RGB"
    crgb.location = -400, 0
    crgb.hide = True

    invt = nodes.new("ShaderNodeInvert")
    invt.label = "Invert"
    invt.name = prefix + "Invert"
    invt.location = -600, -150
    invt.hide = True

    math1 = nodes.new("ShaderNodeMath")
    math1.label = "Add"
    math1.name = prefix + "MathAdd"
    math1.operation = 'ADD'
    math1.location = -800, -150
    math1.hide = True

    math2 = nodes.new("ShaderNodeMath")
    math2.label = "Absolute"
    math2.name = prefix + "MathAbs2"
    math2.operation = 'ABSOLUTE'
    math2.location = -1000, -50
    math2.hide = True

    math3 = nodes.new("ShaderNodeMath")
    math3.label = "Absolute"
    math3.name = prefix + "MathAbs1"
    math3.operation = 'ABSOLUTE'
    math3.location = -1000, 0
    math3.hide = True

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = prefix + "Separate RGB"
    srgb.location = -1200, 0
    srgb.hide = True

    tang = nodes.new("ShaderNodeTangent")
    tang.label = "Tangent"
    tang.name = prefix + "Tangent"
    tang.direction_type = 'UV_MAP'
    tang.location = -1400, 0

    links.new(crgb.outputs["Image"], output_node.inputs[0])
    links.new(invt.outputs["Color"], crgb.inputs[2])
    links.new(math2.outputs["Value"], crgb.inputs[1])
    links.new(math3.outputs["Value"], crgb.inputs[0])
    links.new(math1.outputs["Value"], invt.inputs["Color"])
    links.new(math2.outputs["Value"], math1.inputs[1])
    links.new(math3.outputs["Value"], math1.inputs[0])
    links.new(srgb.outputs["G"], math2.inputs["Value"])
    links.new(srgb.outputs["R"], math3.inputs["Value"])
    links.new(tang.outputs["Tangent"], srgb.inputs["Image"])

    return group


def make_nodegroup_dirsurfaces(name="DirSurfacesGroup"):
    """Create a nodegroup for directional (normal) surface colour."""

    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    group.outputs.new("NodeSocketColor", "Color")

    nodes = group.nodes
    links = group.links

    nodes.clear()
    prefix = ""

    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (-200, 0)

    geom = nodes.new("ShaderNodeNewGeometry")
    geom.label = "Geometry"
    geom.name = prefix + "Geometry"
    geom.location = -400, 0

    links.new(geom.outputs["Normal"], output_node.inputs[0])

    return group


def make_cr_mat_surface_sg(scalargroup, img=[]):
    """Create a Cycles material for colourramped vertexcolour rendering."""

    scn = bpy.context.scene
    nb = scn.nb

    mat = (bpy.data.materials.get(scalargroup.name) or
           bpy.data.materials.new(scalargroup.name))
    mat.use_nodes = True
    mat.use_vertex_color_paint = True
    mat.use_vertex_color_light = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "MixDiffGlos"
    mix1.name = prefix + "MixDiffGlos"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = prefix + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    emit = nodes.new("ShaderNodeEmission")
    emit.label = "Emission"
    emit.name = prefix + "Emission"
    emit.location = 600, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = prefix + "Diffuse BSDF"
    diff.location = 400, 100

    vrgb = nodes.new("ShaderNodeValToRGB")
    vrgb.label = "ColorRamp"
    vrgb.name = prefix + "ColorRamp"
    vrgb.location = 100, 100

    if hasattr(scalargroup, 'nn_elements'):
        scalargroup.colourmap_enum = 'jet'

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = prefix + "Separate RGB"
    srgb.location = -300, 100

    attr = nodes.new("ShaderNodeAttribute")
    attr.location = -500, 300
    attr.name = prefix + "Attribute"
    attr.attribute_name = scalargroup.name
    attr.label = "Attribute"

    itex = nodes.new("ShaderNodeTexImage")
    itex.location = -500, -100
    if img:
        itex.image = img
    itex.label = "Image Texture"

    tval = nodes.new("ShaderNodeValue")
    tval.label = "Value"
    tval.name = prefix + "Value"
    tval.outputs[0].default_value = 1.0
    tval.location = 400, 300

    if nb.settingprops.mode == "scientific":
        links.new(emit.outputs["Emission"], out.inputs["Surface"])
    elif nb.settingprops.mode == "artistic":
        links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(diff.outputs["BSDF"], mix1.inputs[1])
    links.new(vrgb.outputs["Color"], emit.inputs["Color"])
    links.new(vrgb.outputs["Color"], diff.inputs["Color"])
    links.new(srgb.outputs["R"], vrgb.inputs["Fac"])
    links.new(attr.outputs["Color"], srgb.inputs["Image"])
    links.new(tval.outputs["Value"], emit.inputs["Strength"])

    return mat


def make_cr_mat_tract_sg(name, img, group):
    """Create a Cycles material for a tract scalargroup."""

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    groupnode = nodes.new("ShaderNodeGroup")
    groupnode.location = 600, 0
    groupnode.name = prefix + "NodeGroup"
    groupnode.node_tree = group
    groupnode.label = "NodeGroup"

    itex = nodes.new("ShaderNodeTexImage")
    itex.location = 400, 100
    itex.name = prefix + "Image Texture"
    itex.image = img
    itex.label = "Image texture"

    texc = nodes.new("ShaderNodeTexCoord")
    texc.location = 200, 100
    texc.name = prefix + "Texture Coordinate"
    texc.label = "Texture Coordinate"

    links.new(groupnode.outputs["Shader"], out.inputs["Surface"])
    links.new(itex.outputs["Color"], groupnode.inputs["Color"])
    links.new(texc.outputs["UV"], itex.inputs["Vector"])

    return mat


def make_cr_matgroup_tract_sg(diffcol, mix=0.04, nb_ov=None):
    """Create a Cycles material group for a tract scalargroup."""

    diffuse = {'colour': diffcol, 'roughness': 0.1}
    glossy = {'colour': (1.0, 1.0, 1.0, 1.0), 'roughness': 0.1}

    name = "TractOvGroup.{}".format(nb_ov.name)
    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    group.inputs.new("NodeSocketColor", "Color")
    group.outputs.new("NodeSocketShader", "Shader")

    nodes = group.nodes
    links = group.links

    nodes.clear()

    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (800, 0)

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "MixDiffGlos"
    mix1.name = "MixDiffGlos"
    mix1.inputs[0].default_value = mix
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = "Glossy BSDF"
    glos.inputs[0].default_value = glossy['colour']
    glos.inputs[1].default_value = glossy['roughness']
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "MixDiffTrans"
    mix2.name = "MixDiffTrans"
    mix2.inputs[0].default_value = diffuse['colour'][3]
    mix2.location = 400, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = "Transparent BSDF"
    trans.location = 200, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = "Diffuse BSDF"
    diff.inputs[0].default_value = diffuse['colour']
    diff.inputs[1].default_value = diffuse['roughness']
    diff.location = 200, 0

    vrgb = nodes.new("ShaderNodeValToRGB")
    vrgb.label = "ColorRamp"
    vrgb.name = "ColorRamp"
    vrgb.location = -100, 100

    nb_ov.colourmap_enum = 'jet'

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = "Separate RGB"
    srgb.location = -300, 100

    input_node = group.nodes.new("NodeGroupInput")
    input_node.location = (-500, 0)

    links.new(mix1.outputs["Shader"], output_node.inputs[0])
    links.new(mix2.outputs["Shader"], mix1.inputs[1])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(trans.outputs["BSDF"], mix2.inputs[1])
    links.new(diff.outputs["BSDF"], mix2.inputs[2])
    links.new(vrgb.outputs["Color"], diff.inputs["Color"])
    links.new(srgb.outputs["R"], vrgb.inputs["Fac"])
    links.new(input_node.outputs[0], srgb.inputs["Image"])

    return group


def make_material_bake_cycles(name, vcname=None, img=None):
    """Create a Cycles material to bake vc to texture."""

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True
    mat.use_vertex_color_paint = True
    mat.use_vertex_color_light = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = "Material Output"
    out.location = 800, 0

    emit = nodes.new("ShaderNodeEmission")
    emit.label = "Emission"
    emit.name = "Emission"
    emit.location = 600, 0

    attr = nodes.new("ShaderNodeAttribute")
    attr.location = 400, 0
    attr.name = "Attribute"
    if vcname is not None:
        attr.attribute_name = vcname
    attr.label = "Attribute"

    itex = nodes.new("ShaderNodeTexImage")
    itex.location = 400, -200
    if img is not None:
        itex.image = img
    itex.label = "Image Texture"

    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    links.new(attr.outputs["Color"], emit.inputs["Color"])

    return mat
