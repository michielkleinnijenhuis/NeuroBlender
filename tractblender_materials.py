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

        ca = [ob.data.materials]
        matname = tb_utils.check_name(colourtype, "", ca, forcefill=True)

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
    """Attach a material to a mesh.

    TODO: make sure shifting the material slots around
          does not conflict with per-vertex material assignment
    """

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

    ca = [bpy.data.materials]
    name = tb_utils.check_name(name, fpath, ca)
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


def create_vc_overlay_tract(ob, fpath, name="", is_label=False):
    """Create scalar overlay for a surface object."""

    nn_scalars = tb_imp.read_tractscalar(fpath)
    datamin = float('Inf')
    datamax = -float('Inf')
    for s in nn_scalars:
        datamin = min(datamin, min(s))
        datamax = max(datamax, max(s))
    datarange = datamax - datamin
    scalarrange = datamin, datamax
    scalars = [(np.array(s) - datamin) / datarange for s in nn_scalars]

#     set_curve_weights(ob, name, label=None, scalars=scalars)

    tb_ob = tb_utils.active_tb_object()[0]
    ca = [tb_ob.scalars]
    name = tb_utils.check_name(name, fpath, ca)

    tb_imp.add_scalar_to_collection(name, scalarrange)

    ob.data.use_uv_as_generated = True
    diffcol = [0.0, 0.0, 0.0, 1.0]
    group = make_material_overlaytract_cycles_group(diffcol, mix=0.04)
    i = 0
    for spline, scalar in zip(ob.data.splines, scalars):

        # TODO: implement name check that checks for the prefix 'name'
        splname = name + '_spl' + str(i).zfill(8)
        ca = [bpy.data.images,
              bpy.data.materials]
        splname = tb_utils.check_name(splname, fpath, ca, maxlen=52)

        img = create_overlay_tract_img(splname, scalar)

        mat = make_material_overlaytract_cycles_withgroup(splname, img, group)
        ob.data.materials.append(mat)
        spline.material_index = len(ob.data.materials) - 1
        i += 1


def create_overlay_tract_img(name, scalar):
    """"""

    vals = [[val, val, val, 1.0] for val in scalar]
    img = bpy.data.images.new(name, len(scalar), 1)
    pixels = [chan for px in vals for chan in px]
    img.pixels = pixels
    img.source = 'GENERATED'

    return img


def set_curve_weights(ob, name, label=None, scalars=None):
    """"""

    for spline, scalar in zip(ob.data.splines, scalars):
        for point, val in zip(spline.points, scalar):
            point.co[3] = val


def create_vc_overlay(ob, fpath, name="", is_label=False):
    """Create scalar overlay for a surface object."""

    scalars = tb_imp.read_surfscalar(fpath)
    scalars, scalarrange = tb_imp.normalize_data(scalars)

    ca = [ob.vertex_groups,
          ob.data.vertex_colors,
          bpy.data.materials]
    name = tb_utils.check_name(name, fpath, ca)

    vg = set_vertex_group(ob, name, label=None, scalars=scalars)

    tb_imp.add_scalar_to_collection(name, scalarrange)

    map_to_vertexcolours(ob, name, [vg])

    # NOTE: UV is useless without proper flatmaps ...
#     uvname = 'uv_'+vgname
#     #img = create_overlay_tract_img(uvname, scalars)
#     nverts = len(ob.data.vertices)
#     imsize = np.ceil(np.sqrt(nverts))
#     img = bpy.data.images.new(uvname, imsize, imsize)
#     scalars = np.append(scalars, [0] * (imsize**2 - nverts))
#     vals = [[val, val, val, 1.0] for val in scalars]
#     pixels = [chan for px in vals for chan in px]
#     img.pixels = pixels
#     img.source = 'GENERATED'
#     map_to_uv(ob, uvname=uvname, img=img)


def create_vg_annot(ob, fpath, name=""):
    """Import an annotation file to vertex groups.

    TODO: decide what is the best approach:
    reading gifti and converting to freesurfer format (current) or
    have a seperate functions for handling .gii annotations
    (this can be found in commit c3b6d66)
    """

    if name:
        basename = name
    else:
        basename = os.path.basename(fpath)

    if fpath.endswith('.border'):
        borderlist = tb_imp.read_borders(fpath)
        create_polygon_layer_int(ob, borderlist)
        # (for each border?, will be expensive: do one for every file now)
        # this already takes a long time...

        new_mats = []
        for i, border in enumerate(borderlist):

            name = basename + '.border.' + border['name']
            ca = [ob.data.polygon_layers_int,
                  bpy.data.materials]
            name = tb_utils.check_name(name, "", ca)

            value = i + 1
            diffcol = list(border['rgb']) + [1.0]

            mat = make_material_basic_cycles(name, diffcol, mix=0.05)
            new_mats.append(mat)

            tb_imp.add_label_to_collection(name, value, diffcol)

        pl = ob.data.polygon_layers_int["pl"]
        set_materials_to_polygonlayers(ob, pl, new_mats)

    else:
        labels, ctab, names = tb_imp.read_surfannot(fpath)

        new_vgs = []
        new_mats = []
        for i, labelname in enumerate(names):

            name = basename + '.' + labelname
            ca = [ob.vertex_groups,
                  bpy.data.materials]
            name = tb_utils.check_name(name, "", ca)

            label = np.where(labels == i)[0]
            value = ctab[i, 4]
            diffcol = ctab[i, 0:4]/255

            vg = set_vertex_group(ob, name, label)
            new_vgs.append(vg)

            mat = make_material_basic_cycles(name, diffcol, mix=0.05)
            new_mats.append(mat)

            tb_imp.add_label_to_collection(name, value, diffcol)

        set_materials_to_vertexgroups(ob, new_vgs, new_mats)


def create_border_curves(ob, fpath, name=""):
    """Import an border file and create curves."""

    if name:
        basename = name
    else:
        basename = os.path.basename(fpath)

    borderlist = tb_imp.read_borders(fpath)

    bordergroup = bpy.data.objects.new(name=basename, object_data=None)
    bpy.context.scene.objects.link(bordergroup)
    bordergroup.parent = ob

    for i, border in enumerate(borderlist):

        name = border['name']
        ca = [bpy.data.objects,
              bpy.data.materials]
        name = tb_utils.check_name(name, "", ca)

        diffcol = list(border['rgb']) + [1.0]
        mat = make_material_basic_cycles(name, diffcol, mix=0.05)

        bevel_depth = 0.5
        bevel_resolution = 10
        iterations = 10
        factor = 0.5
        tb_imp.add_border_to_collection(name, diffcol,
                                        bevel_depth, bevel_resolution,
                                        iterations, factor)

        curve = bpy.data.curves.new(name=name, type='CURVE')
        curve.dimensions = '3D'
        curveob = bpy.data.objects.new(name, curve)
        bpy.context.scene.objects.link(curveob)
        tb_imp.make_polyline_ob_vi(curve, ob, border['verts'][:, 0])
        curveob.data.fill_mode = 'FULL'
        curveob.data.bevel_depth = bevel_depth
        curveob.data.bevel_resolution = bevel_resolution
        curveob.parent = bordergroup
        mod = curveob.modifiers.new("smooth", type='SMOOTH')
        mod.iterations = iterations
        mod.factor = factor
        set_materials(curveob.data, mat)


def create_polygon_layer_int(ob, borderlist):
    """Creates a polygon layer and sets value to the borderindex."""

    me = ob.data
    pl = me.polygon_layers_int.new("pl")
    loopsets = [set([vi for vi in poly.vertices]) for poly in me.polygons]
    for bi, border in enumerate(borderlist):
        pi = [loopsets.index(set(tri)) for tri in border['verts']]
        for poly in me.polygons:
            if poly.index in pi:
                # note that this overwrites double entriesZ
                pl.data[poly.index].value = bi


def create_vg_overlay(ob, fpath, name="", is_label=False, trans=1):
    """Create label/scalar overlay from a labelfile.

    Note that a (freesurfer) labelfile can contain scalars.
    If scalars are available and is_label=False (loaded from scalars-menu),
    a scalar-type overlay will be generated.
    """

    tb_ob = tb_utils.active_tb_object()[0]

    label, scalars = tb_imp.read_surflabel(fpath, is_label)

    ca = [ob.vertex_groups,
          bpy.data.materials]
    name = tb_utils.check_name(name, fpath, ca)

    if scalars is not None:
        vgscalars, scalarrange = tb_imp.normalize_data(scalars)

        vg = set_vertex_group(ob, name, label, scalars)

        tb_imp.add_scalar_to_collection(name, scalarrange)

        # TODO: only set this material to vertexgroup
        map_to_vertexcolours(ob, name, [vg], is_label)

    else:
        vg = set_vertex_group(ob, name, label, scalars)

        values = [label.value for label in tb_ob.labels] or [0]
        value = max(values) + 1
        diffcol = [random.random() for _ in range(3)] + [trans]
        mat = make_material_basic_cycles(name, diffcol, mix=0.05)
        set_materials_to_vertexgroups(ob, [vg], [mat])

        tb_imp.add_label_to_collection(name, value, diffcol)


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

    mat_idxs = []
    for mat in mats:
        ob.data.materials.append(mat)
        mat_idxs.append(len(ob.data.materials) - 1)

    assign_materialslots_to_faces(ob, vgs, mat_idxs)


def assign_materialslots_to_faces(ob, vgs=None, mat_idxs=[]):
    """Assign a material slot to faces in associated with a vertexgroup."""

    vgs_idxs = [g.index for g in vgs]
    if vgs is not None:
        group_lookup = {g.index: g.name for g in vgs}
        me = ob.data
        for poly in me.polygons:
            for vi in poly.vertices:
                for g in me.vertices[vi].groups:
                    if g.group in list(group_lookup.keys()):
                        mat_idx = mat_idxs[vgs_idxs.index(g.group)]
                        poly.material_index = mat_idx
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


# =========================================================================== #
# mapping vertex weights to vertexcolours
# =========================================================================== #


def map_to_vertexcolours(ob, name="", vgs=None, is_label=False, colourtype=""):
    """Write vertex group weights to a vertex colour attribute.

    A colourbar is prepared for scalar overlays.
    """

    mat = make_material_overlay_cycles(name, name, ob)

    set_materials_to_vertexgroups(ob, vgs, [mat])

    vcs = ob.data.vertex_colors
    vc = vcs.new(name=name)
    ob.data.vertex_colors.active = vc
    ob = assign_vc(ob, vc, vgs, colourtype, is_label)

    if not is_label:  # TODO: label legend?
        cbar, vg = get_color_bar(name=name + "_colourbar")
        set_materials(cbar.data, mat)
        vcs = cbar.data.vertex_colors
        vc = vcs.new(name=name)
        cbar.data.vertex_colors.active = vc
        assign_vc(cbar, vc, [vg], colourtype, is_label)


def assign_vc(ob, vertexcolours, vgs=None, colourtype="", is_label=False):
    """Assign RGB values to the vertex_colors attribute.

    TODO: find better ways to handle multiple assignments to vertexgroups
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
            w = linear_to_sRGB(w)
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


def sRGB_to_linear(C):
    """Converts sRGB to linear color space."""

    if(C <= 0.0404482362771082):
        L = C / 12.92
    else:
        L = pow(((C + 0.055) / 1.055), 2.4)

    return L


def linear_to_sRGB(L):
    """Converts linear to sRGB color space."""

    if (L > 0.00313066844250063):
        C = 1.055 * (pow(L, (1.0 / 2.4))) - 0.055
    else:
        C = 12.92 * L

    return C


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

    name = name
    ca = [bpy.data.materials,
          bpy.data.textures]
    name = tb_utils.check_name(name, "", ca)

    return name


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
        # ... (image sequence data does not seem ...
        # to agree with ticks on colorramp)
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
            el = cre.new(prevlabel.value/maxlabel)
#             el = cre.new((label.value-1)/maxlabel + offset)
            el.color = label.colour
            prevlabel = label
    elif is_overlay:
        tex.use_color_ramp = True
        cr = tex.color_ramp
        cr.color_mode = 'HSV'
        cr.hue_interpolation = 'FAR'
        cre = cr.elements
        cre[0].color = (0, 0.01, 1, 0)
        cre[1].color = (0, 0,    1, 1)
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
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = prefix + "Mix Shader"
    mix1.inputs[0].default_value = mix
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = prefix + "Glossy BSDF"
    glos.inputs[0].default_value = glossy['colour']
    glos.inputs[1].default_value = glossy['roughness']
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "Mix Shader"
    mix2.name = prefix + "Mix Shader"
    mix2.inputs[0].default_value = diffuse['colour'][3]
    mix2.location = 400, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = prefix + "Transparent BSDF"
    trans.location = 200, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = prefix + "Diffuse BSDF"
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
    prefix = ""

    out = nodes.new("ShaderNodeOutput")
    out.label = "Output"
    out.name = prefix + "Output"
    out.location = 800, -500

    mtrl = nodes.new("ShaderNodeMaterial")
    mtrl.label = "Material"
    mtrl.name = prefix + "Material"
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
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = prefix + "Mix Shader"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = prefix + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "Mix Shader"
    mix2.name = prefix + "Mix Shader"
    mix2.inputs[0].default_value = trans
    mix2.location = 400, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = prefix + "Transparent BSDF"
    trans.location = 200, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = prefix + "Diffuse BSDF"
    diff.location = 200, 0

    geom = nodes.new("ShaderNodeNewGeometry")
    geom.label = "Geometry"
    geom.name = prefix + "Geometry"
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
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = prefix + "Mix Shader"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = prefix + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    mix2 = nodes.new("ShaderNodeMixShader")
    mix2.label = "Mix Shader"
    mix2.name = prefix + "Mix Shader"
    mix2.inputs[0].default_value = trans
    mix2.location = 400, 100

    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.label = "Transparent BSDF"
    trans.name = prefix + "Transparent BSDF"
    trans.location = 200, 200

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = prefix + "Diffuse BSDF"
    diff.location = 200, 0

    crgb = nodes.new("ShaderNodeCombineRGB")
    crgb.label = "Combine RGB"
    crgb.name = prefix + "Combine RGB"
    crgb.location = 0, 0
    crgb.hide = True

    invt = nodes.new("ShaderNodeInvert")
    invt.label = "Invert"
    invt.name = prefix + "Invert"
    invt.location = -200, -150
    invt.hide = True

    math1 = nodes.new("ShaderNodeMath")
    math1.label = "Add"
    math1.name = prefix + "MathAdd"
    math1.operation = 'ADD'
    math1.location = -400, -150
    math1.hide = True

    math2 = nodes.new("ShaderNodeMath")
    math2.label = "Absolute"
    math2.name = prefix + "MathAbs2"
    math2.operation = 'ABSOLUTE'
    math2.location = -600, -50
    math2.hide = True

    math3 = nodes.new("ShaderNodeMath")
    math3.label = "Absolute"
    math3.name = prefix + "MathAbs1"
    math3.operation = 'ABSOLUTE'
    math3.location = -600, 0
    math3.hide = True

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = prefix + "Separate RGB"
    srgb.location = -800, 0
    srgb.hide = True

    tang = nodes.new("ShaderNodeTangent")
    tang.label = "Tangent"
    tang.name = prefix + "Tangent"
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


def make_material_overlay_cycles(name, vcname, ob=None):
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
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = prefix + "Mix Shader"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = prefix + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = prefix + "Diffuse BSDF"
    diff.location = 400, 100

    vrgb = nodes.new("ShaderNodeValToRGB")
    vrgb.label = "ColorRamp"
    vrgb.name = prefix + "ColorRamp"
    vrgb.location = 100, 100

    set_colorramp_preset(vrgb, mat=mat)

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = prefix + "Separate RGB"
    srgb.location = -300, 100

    attr = nodes.new("ShaderNodeAttribute")
    attr.location = -500, 100
    attr.name = prefix + "Attribute"
    attr.attribute_name = vcname
    attr.label = "Attribute"

#     if ob is not None:
#         nnel = nodes.new("ShaderNodeValue")
#         nnel.location = 100, 300
#         nnel.name = prefix + "Value"
#         nnel.label = "Value"
#         driver = nnel.outputs[0].driver_add("default_value")
#         var2 = driver.driver.variables.new()
#         var2.name = "dmin"
#         var2.targets[0].id = ob  #.id_data
#         var2.targets[0].data_path = "scalars[" + name + "].range[0]"
#         var3 = driver.driver.variables.new()
#         var3.name = "dmax"
#         var3.targets[0].id = ob  #.id_data
#         var3.targets[0].data_path = "scalars[" + name + "].range[1]"
#         var1 = driver.driver.variables.new()
#         var1.name = "norm_pos"
#         var1.targets[0].id = mat  # bpy.data.node_groups["Shader Nodetree"]
#         var1.targets[0].data_path = "node_tree.nodes['_ColorRamp'].color_ramp.elements[0].position"
#         driver.driver.expression = "norm_pos * (dmax - dmin) - dmin"

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
    links.new(srgb.outputs["R"], vrgb.inputs["Fac"])
    links.new(attr.outputs["Color"], srgb.inputs["Image"])

    return mat


def make_material_uvoverlay_cycles(name, vcname, img):
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
    prefix = ""

    out = nodes.new("ShaderNodeOutputMaterial")
    out.label = "Material Output"
    out.name = prefix + "Material Output"
    out.location = 800, 0

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = prefix + "Mix Shader"
    mix1.inputs[0].default_value = 0.04
    mix1.location = 600, 0

    glos = nodes.new("ShaderNodeBsdfGlossy")
    glos.label = "Glossy BSDF"
    glos.name = prefix + "Glossy BSDF"
    glos.inputs[1].default_value = 0.15
    glos.distribution = "BECKMANN"
    glos.location = 400, -100

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.label = "Diffuse BSDF"
    diff.name = prefix + "Diffuse BSDF"
    diff.location = 400, 100

    vrgb = nodes.new("ShaderNodeValToRGB")
    vrgb.label = "ColorRamp"
    vrgb.name = prefix + "ColorRamp"
    vrgb.location = 100, 100

    set_colorramp_preset(vrgb, mat=mat, prefix='uv_')

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = prefix + "Separate RGB"
    srgb.location = -300, 100

    itex = nodes.new("ShaderNodeTexImage")
    itex.location = 600, 100
    itex.name = prefix + "Image Texture"
    itex.image = img
    itex.label = "Image texture"

    texc = nodes.new("ShaderNodeTexCoord")
    texc.location = 800, 100
    texc.name = prefix + "Texture Coordinate"
    texc.label = "Texture Coordinate"

    links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(diff.outputs["BSDF"], mix1.inputs[1])
    links.new(vrgb.outputs["Color"], diff.inputs["Color"])
    links.new(srgb.outputs["R"], vrgb.inputs["Fac"])
    links.new(itex.outputs["Color"], srgb.inputs["Image"])
    links.new(texc.outputs["UV"], itex.inputs["Vector"])

    return mat


def make_material_overlaytract_cycles_withgroup(name, img, group):
    """"""

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


def make_material_overlaytract_cycles_group(diffcol, mix=0.04):
    """Create a basic Cycles material.

    The material mixes difffuse, transparent and glossy.
    """

    diffuse = {'colour': diffcol, 'roughness': 0.1}
    glossy = {'colour': (1.0, 1.0, 1.0, 1.0), 'roughness': 0.1}

    scn = bpy.context.scene
    if not scn.render.engine == "CYCLES":
        scn.render.engine = "CYCLES"

    group = bpy.data.node_groups.new("TractOvGroup", "ShaderNodeTree")
    group.inputs.new("NodeSocketColor", "Color")
    group.outputs.new("NodeSocketShader", "Shader")

    nodes = group.nodes
    links = group.links

    nodes.clear()

    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (800, 0)

    mix1 = nodes.new("ShaderNodeMixShader")
    mix1.label = "Mix Shader"
    mix1.name = "Mix Shader"
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
    mix2.label = "Mix Shader"
    mix2.name = "Mix Shader"
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

    elements = vrgb.color_ramp.elements
    for el in elements[1:]:
        elements.remove(el)
    positions = [0.0, 1.0]
    colors = [(1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0)]
    for p in positions[1:]:
        elements.new(p)
    elements.foreach_set("position", positions)
    for i in range(len(colors)):
        setattr(elements[i], "color", colors[i])

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


def set_colorramp_preset(node, cmapname="r2b", mat=None, prefix=''):
    """Set a colourramp node to a preset."""

    tb_ob = tb_utils.active_tb_object()[0]
    scalarslist = tb_ob.scalars

    elements = node.color_ramp.elements

    for el in elements[1:]:
        elements.remove(el)

    if (cmapname == "fscurv") | (mat.name.endswith(".curv")):
        i = 0
        while prefix + scalarslist[i].name != mat.name:
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


def map_to_uv(ob, uvname="", fpath="", img=None):
    """"""

    # need a unique name (same for "Vertex Colors" and "Material")
    # TODO: but maybe not for 'directional'?
    uvs = ob.data.uv_layers
    uvname = tb_utils.check_name(uvname, fpath, checkagainst=uvs)
    materials = bpy.data.materials
    uvname = tb_utils.check_name(uvname, fpath, checkagainst=materials)

    mat = make_material_uvoverlay_cycles(uvname, uvname, img)

    set_materials(ob.data, mat)
    uv = ob.data.uv_textures.new(uvname)
    uv_map = ob.data.uv_layers.active.data
    ob = assign_uv(ob, uv_map)


def assign_uv(ob, uv_map):
    """"""

    me = ob.data
    nverts = len(me.vertices)
    imsize = np.ceil(np.sqrt(nverts))
    for poly in me.polygons:
        for idx in poly.loop_indices:
            vi = ob.data.loops[idx].vertex_index
            uvcoord = divmod(vi, imsize)
            uvcoord = [(uvcoord[1] + 0.5)/imsize, (uvcoord[0] + 0.5)/imsize]
            uv_map[idx].uv = mathutils.Vector(uvcoord)
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
    prefix = ""

    node = nodes.new("ShaderNodeOutputMaterial")
    node.label = "Material Output"
    node.name = prefix + "Material Output"
    node.location = 800, 0

    node = nodes.new("ShaderNodeMixShader")
    node.label = "Mix Shader"
    node.name = prefix + "Mix Shader"
    node.inputs[0].default_value = 0.04
    node.location = 600, 0

    node = nodes.new("ShaderNodeBsdfGlossy")
    node.label = "Glossy BSDF"
    node.name = prefix + "Glossy BSDF"
    node.inputs[1].default_value = 0.15
    node.distribution = "BECKMANN"
    node.location = 400, -100

    node = nodes.new("ShaderNodeBsdfDiffuse")
    node.label = "Diffuse BSDF"
    node.name = prefix + "Diffuse BSDF"
    node.location = 400, 100

    node = nodes.new("ShaderNodeAttribute")
    node.location = 200, 100
    node.name = prefix + "Attribute"
    node.attribute_name = vcname
    node.label = "Attribute"

    links.new(nodes[prefix + "Mix Shader"].outputs["Shader"],
              nodes[prefix + "Material Output"].inputs["Surface"])
    links.new(nodes[prefix + "Glossy BSDF"].outputs["BSDF"],
              nodes[prefix + "Mix Shader"].inputs[2])
    links.new(nodes[prefix + "Diffuse BSDF"].outputs["BSDF"],
              nodes[prefix + "Mix Shader"].inputs[1])
    links.new(nodes[prefix + "Attribute"].outputs["Color"],
              nodes[prefix + "Diffuse BSDF"].inputs["Color"])
    # FIXME: node names will truncate if too long; this will error

    return mat
