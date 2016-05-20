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
import mathutils

from . import tractblender_utils as tb_utils
from . import tractblender_import as tb_imp

# =========================================================================== #
# material assignment
# =========================================================================== #


def materialise(ob, colourtype='primary6', colourpicker=(1, 1, 1), trans=1):
    """Attach material to an object."""

    primary6_colours = [[1, 0, 0], [0, 1, 0], [0, 0, 1],
                        [1, 1, 0], [1, 0, 1], [0, 1, 1]]

    ob.show_transparent = True

    if colourtype == "none":
        mat = None

    elif colourtype in ["primary6", 
                        "random", 
                        "pick", 
                        "golden_angle"]:

        matname = tb_utils.check_name(colourtype, fpath="",
                                      checkagainst=ob.data.materials,
                                      zfill=3, forcefill=True)

        if colourtype == "primary6":
            diffcol = primary6_colours[int(matname[-3:]) % 6]
        elif colourtype == "random":
            diffcol = [random.random() for _ in range(3)]
        elif colourtype == "pick":
            diffcol = list(colourpicker)
        elif colourtype == "golden_angle":
            rgb = get_golden_angle_colour(int(matname[-3:]))
            diffcol = rgb
        diffcol.append(trans)

        if bpy.data.materials.get(matname) is not None:
            mat = bpy.data.materials[matname]
        else:
            mat = make_material_basic_cycles(matname, diffcol, mix=0.05)

    elif colourtype == "directional":
        matname = colourtype + ob.type
        if ob.type == "CURVE":
            ob.data.use_uv_as_generated = True
            mat = make_material_dirtract_cycles(matname, trans)
        elif ob.type == "MESH":
            mat = make_material_dirsurf_cycles(matname, trans)

    set_materials(ob.data, mat)


def set_materials(me, mat):
    """Attach a material to a mesh."""

    me.materials.append(mat)
    for i, mat in enumerate(tuple(me.materials)):
        new_idx = len(me.materials)-1-i
        me.materials[new_idx] = mat


def make_material(name="Material",
                  diffuse=[1, 0, 0, 1], specular=[1, 1, 1, 0.5], alpha=1):
    """Create a basic Blender Internal material."""

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
    """Create a material for vertexcolour mapping.

    # http://blenderartists.org/forum/showthread.php?247846-Context-problem
    #     bpy.context.scene.game_settings.material_mode = "GLSL"
    #     if bpy.context.scene.render.engine = "BLENDER_RENDER"
    #         bpy.context.space_data.show_textured_solid = True
    """

    name = tb_utils.check_name(name, fpath, checkagainst=bpy.data.materials)
    mat = bpy.data.materials.new(name)
    mat.use_vertex_color_paint = True
    mat.use_vertex_color_light = True

    return mat


def get_golden_angle_colour(i):
    """Return the golden angle colour from an integer number of steps."""

    c = mathutils.Color()
    h = divmod(111.25/360 * i, 1)[1]
    c.hsv = h, 1, 1

    return list(c)


# ========================================================================== #
# mapping properties to vertices
# ========================================================================== #


def create_vc_overlay(ob, fpath, is_label=False):
    """Create scalar overlay for a surface object."""

    scalars = tb_imp.read_surfscalar(ob, fpath)
    scalars, scalarrange = tb_imp.normalize_data(scalars)

    vgname = tb_utils.check_name("", fpath, checkagainst=ob.vertex_groups)

    vg = set_vertex_group(ob, vgname, label=None, scalars=scalars)

    tb_imp.add_scalar_to_collection(vgname, scalarrange)

    map_to_vertexcolours(ob, vcname='vc_'+vgname, vgs=[vg])
#     map_to_uv(ob, uvname='uv_'+vgname, vgs=[vg])


def create_vg_annot(ob, fpath):
    """Import an annotation file to vertex groups.
    
    TODO: decide what is the best approach:
    reading gifti and converting to freesurfer format (current) or
    have a seperate functions for handling .gii annotations
    (this can be found in commit c3b6d66)
    """

    tb_ob = tb_utils.active_tb_object()[0]

    labels, ctab, names = tb_imp.read_surfannot(fpath)

    basename = os.path.basename(fpath)
    for i, labelname in enumerate(names):

        vgname = basename + '.' + labelname
        vgname = tb_utils.check_name(vgname, fpath="",
                                     checkagainst=ob.vertex_groups)

        label = np.where(labels == i)[0]
        value = ctab[i, 4]
        diffcol = ctab[i, 0:4]/255

        vg = set_vertex_group(ob, vgname, label)

        matname = tb_utils.check_name(vgname, fpath="",
                                      checkagainst=bpy.data.materials)
        mat = make_material_basic_cycles(matname, diffcol, mix=0.05)
        set_materials_to_vertexgroups(ob, [vg], [mat])

        tb_imp.add_label_to_collection(vgname, value, diffcol)
    # TODO: similar handling of label overlays


def create_vg_overlay(ob, fpath, is_label=False, trans=1):
    """Create label/scalar overlay from a labelfile.

    Note that a (freesurfer) labelfile can contain scalars.
    If scalars are available and is_label=False (loaded from scalars-menu),
    a scalar-type overlay will be generated.
    """

    tb_ob = tb_utils.active_tb_object()[0]

    label, scalars = tb_imp.read_surflabel(ob, fpath, is_label)

    vgname = tb_utils.check_name(name="", fpath=fpath,
                                 checkagainst=ob.vertex_groups)

    if scalars is not None:
        vgscalars, scalarrange = tb_imp.normalize_data(scalars)

        vg = set_vertex_group(ob, vgname, label, scalars)

        tb_imp.add_scalar_to_collection(vgname, scalarrange)

        # TODO: only set this material to vertexgroup
        map_to_vertexcolours(ob, vcname='vc_'+vgname,
                             vgs=[vg], is_label=is_label)

    else:
        vg = set_vertex_group(ob, vgname, label, scalars)

        values = [label.value for label in tb_ob.labels] or [0]
        value = max(values) + 1
        diffcol = [random.random() for _ in range(3)]
        diffcol.append(trans)
        matname = tb_utils.check_name(vgname, fpath="",
                                      checkagainst=bpy.data.materials)
        mat = make_material_basic_cycles(matname, diffcol, mix=0.05)
        set_materials_to_vertexgroups(ob, [vg], [mat])

        tb_imp.add_label_to_collection(vgname, value, diffcol)


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

    return vg


def get_vidxs_in_groups(ob, vgs=None):
    """Return the vertex indices within vertex groups."""

    if vgs is None:
        vgs = ob.vertex_groups

    group_lookup = {g.index: g.name for g in vgs}
    vidxs = {name: [] for name in group_lookup.values()}
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group in list(group_lookup.keys()):
                vidxs[group_lookup[g.group]].append(v.index)

    return vidxs


def select_vertices_in_vertexgroups(ob, vgs=None):
    """Select the vertices in the vertexgroups."""

    if vgs is None:
        vgs = ob.vertex_groups

    group_lookup = {g.index: g.name for g in vgs}
    for v in ob.data.vertices:
        for g in v.groups:
            v.select = g.group in list(group_lookup.keys())


# =========================================================================== #
# vertex group materials
# =========================================================================== #


def set_materials_to_vertexgroups(ob, vgs, mats):
    """Attach materials to vertexgroups.

    see for operator-based method:
    https://wiki.blender.org/index.php/Dev:Py/Scripts/Cookbook/Materials/Multiple_Materials
    """

    if vgs is None:
        set_materials(ob.data, mats[0])
        return

    for vg, mat in zip(vgs, mats):
        idx = ob.vertex_groups.find(vg.name)
        ob.vertex_groups.active_index = idx
        ob.data.materials.append(mat)
        mat_idx = len(ob.data.materials) - 1
        assign_material_to_faces(ob, [vg], mat_idx)


def assign_material_to_faces(ob, vgs=None, mat_idx=0):
    """Assign a material to faces in associated with a vertexgroup.
    
    TODO: speed-up
    """

    if vgs is not None:
        group_lookup = {g.index: g.name for g in vgs}

    me = ob.data
    for poly in me.polygons:
        for idx in poly.loop_indices:
            v = me.vertices[ob.data.loops[idx].vertex_index]
            for g in v.groups:
                if g.group in list(group_lookup.keys()):
                    poly.material_index = mat_idx
    me.update()

    return ob


# =========================================================================== #
# mapping vertex weights to vertexcolours
# =========================================================================== #


def map_to_vertexcolours(ob, vcname="", fpath="",
                         vgs=None, is_label=False,
                         colourtype=""):
    """Write vertex group weights to a vertex colour attribute.
    
    A colourbar is prepared for scalar overlays.
    """

    vcs = ob.data.vertex_colors
    vcname = tb_utils.check_name(vcname, fpath, checkagainst=vcs)
    materials = bpy.data.materials
    vcname = tb_utils.check_name(vcname, fpath, checkagainst=materials)

    mat = make_material_overlay_cycles(name, name)

    set_materials_to_vertexgroups(ob, vgs, [mat])

    vc = vcs.new(name=vcname)
    ob.data.vertex_colors.active = vc
    ob = assign_vc(ob, vc, vgs, colourtype, is_label)

    if not is_label:  # TODO: label legend?
        cbar, vg = get_color_bar(name=vcname + "_colourbar")
        set_materials(cbar.data, mat)
        vc = vcs.new(name=vcname)
        cbar.data.vertex_colors.active = vc
        assign_vc(cbar, vc, [vg], colourtype, is_label)


def assign_vc(ob, vertexcolours, vgs=None,
              colourtype="", is_label=False):
    """Assign RGB values to the vertex_colors attribute.

    TODO: find better ways to handle multiple assignments to vertexgroups
    TODO: speed-up
    """

    tb_ob = tb_utils.active_tb_object()[0]

    if vgs is not None:
        group_lookup = {g.index: g.name for g in vgs}

    me = ob.data
    i = 0
    for poly in me.polygons:
        for idx in poly.loop_indices:
            vi = ob.data.loops[idx].vertex_index
            w = sum_vertexweights(me.vertices[vi], vgs, group_lookup)
            rgb = (w, w, w)
            vertexcolours.data[i].color = rgb  # TODO: foreach_set?
            i += 1
    me.update()

    return ob


def sum_vertexweights(v, vgs, group_lookup):
    """Sums the weights over all vertexgroups of a vertex.

    FIXME: this sums to >1 and is therefore not useable as rgb.
    """

    w = 0
    for g in v.groups:
        if g.group in list(group_lookup.keys()):
            w += g.weight

    return w


def vgs2vc():
    """Create a vertex colour layer from (multiple) vertex groups.

    TODO
    """

    tb = bpy.context.scene.tb
    print('use groups: ', tb.vgs2vc)


# =========================================================================== #
# voxelvolume texture mapping
# =========================================================================== #


def get_voxmatname(name):
    """Return a unique name for a voxelvolume material and texture."""

    matname = 'vv_' + name
    mats = bpy.data.materials
    matname = tb_utils.check_name(matname, fpath="", checkagainst=mats)
    texs = bpy.data.textures
    matname = tb_utils.check_name(matname, fpath="", checkagainst=texs)

    return matname


def get_voxmat(matname, img, dims, file_format="IMAGE_SEQUENCE", 
               is_overlay=False, is_label=False, labels=None):
    """Return a textured material for voxeldata."""

    tex = bpy.data.textures.new(matname, 'VOXEL_DATA')
    tex.use_preview_alpha = True
    tex.voxel_data.file_format = file_format
    if file_format == "IMAGE_SEQUENCE":
        tex.image_user.frame_duration = dims[2]
        tex.image_user.frame_start = 1
        tex.image_user.frame_offset = 0
        tex.image = img
    else:
        tex.voxel_data.filepath = img
        tex.voxel_data.resolution = [int(dim) for dim in dims]

    if is_label:
        tex.voxel_data.interpolation = "NEREASTNEIGHBOR"
        # FIXME: unexpected behaviour of colorramp
        # ... (image sequence data does not seem to agree with ticks on colorramp)
        tex.use_color_ramp = True
        cr = tex.color_ramp
        cr.interpolation = 'CONSTANT'
        cre = cr.elements
        cre[1].position = 0.001
        cre[1].color = labels[0].colour
        # FIXME: blender often crashes on creating colorramp ticks
        prevlabel = labels[0]
        maxlabel = max([label.value for label in labels])
#         offset = 1/maxlabel*1/2
        for label in labels[1:]:
#             el = cre.new((label.value-1)/maxlabel + offset)
            el = cre.new(prevlabel.value/maxlabel)
            el.color = label.colour
            prevlabel = label
    elif is_overlay:
        tex.use_color_ramp = True
        cr = tex.color_ramp
        cr.color_mode = 'HSV'
        cr.hue_interpolation = 'FAR'
        cre = cr.elements
        cre[0].color = (0, 0.01,1, 0)
        cre[1].color = (0, 0,   1, 1)
        # TODO: get easily customizable overlay colorramps

    mat = bpy.data.materials.new(matname)
    mat.type = "VOLUME"
    mat.volume.density = 0.

    texslot = mat.texture_slots.add()
    texslot.texture = tex
    texslot.use_map_density = True
    texslot.texture_coords = 'ORCO'
#     if is_overlay:
    texslot.use_map_emission = True

    return mat


# ========================================================================== #
# cycles node generation
# ========================================================================== #


def make_material_basic_cycles(name, diffcol, mix=0.04):
    """Create a basic Cycles material.

    The material mixes difffuse, transparent and glossy.
    """

    diffuse = {'colour': diffcol, 'roughness': 0.1}
    glossy = {'colour': (1.0, 1.0, 1.0, 1.0), 'roughness': 0.1}

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    name = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = name + "_" + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = name + "_" + "Mix Shader"
    mix1.inputs[0].default_value = mix
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = name + "_" + "Glossy BSDF"
    glos.inputs[0].default_value = glossy['colour']
    glos.inputs[1].default_value = glossy['roughness']
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "Mix Shader"
    mix2.name = name + "_" + "Mix Shader"
    mix2.inputs[0].default_value = diffuse['colour'][3]
    mix2.location = 400, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = name + "_" + "Transparent BSDF"
    trans.location = 200, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = name + "_" + "Diffuse BSDF"
    diff.inputs[0].default_value = diffuse['colour']
    diff.inputs[1].default_value = diffuse['roughness']
    diff.location = 200, 0

    links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(mix2.outputs["Shader"], mix1.inputs[1])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(trans.outputs["BSDF"], mix2.inputs[1])
    links.new(diff.outputs["BSDF"], mix2.inputs[2])

    return mat


def make_material_emit_cycles(name, emission):
    """Create a Cycles emitter material for lighting."""

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    name = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = name + "_" + "Material Output"
    out.location = 800, 0

    emit = nodes.new("ShaderNodeEmission")
    emit.label = "Emission"
    emit.name = name + "_" + "Emission"
    emit.inputs[0].default_value = emission['colour']
    emit.inputs[1].default_value = emission['strength']
    emit.location = 600, -100

    links.new(emit.outputs["Emission"], out.inputs["Surface"])

    return mat


def make_material_emit_internal(name, emission, is_addition=False):
    """Create a Blender Internal emitter material for lighting."""

    scn = bpy.context.scene
    if not scn.render.engine == "BLENDER_RENDER":
        scn.render.engine = "BLENDER_RENDER"

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    if not is_addition:
        nodes.clear()
    name = ""

    out = nodes.new("ShaderNodeOutput")
    out.label = "Output"
    out.name = name + "_" + "Output"
    out.location = 800, -500

    mtrl = nodes.new("ShaderNodeMaterial")
    mtrl.label = "Material"
    mtrl.name = name + "_" + "Material"
    mtrl.material = bpy.data.materials[mat.name]
    mtrl.location = 600, -600

    mat.diffuse_color = emission["colour"][:3]
    mat.emit = emission["strength"]

    links.new(mtrl.outputs["Color"], out.inputs["Color"])

    return mat


def make_material_dirsurf_cycles(name, trans=1):
    """Create a material for directional (normals) surface colour."""

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    mat = (bpy.data.materials.get(name) or
           bpy.data.materials.new(name))
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    name = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = name + "_" + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = name + "_" + "Mix Shader"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = name + "_" + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "Mix Shader"
    mix2.name = name + "_" + "Mix Shader"
    mix2.inputs[0].default_value = trans
    mix2.location = 400, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = name + "_" + "Transparent BSDF"
    trans.location = 200, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = name + "_" + "Diffuse BSDF"
    diff.location = 200, 0


    geom = nodes.new("ShaderNodeNewGeometry")
    geom.label = "Geometry"
    geom.name = name + "_" + "Geometry"
    geom.location = 0, 0

    links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(mix2.outputs["Shader"], mix1.inputs[1])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(trans.outputs["BSDF"], mix2.inputs[1])
    links.new(diff.outputs["BSDF"], mix2.inputs[2])

    links.new(geom.outputs["Normal"], diff.inputs["Color"])

    return mat


def make_material_dirtract_cycles(name, trans=1):
    """Create a material for directional (tangent) tract colour.

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
    name = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = name + "_" + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = name + "_" + "Mix Shader"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = name + "_" + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "Mix Shader"
    mix2.name = name + "_" + "Mix Shader"
    mix2.inputs[0].default_value = trans
    mix2.location = 400, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = name + "_" + "Transparent BSDF"
    trans.location = 200, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = name + "_" + "Diffuse BSDF"
    diff.location = 200, 0


    crgb = nodes.new("ShaderNodeCombineRGB")
    crgb.label = "Combine RGB"
    crgb.name = name + "_" + "Combine RGB"
    crgb.location = 0, 0
    crgb.hide = True

    invt = nodes.new("ShaderNodeInvert")
    invt.label = "Invert"
    invt.name = name + "_" + "Invert"
    invt.location = -200, -150
    invt.hide = True

    math1 = nodes.new("ShaderNodeMath")
    math1.label = "Add"
    math1.name = name + "_" + "MathAdd"
    math1.operation = 'ADD'
    math1.location = -400, -150
    math1.hide = True

    math2 = nodes.new("ShaderNodeMath")
    math2.label = "Absolute"
    math2.name = name + "_" + "MathAbs2"
    math2.operation = 'ABSOLUTE'
    math2.location = -600, -50
    math2.hide = True

    math3 = nodes.new("ShaderNodeMath")
    math3.label = "Absolute"
    math3.name = name + "_" + "MathAbs1"
    math3.operation = 'ABSOLUTE'
    math3.location = -600, 0
    math3.hide = True

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = name + "_" + "Separate RGB"
    srgb.location = -800, 0
    srgb.hide = True

    tang = nodes.new("ShaderNodeTangent")
    tang.label = "Tangent"
    tang.name = name + "_" + "Tangent"
    tang.direction_type = 'UV_MAP'
    tang.location = -1000, 0


    links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(mix2.outputs["Shader"], mix1.inputs[1])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(trans.outputs["BSDF"], mix2.inputs[1])
    links.new(diff.outputs["BSDF"], mix2.inputs[2])

    links.new(crgb.outputs["Image"], diff.inputs["Color"])
    links.new(invt.outputs["Color"], crgb.inputs[2])
    links.new(math2.outputs["Value"], crgb.inputs[1])
    links.new(math3.outputs["Value"], crgb.inputs[0])
    links.new(math1.outputs["Value"], invt.inputs["Color"])
    links.new(math2.outputs["Value"], math1.inputs[1])
    links.new(math3.outputs["Value"], math1.inputs[0])
    links.new(srgb.outputs["G"], math2.inputs["Value"])
    links.new(srgb.outputs["R"], math3.inputs["Value"])
    links.new(tang.outputs["Tangent"], srgb.inputs["Image"])

    return mat


def make_material_overlay_cycles(name, vcname):
    """Create a Cycles material for colourramped vertexcolour rendering."""

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
    name = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = name + "_" + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = name + "_" + "Mix Shader"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = name + "_" + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = name + "_" + "Diffuse BSDF"
    diff.location = 400, 100

    vrgb = nodes.new("ShaderNodeValToRGB")
    vrgb.label = "ColorRamp"
    vrgb.name = name + "_" + "ColorRamp"
    vrgb.location = 100, 100

    set_colorramp_preset(vrgb, mat=mat)

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = name + "_" + "Separate RGB"
    srgb.location = -300, 100

    attr = nodes.new("ShaderNodeAttribute")
    attr.location = -500, 100
    attr.name = name + "_" + "Attribute"
    attr.attribute_name = vcname
    attr.label = "Attribute"

#     driver = diffuse.inputs[1].driver_add("default_value")
#     var = driver.driver.variables.new()
#     var.name = "variable"
#     var.targets[0].data_path = "PATH"
#     var.targets[0].id = "Target_Object_Name"
#     driver.driver.expression = "variable"
#
#     # remove driver
#     diffuse.inputs[1].driver_remove("default_value")

    links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(diff.outputs["BSDF"], mix1.inputs[1])
    links.new(vrgb.outputs["Color"], diff.inputs["Color"])
    links.new(srgb.outputs["R"], vrgb.inputs["Value"])
    links.new(attr.outputs["Color"], srgb.inputs["Image"])

    return mat


def set_colorramp_preset(node, cmapname="r2b", mat=None):
    """Set a colourramp node to a preset."""

    tb_ob = tb_utils.active_tb_object()[0]
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
    for i in range(len(colors)):
        setattr(elements[i], "color", colors[i])
#     elements.foreach_set("color", colors)  # FIXME!
#     collection.foreach_set(seq, attr)
#     # Python equivalent
#     for i in range(len(seq)): setattr(collection[i], attr, seq[i])


# ========================================================================== #
# Colourbar
# ========================================================================== #


def get_color_bar(name="Colourbar", width=1., height=0.1):
    """Create, colour and label a colourbar."""

    if bpy.data.objects.get("Colourbars") is not None:
        cbars = bpy.data.objects.get("Colourbars")
    else:
        cbars = bpy.data.objects.new(name="Colourbars", object_data=None)
        bpy.context.scene.objects.link(cbars)

    if bpy.data.objects.get(name) is not None:
        ob = bpy.data.objects.get(name)
    else:
        ob = create_colourbar(name, width, height)
        ob.parent = cbars
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=100)
        bpy.ops.object.mode_set(mode='OBJECT')
        layer = 10
        tb_utils.move_to_layer(ob, layer)
        bpy.context.scene.layers[layer] = True

#     if ob.vertex_groups.get("all") is not None:
#         vg = ob.vertex_groups.get("all")
#     else:
    vg = ob.vertex_groups.new("all")
    for i, v in enumerate(ob.data.vertices):
        vg.add([i], v.co.x/width, "REPLACE")
    vg.lock_weight = True

    # FIXME: these only work for bar of default size: [1.0, 0.1]
    # FIXME: this only works for small scalarrange
    tb_ov, ov_idx = tb_utils.active_tb_overlay()
    scalarrange = tb_ov.range
      # ("label:%8.4f" % label['label'])
    labels = [{'label': "%4.2f" % scalarrange[0],
               'loc': [0.025, 0.015]},
              {'label': "%4.2f" % scalarrange[1],
               'loc': [0.80, 0.015]}]
    # NOTE: use loc[1]=-height for placement under the bar
    add_labels_to_colourbar(ob, labels, height)

    return ob, vg


def add_labels_to_colourbar(colourbar, labels, height):
    """Add labels to colourbar."""

    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 1}
    mat = make_material_emit_cycles("cbartext", emission)

    for label in labels:
        bpy.ops.object.text_add()
        text = bpy.context.scene.objects.active
        text.parent = colourbar
        text.scale[0] = height
        text.scale[1] = height
        text.location[0] = label['loc'][0]
        text.location[1] = label['loc'][1]
        text.data.body = label['label']
        text.name = "label:" + label['label']
        set_materials(text.data, mat)


def create_colourbar(name="Colourbar", width=1., height=0.1):
    """Create a plane of dimension width x height."""

    scn = bpy.context.scene

    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    scn.objects.link(ob)
    scn.objects.active = ob
    ob.select = True

    verts = [(0, 0, 0), (0, height, 0), (width, height, 0), (width, 0, 0)]
    faces = [(3, 2, 1, 0)]
    me.from_pydata(verts, [], faces)
    me.update()

    return ob




# ========================================================================== #
# DEPRECATED and development functions
# ========================================================================== #


def map_to_uv(ob, uvname="", fpath="",
              vgs=None, is_label=False,
              colourtype=""):
    """"""

    # need a unique name (same for "Vertex Colors" and "Material")
    # TODO: but maybe not for 'directional'?
    uvs = ob.data.uv_layers
    uvname = tb_utils.check_name(uvname, fpath, checkagainst=uvs)
    materials = bpy.data.materials
    uvname = tb_utils.check_name(uvname, fpath, checkagainst=materials)

    mat = get_vc_material(ob, uvname, fpath, colourtype, is_label)
    set_materials(ob.data, mat)
    ob.data.uv_textures.new(uvname)
    ob = assign_uv(ob, uv, vgs, colourtype, is_label)
#
#     if not is_label:
#         cbar, vg = get_color_bar(name=vcname + "_colourbar")
#         set_materials(cbar.data, mat)
#         uv = get_uv(cbar, uvname, fpath)
#         assign_uv(cbar, uv, [vg], colourtype, is_label)


def get_uv(ob, name="", fpath=""):
    """Create a new uv layer."""

    ob.data.uv_textures.new(name)
#     uv_layer = ob.data.loops.layers.uv[0]
#     ob.data.uv_layers.active = uv_layer

    return uv_layer


def assign_uv(ob, vertexcolours, vgs=None,
              colourtype="", is_label=False):
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
#             print(uv_layer[idx].uv)
#             uv_layer[idx].uv = ...  # get from flatmap
#             if colourtype == "directional":
#                 rgb = me.vertices[vi].normal
#             elif is_label:
#                 rgb = vertexcolour_fromlabel(me.vertices[vi],
#                                              vgs, group_lookup, tb_ob.labels)
#             else:
#                 w = sum_vertexweights(me.vertices[vi], vgs, group_lookup)
# #                 rgb = weights_to_colour(w)
#                 rgb = (w, w, w)
#                 # map_rgb_value(scalars[vi], colourmapping)
#             vertexcolours.data[i].color = rgb  # TODO: foreach_set?
#             i += 1
    me.update()

    return ob


def get_vc_material(ob, name, fpath, colourtype="", is_label=False):
    """Return a Cycles material that reads the vertex colour attribute."""

    materials = bpy.data.materials
    if materials.get(name) is not None:  # mostly for 'directional'
        mat = materials.get(name)
    else:
        if colourtype == "directional":
          # TODO: check if normals can avoid vertex colour 
          # by accesing directly from cycles attribute node
            name = colourtype + ob.type
            name = tb_utils.check_name(name, "", checkagainst=materials)
            mat = make_material_dirsurf_cycles(name)
        elif is_label:  # NOTE: labels not handled with vertex colour anymore
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


def vertexcolour_fromlabel(v, vgs, group_lookup, labels):
    """"""

    rgba = []
    for g in v.groups:
        if g.group in list(group_lookup.keys()):
            i = 0
            while labels[i].name != group_lookup[g.group]:
                i += 1
            rgba.append(labels[i].colour)
#             TODO: do this with key-value?

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


def make_material_labels_cycles(name, vcname):
    """Create a Cycles material for vertexcolour rendering."""

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
    name = ""

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
    node.name = name + "_" + "Attribute"
    node.attribute_name = vcname
    node.label = "Attribute"

    links.new(nodes[name + "_" + "Mix Shader"].outputs["Shader"],
              nodes[name + "_" + "Material Output"].inputs["Surface"])
    links.new(nodes[name + "_" + "Glossy BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[2])
    links.new(nodes[name + "_" + "Diffuse BSDF"].outputs["BSDF"],
              nodes[name + "_" + "Mix Shader"].inputs[1])
    links.new(nodes[name + "_" + "Attribute"].outputs["Color"],
              nodes[name + "_" + "Diffuse BSDF"].inputs["Color"])
    # FIXME: node names will truncate if too long; this will error

    return mat


