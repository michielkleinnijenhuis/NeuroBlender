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

# =========================================================================== #

import bpy

import os
import random
import numpy as np

from . import tractblender_utils as tb_utils
from . import tractblender_import as tb_imp

# =========================================================================== #
# material assignment
# =========================================================================== #


def materialise(ob, colourtype='primary6', colourpicker=(1,1,1)):
    """Attach material to an object."""

    primary6_colours = [[1, 0, 0], [0, 1, 0], [0, 0, 1],
                        [1, 1, 0], [1, 0, 1], [0, 1, 1]]

    ob.show_transparent = True

    # TODO: proper cycling through primary6
    ii = 0
    if colourtype in ["primary6", "random", "pick"]:

        if colourtype == "primary6":
            matname = "primary6_" + str(ii % 6)
            diffcol = primary6_colours[ii % 6] + [1.]
        elif colourtype == "random":
            matname = "random_" + str(ii)
            diffcol = [random.random() for _ in range(3)] + [1.]
        elif colourtype == "pick":
            matname = "picked_" + str(ii)
            diffcol = list(colourpicker) + [1.]

        if bpy.data.materials.get(matname) is not None:
            mat = bpy.data.materials[matname]
        else:
#             mat = make_material(matname, diffcol, alpha=1.)
            diffuse = {'colour': diffcol, 'roughness': 0.1}
            glossy = {'colour': (1.0, 1.0, 1.0, 1.0), 'roughness': 0.1}
            mat = make_material_basic_cycles(matname, diffuse, glossy, mix=0.05)
        set_material(ob.data, mat)

    elif colourtype == "directional":

        matname = colourtype + ob.type
        
        if ob.type == "CURVE":
            mat = make_material_dirtract_cycles(matname)
            ob.data.use_uv_as_generated = True
            set_material(ob.data, bpy.data.materials[matname])
        elif ob.type == "MESH":
            map_to_vertexcolours(ob, vcname=matname, colourtype=colourtype)
    else:
        pass


def set_material(me, mat):
    """Attach a material to a mesh."""

    if len(me.materials):
        me.materials[0] = mat
    else:
        me.materials.append(mat)


def make_material(name="Material",
                  diffuse=[1, 0, 0, 1], specular=[1, 1, 1, 0.5], alpha=1):
    """Create a basic material."""

    mat = bpy.data.materials.new(name)
    mat.diffuse_color = diffuse[:3]
    mat.diffuse_shader = "LAMBERT"
    mat.diffuse_intensity = diffuse[3]
    mat.specular_color = specular[:3]
    mat.specular_shader = "COOKTORR"
    mat.specular_intensity = specular[3]
    mat.alpha = alpha
    mat.use_transparency = True
    mat.ambient = 1

    return mat


def make_material_vc_blender(name, fpath=""):
    """Create a material for vertexcolour mapping."""

    name = tb_utils.check_name(name, fpath, checkagainst=bpy.data.materials)
    mat = bpy.data.materials.new(name)
    mat.use_vertex_color_paint = True
    mat.use_vertex_color_light = True
# http://blenderartists.org/forum/showthread.php?247846-Context-problem
#     bpy.context.scene.game_settings.material_mode = "GLSL"
#     if bpy.context.scene.render.engine = "BLENDER_RENDER"
#         bpy.context.space_data.show_textured_solid = True

    return mat


# ========================================================================== #
# mapping properties to vertices
# ========================================================================== #


def normalize_scalars(scalars):
    """"""
    scalarmin = np.amin(scalars)
    scalarmax = np.amax(scalars)
    scalars -= scalarmin
    scalars *= 1/(scalarmax-scalarmin)

    return scalars, [scalarmin, scalarmax]


def create_vg_annot(ob, fpath):
    """"""

    tb = bpy.context.scene.tb
    obtype = tb.objecttype
    idx = eval("tb.index_%s" % obtype)
    tb_ob = eval("tb.%s[%d]" % (obtype, idx))

    labels, ctab, names = tb_imp.import_surfannot(ob, fpath)

    basename = os.path.basename(fpath)
    vgs = []
    for i, labelname in enumerate(names):
        vgname = basename + '.' + labelname.decode('utf-8')
        vgname = tb_utils.check_name(vgname, fpath="", 
                                     checkagainst=ob.vertex_groups)
        label = np.where(labels==i)[0]
        vg = set_vertex_group(ob, vgname, label)
        vgs.append(vg)

        label = tb_ob.labels.add()
        label.name = vgname
        label.value = ctab[i, 4]
        label.colour = ctab[i,0:4]/255
        tb_ob.index_labels = (len(tb_ob.labels)-1)

    map_to_vertexcolours(ob, vcname='vc_'+basename, vgs=vgs, labelflag=True)

def create_vc_overlay(ob, fpath, labelflag=False):
    """Create scalar overlay for a a full mesh object."""

    scalars = tb_imp.import_surfscalars(ob, fpath)
    scalars, scalarrange = normalize_scalars(scalars)

    vgs = ob.vertex_groups
    vgname = tb_utils.check_name("", fpath, checkagainst=vgs)
    vg = set_vertex_group(ob, vgname, label=None, scalars=scalars)

    tb = bpy.context.scene.tb
    obtype = tb.objecttype
    idx = eval("tb.index_%s" % obtype)
    tb_ob = eval("tb.%s[%d]" % (obtype, idx))
    scalar = tb_ob.scalars.add()
    scalar.name = vgname
    scalar.range = scalarrange
    tb_ob.index_scalars = (len(tb_ob.scalars)-1)

    map_to_vertexcolours(ob, vcname='vc_'+vgname, vgs=[vg])


def create_vg_overlay(ob, fpath, labelflag=False):
    """Create scalar overlay for a vertex group from labelfile."""

    vgs = ob.vertex_groups
    vgname = tb_utils.check_name("", fpath, checkagainst=vgs)
    vg = labelidxs_to_vertexgroup(ob, vgname, fpath, labelflag)
    map_to_vertexcolours(ob, vcname='vc_'+vgname, 
                         vgs=[vg], labelflag=labelflag)


def labelidxs_to_vertexgroup(ob, vgname="", fpath="", labelflag=False):
    
    tb = bpy.context.scene.tb
    obtype = tb.objecttype
    idx = eval("tb.index_%s" % obtype)
    tb_ob = eval("tb.%s[%d]" % (obtype, idx))

    label, scalars = tb_imp.import_surflabel(ob, fpath, labelflag)

    if scalars is not None:
        vgscalars, scalarrange = normalize_scalars(scalars)
        scalar = tb_ob.scalars.add()
        scalar.name = vgname
        scalar.range = scalarrange
        tb_ob.index_scalars = (len(tb_ob.scalars)-1)
    else:
        lab = tb_ob.labels.add()
        lab.name = vgname
        labvalues = [label.value for label in tb_ob.labels]
        lab.value = max(labvalues) + 1
        lab.colour = [random.random() for _ in range(4)]
        tb_ob.index_labels = (len(tb_ob.labels)-1)
#         if scalars is None, the label is simply stored as a vertexgroup (w=1)

    vg = set_vertex_group(ob, vgname, label, scalars)

    return vg


def set_vertex_group(ob, name, label=None, scalars=None):
    """"""

    if label is None:
        label = range(len(ob.data.vertices))

    if scalars is None:
        w = np.ones(len(label))
    else:
        w = scalars

    vg = ob.vertex_groups.new(name)
    for i, l in enumerate(list(label)):
        vg.add([int(l)], w[i], "REPLACE")
    vg.lock_weight = True

    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")

    return vg


def get_vidxs_in_groups(ob, vgs=None):
    """Return the vertex indices within vertex groups."""

    if vgs is None: vgs = ob.vertex_groups

    group_lookup = {g.index: g.name for g in vgs}
    vidxs = {name: [] for name in group_lookup.values()}
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group in list(group_lookup.keys()):
                vidxs[group_lookup[g.group]].append(v.index)

    return vidxs


# =========================================================================== #
# mapping properties or weights to vertexcolours
# =========================================================================== #


def vgs2vc():
    """Create a vertex colour layer from (multiple) vertex groups."""

    tb = bpy.context.scene.tb
    print('use groups: ', tb.vgs2vc)


def map_to_vertexcolours(ob, vcname="", fpath="",
                         vgs=None, labelflag=False,
                         colourtype=""):
    """"""

    # need a unique name (same for "Vertex Colors" and "Material")
    # TODO: but maybe not for 'directional'?
    vcs = ob.data.vertex_colors
    vcname = tb_utils.check_name(vcname, fpath, checkagainst=vcs)
    materials = bpy.data.materials
    vcname = tb_utils.check_name(vcname, fpath, checkagainst=materials)

    mat = get_vc_material(ob, vcname, fpath, colourtype, labelflag)
    set_material(ob.data, mat)
    vc = get_vertexcolours(ob, vcname, fpath)
    ob = assign_vc(ob, vc, vgs, colourtype, labelflag)

    bpy.ops.object.mode_set(mode="VERTEX_PAINT")


def get_vc_material(ob, name, fpath, colourtype="", labelflag=False):
    """"""
    
    materials = bpy.data.materials
    if materials.get(name) is not None:  # mostly for 'directional'
        mat = materials.get(name)
    else:
        if colourtype == "directional":
            name = colourtype + ob.type
            name = tb_utils.check_name(name, "", checkagainst=materials)
            mat = make_material_dirsurf_cycles(name)
        elif labelflag:
            mat = make_material_labels_cycles(name, name)
        else:
            mat = make_material_overlay_cycles(name, name)
    
    return mat


def get_vertexcolours(ob, name="", fpath=""):
    """Create a new vertex_colors attribute."""

    vcs = ob.data.vertex_colors
    vertexcolours = vcs.new(name=name)
#     name = tb_utils.check_name(name, fpath, checkagainst=vcs)
    ob.data.vertex_colors.active = vertexcolours

    return vertexcolours


def map_rgb_value(scalar, colourmapping="r2k"):
    """Map a scalar to RGB in a certain colour map."""

    if colourmapping == "r2k":
        rgb = (scalar, 0, 0)
    elif colourmapping == "g2k":
        rgb = (0, scalar, 0)
    elif colourmapping == "b2k":
        rgb = (0, 0, scalar)
    elif colourmapping == "fscurv":  # direct r2g cmap centred on 0
        if scalar < 0:
            rgb = (-scalar, 0, 0)
        if scalar >= 0:
            rgb = (0, scalar, 0)
    
    return rgb


def lookup_rgb():
    """"""
    pass


def assign_vc(ob, vertexcolours, vgs=None, 
              colourtype="", labelflag=False):
    """Assign RGB values to the vertex_colors attribute."""

    tb = bpy.context.scene.tb
    obtype = tb.objecttype
    idx = eval("tb.index_%s" % obtype)
    tb_ob = eval("tb.%s[%d]" % (obtype, idx))

    if vgs is not None:
        group_lookup = {g.index: g.name for g in vgs}

    me = ob.data
    i = 0
    for poly in me.polygons:
        for idx in poly.loop_indices:
            vi = ob.data.loops[idx].vertex_index
            if colourtype == "directional":
                rgb = me.vertices[vi].normal
            elif labelflag:
                rgb = vertexcolour_fromlabel(me.vertices[vi], 
                                             vgs, group_lookup, tb_ob.labels)
            else:
                w = sum_vertexweights(me.vertices[vi], vgs, group_lookup)
#                 rgb = weights_to_colour(w)
                rgb = (w, w, w)
                # map_rgb_value(scalars[vi], colourmapping)
            vertexcolours.data[i].color = rgb  # TODO: foreach_set?
            i += 1
    me.update()

    return ob


def vertexcolour_fromlabel(v, vgs, group_lookup, labels):
    """"""

    rgba = []
    for g in v.groups:
        if g.group in list(group_lookup.keys()):
#             TODO: do this with key-value?
            i=0
            while labels[i].name != group_lookup[g.group]:
                i += 1
            rgba.append(labels[i].colour)

    if not rgba:
        rgba = [0.5, 0.5, 0.5, 1.0]
    else:
        # TODO: proper handling of multiple labels
        rgba = np.array(rgba)
        if rgba.ndim > 1:
            rgba = np.mean(rgba, axis=0)
        else:
            rgba = rgba

    return tuple(rgba[0:3])


def sum_vertexweights(v, vgs, group_lookup):
    """"""

    w = 0
    for g in v.groups:
        if g.group in list(group_lookup.keys()):
            w += g.weight

    return w


# ========================================================================== #
# cycles node generation
# ========================================================================== #


def make_material_basic_cycles(name, diffuse, glossy, mix=0.04):
    """"""

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or 
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node = nodes.new("ShaderNodeOutputMaterial")
    node.label = "Material Output"
    node.name = name + "_" + "Material Output"
    node.location = 800, 0

    node = nodes.new("ShaderNodeMixShader")
    node.label = "Mix Shader"
    node.name = name + "_" + "Mix Shader"
    node.inputs[0].default_value = mix
    node.location = 600, 0

    node = nodes.new("ShaderNodeBsdfGlossy")
    node.label = "Glossy BSDF"
    node.name = name + "_" + "Glossy BSDF"
    node.inputs[0].default_value = glossy['colour']
    node.inputs[1].default_value = glossy['roughness']
    node.distribution = "BECKMANN"
    node.location = 400, -100

    node = nodes.new("ShaderNodeBsdfDiffuse")
    node.label = "Diffuse BSDF"
    node.name = name + "_" + "Diffuse BSDF"
    node.inputs[0].default_value = diffuse['colour']
    node.inputs[1].default_value = diffuse['roughness']
    node.location = 400, 100

    links.new(nodes[name + "_" + "Mix Shader"].outputs["Shader"],
              nodes[name + "_" + "Material Output"].inputs["Surface"])
    links.new(nodes[name + "_" + "Glossy BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[2])
    links.new(nodes[name + "_" + "Diffuse BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[1])

    return mat


def make_material_emit_cycles(name, emission):
    """"""

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or 
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node = nodes.new("ShaderNodeOutputMaterial")
    node.label = "Material Output"
    node.name = name + "_" + "Material Output"
    node.location = 800, 0

    node = nodes.new("ShaderNodeEmission")
    node.label = "Emission"
    node.name = name + "_" + "Emission"
    node.inputs[0].default_value = emission['colour']
    node.inputs[1].default_value = emission['strength']
    node.location = 600, -100

    links.new(nodes[name + "_" + "Emission"].outputs["Emission"],
              nodes[name + "_" + "Material Output"].inputs["Surface"])

    return mat


def make_material_dirsurf_cycles(name):
    """"""

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or 
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node = nodes.new("ShaderNodeOutputMaterial")
    node.label = "Material Output"
    node.name = name + "_" + "Material Output"
    node.location = 800, 0

    node = nodes.new("ShaderNodeMixShader")
    node.label = "Mix Shader"
    node.name = name + "_" + "Mix Shader"
    node.inputs[0].default_value = 0.04
    node.location = 600, 0

    node = nodes.new("ShaderNodeBsdfGlossy")
    node.label = "Glossy BSDF"
    node.name = name + "_" + "Glossy BSDF"
    node.inputs[1].default_value = 0.15
    node.distribution = "BECKMANN"
    node.location = 400, -100

    node = nodes.new("ShaderNodeBsdfDiffuse")
    node.label = "Diffuse BSDF"
    node.name = name + "_" + "Diffuse BSDF"
    node.location = 400, 100

    node = nodes.new("ShaderNodeAttribute")
    node.label = "Attribute"
    node.name = name + "_" + "Attribute"
    node.attribute_name = name
    node.location = 200, 100


    links.new(nodes[name + "_" + "Mix Shader"].outputs["Shader"],
              nodes[name + "_" + "Material Output"].inputs["Surface"])
    links.new(nodes[name + "_" + "Glossy BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[2])
    links.new(nodes[name + "_" + "Diffuse BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[1])
    links.new(nodes[name + "_" + "Attribute"].outputs["Color"],
              nodes[name + "_" + "Diffuse BSDF"].inputs["Color"])

    return mat


def make_material_dirtract_cycles(name):
    """
    # http://blender.stackexchange.com/questions/43102
    """

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or 
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node = nodes.new("ShaderNodeOutputMaterial")
    node.label = "Material Output"
    node.name = name + "_" + "Material Output"
    node.location = 800, 0

    node = nodes.new("ShaderNodeMixShader")
    node.label = "Mix Shader"
    node.name = name + "_" + "Mix Shader"
    node.inputs[0].default_value = 0.04
    node.location = 600, 0

    node = nodes.new("ShaderNodeBsdfGlossy")
    node.label = "Glossy BSDF"
    node.name = name + "_" + "Glossy BSDF"
    node.inputs[1].default_value = 0.15
    node.distribution = "BECKMANN"
    node.location = 400, -100

    node = nodes.new("ShaderNodeBsdfDiffuse")
    node.label = "Diffuse BSDF"
    node.name = name + "_" + "Diffuse BSDF"
    node.location = 400, 100

    node = nodes.new("ShaderNodeCombineRGB")
    node.label = "Combine RGB"
    node.name = name + "_" + "Combine RGB"
    node.location = 200, 100
    node.hide = True

    node = nodes.new("ShaderNodeInvert")
    node.label = "Invert"
    node.name = name + "_" + "Invert"
    node.location = 000, -50
    node.hide = True
    
    node = nodes.new("ShaderNodeMath")
    node.label = "Add"
    node.name = name + "_" + "MathAdd"
    node.operation = 'ADD'
    node.location = -200, -50
    node.hide = True

    node = nodes.new("ShaderNodeMath")
    node.label = "Absolute"
    node.name = name + "_" + "MathAbs2"
    node.operation = 'ABSOLUTE'
    node.location = -400, 50
    node.hide = True

    node = nodes.new("ShaderNodeMath")
    node.label = "Absolute"
    node.name = name + "_" + "MathAbs1"
    node.operation = 'ABSOLUTE'
    node.location = -400, 100
    node.hide = True

    node = nodes.new("ShaderNodeSeparateRGB")
    node.label = "Separate RGB"
    node.name = name + "_" + "Separate RGB"
    node.location = -600, 100
    node.hide = True

    node = nodes.new("ShaderNodeTangent")
    node.label = "Tangent"
    node.name = name + "_" + "Tangent"
    node.direction_type = 'UV_MAP'
    node.location = -800, 100


    links.new(nodes[name + "_" + "Mix Shader"].outputs["Shader"],
              nodes[name + "_" + "Material Output"].inputs["Surface"])
    links.new(nodes[name + "_" + "Glossy BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[2])
    links.new(nodes[name + "_" + "Diffuse BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[1])
    links.new(nodes[name + "_" + "Combine RGB"].outputs["Image"],
              nodes[name + "_" + "Diffuse BSDF"].inputs["Color"])
    links.new(nodes[name + "_" + "Invert"].outputs["Color"],
              nodes[name + "_" + "Combine RGB"].inputs[2])
    links.new(nodes[name + "_" + "MathAbs2"].outputs["Value"],
              nodes[name + "_" + "Combine RGB"].inputs[1])
    links.new(nodes[name + "_" + "MathAbs1"].outputs["Value"],
              nodes[name + "_" + "Combine RGB"].inputs[0])
    links.new(nodes[name + "_" + "MathAdd"].outputs["Value"],
              nodes[name + "_" + "Invert"].inputs["Color"])
    links.new(nodes[name + "_" + "MathAbs2"].outputs["Value"],
              nodes[name + "_" + "MathAdd"].inputs[1])
    links.new(nodes[name + "_" + "MathAbs1"].outputs["Value"],
              nodes[name + "_" + "MathAdd"].inputs[0])
    links.new(nodes[name + "_" + "Separate RGB"].outputs["G"],
              nodes[name + "_" + "MathAbs2"].inputs["Value"])
    links.new(nodes[name + "_" + "Separate RGB"].outputs["R"],
              nodes[name + "_" + "MathAbs1"].inputs["Value"])
    links.new(nodes[name + "_" + "Tangent"].outputs["Tangent"],
              nodes[name + "_" + "Separate RGB"].inputs["Image"])
    
    return mat


def make_material_overlay_cycles(name, vcname):
    """"""

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or 
           bpy.data.materials.new(name))
    mat.use_nodes = True
    mat.use_vertex_color_paint = True
    mat.use_vertex_color_light = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node = nodes.new("ShaderNodeOutputMaterial")
    node.label = "Material Output"
    node.name = name + "_" + "Material Output"
    node.location = 800, 0

    node = nodes.new("ShaderNodeMixShader")
    node.label = "Mix Shader"
    node.name = name + "_" + "Mix Shader"
    node.inputs[0].default_value = 0.04
    node.location = 600, 0

    node = nodes.new("ShaderNodeBsdfGlossy")
    node.label = "Glossy BSDF"
    node.name = name + "_" + "Glossy BSDF"
    node.inputs[1].default_value = 0.15
    node.distribution = "BECKMANN"
    node.location = 400, -100

    node = nodes.new("ShaderNodeBsdfDiffuse")
    node.label = "Diffuse BSDF"
    node.name = name + "_" + "Diffuse BSDF"
    node.location = 400, 100

    node = nodes.new("ShaderNodeValToRGB")
    node.label = "ColorRamp"
    node.name = name + "_" + "ColorRamp"
    node.location = 100, 100
    set_colorramp_preset(node, mat=mat)

    node = nodes.new("ShaderNodeMath")
    node.label = "Multiply"
    node.name = name + "_" + "Math"
    node.operation = 'MULTIPLY'
    node.inputs[1].default_value = 1.0
    node.location = -100, 100

    node = nodes.new("ShaderNodeSeparateRGB")
    node.label = "Separate RGB"
    node.name = name + "_" + "Separate RGB"
    node.location = -300, 100

    node = nodes.new("ShaderNodeAttribute")
    node.location = -500, 100
    node.name = name + "_" + vcname
    node.attribute_name = vcname
    node.label = "Attribute"

#     driver = diffuse.inputs[1].driver_add("default_value")
#     var = driver.driver.variables.new()
#     var.name = "variable"
#     var.targets[0].data_path = "PATH"
#     var.targets[0].id = "Target_Object_Name"
#     driver.driver.expression = "variable"
# 
#     # remove driver
#     diffuse.inputs[1].driver_remove("default_value")

    links.new(nodes[name + "_" + "Mix Shader"].outputs["Shader"], 
              nodes[name + "_" + "Material Output"].inputs["Surface"])
    links.new(nodes[name + "_" + "Glossy BSDF"].outputs["BSDF"], 
              nodes[name + "_" + "Mix Shader"].inputs[2])
    links.new(nodes[name + "_" + "Diffuse BSDF"].outputs["BSDF"], 
              nodes[name + "_" + "Mix Shader"].inputs[1])
    links.new(nodes[name + "_" + "ColorRamp"].outputs["Color"], 
              nodes[name + "_" + "Diffuse BSDF"].inputs["Color"])
    links.new(nodes[name + "_" + "Math"].outputs["Value"], 
              nodes[name + "_" + "ColorRamp"].inputs["Fac"])
    links.new(nodes[name + "_" + "Separate RGB"].outputs["R"], 
              nodes[name + "_" + "Math"].inputs["Value"])
    links.new(nodes[name + "_" + vcname].outputs["Color"], 
              nodes[name + "_" + "Separate RGB"].inputs["Image"])
    
    return mat


def make_material_labels_cycles(name, vcname):
    """"""

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or 
           bpy.data.materials.new(name))
    mat.use_nodes = True
    mat.use_vertex_color_paint = True
    mat.use_vertex_color_light = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node = nodes.new("ShaderNodeOutputMaterial")
    node.label = "Material Output"
    node.name = name + "_" + "Material Output"
    node.location = 800, 0

    node = nodes.new("ShaderNodeMixShader")
    node.label = "Mix Shader"
    node.name = name + "_" + "Mix Shader"
    node.inputs[0].default_value = 0.04
    node.location = 600, 0

    node = nodes.new("ShaderNodeBsdfGlossy")
    node.label = "Glossy BSDF"
    node.name = name + "_" + "Glossy BSDF"
    node.inputs[1].default_value = 0.15
    node.distribution = "BECKMANN"
    node.location = 400, -100

    node = nodes.new("ShaderNodeBsdfDiffuse")
    node.label = "Diffuse BSDF"
    node.name = name + "_" + "Diffuse BSDF"
    node.location = 400, 100

    node = nodes.new("ShaderNodeAttribute")
    node.location = 200, 100
    node.name = name + "_" + vcname
    node.attribute_name = vcname
    node.label = "Attribute"

    links.new(nodes[name + "_" + "Mix Shader"].outputs["Shader"],
              nodes[name + "_" + "Material Output"].inputs["Surface"])
    links.new(nodes[name + "_" + "Glossy BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[2])
    links.new(nodes[name + "_" + "Diffuse BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[1])
    links.new(nodes[name + "_" + vcname].outputs["Color"],
              nodes[name + "_" + "Diffuse BSDF"].inputs["Color"])

    return mat


def set_colorramp_preset(node, cmapname="r2b", mat=None):
    """"""

    tb = bpy.context.scene.tb
    obtype = tb.objecttype
    idx = eval("tb.index_%s" % obtype)
    tb_ob = eval("tb.%s[%d]" % (obtype, idx))
    scalarslist = tb_ob.scalars

    elements = node.color_ramp.elements

    for el in elements[1:]:
        elements.remove(el) 

    if (cmapname == "fscurv") | (mat.name.endswith(".curv")):
        i = 0
        while 'vc_' + scalarslist[i].name != mat.name:
            i += 1
        sr = scalarslist[i].range
        positions = [(-sr[0]-0.2)/(sr[1]-sr[0]),
                     (-sr[0]-0.0)/(sr[1]-sr[0]),
                     (-sr[0]+0.2)/(sr[1]-sr[0])]
        colors = [(1.0, 0.0, 0.0, 1.0),
                  (0.5, 0.5, 0.5, 1.0),
                  (0.0, 1.0, 0.0, 1.0)]
    elif cmapname == "r2g":
        positions = [0.0, 1.0]
        colors = [(1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0)]
    elif cmapname == "r2b":
        positions = [0.0, 1.0]
        colors = [(1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0)]
    elif cmapname == "g2b":
        positions = [0.0, 1.0]
        colors = [(0.0, 1.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0)]

    # FIXME: wromng range and multiplication factors on loading!
    # TODO: extend colourmaps
#     node.color_ramp.color_mode = 'HSV'  # HSV, HSL / RGB
#     # NEAR, FAR, CW, CCW / LINEAR, B_SPLINE, ...Z
#     node.color_ramp.hue_interpolation = 'NEAR'

    for p in positions[1:]:
        elements.new(p)

    elements.foreach_set("position", positions)
    for i in range(len(colors)): setattr(elements[i], "color", colors[i])
#     elements.foreach_set("color", colors)  # FIXME!
#     collection.foreach_set(seq, attr)
#     # Python equivalent
#     for i in range(len(seq)): setattr(collection[i], attr, seq[i])
