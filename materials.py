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

from . import (imports as nb_im,
               utils as nb_ut)


# =========================================================================== #
# material assignment
# =========================================================================== #


def materialise(ob, colourtype='primary6', colourpicker=(1, 1, 1), trans=1):
    """Attach material to an object."""

    if ob is None:
        info = "no object to materialise"
        return info

    scn = bpy.context.scene
    nb = scn.nb

    primary6_colours = [[1, 0, 0], [0, 1, 0], [0, 0, 1],
                        [1, 1, 0], [1, 0, 1], [0, 1, 1]]

    ob.show_transparent = True

    matname = ob.name

    diffcol = [1, 1, 1]
    mix = 0.05
    diff_rn = 0.1

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

    mat = make_material_basic_cycles(matname, diffcol, mix, diff_rn, group)

    link_innode(mat, colourtype)

    set_materials(ob.data, mat)

    info = "material: type=%s; colour=%s" % (colourtype, diffcol)

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

    mats = [mat for mat in me.materials]
    mats.insert(0, mat)
    me.materials.clear()
    for mat in mats:
        me.materials.append(mat)


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
    name = nb_ut.check_name(name, fpath, ca)
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


def CR2BR(mat):
    """Copy Cycles settings to Blender Render material."""

    mat.use_nodes = False

    try:
        rgb = mat.node_tree.nodes["RGB"]
    except KeyError:
        pass
    else:
        mat.diffuse_color = rgb.outputs[0].default_value[0:3]

    try:
        trans = mat.node_tree.nodes["Transparency"]
    except KeyError:
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


def create_vc_overlay_tract(ob, fpath, name="", is_label=False):
    """Create scalar overlay for a tract object."""

    # TODO: implement reading of groups
    nn_scalargroup_data = nb_im.read_tractscalar(fpath)
    groupmin = float('Inf')
    groupmax = -float('Inf')
    scalarranges = []
    for scalar_data in nn_scalargroup_data:
        datamin = float('Inf')
        datamax = -float('Inf')
        for streamline in scalar_data:
            datamin = min(datamin, min(streamline))
            datamax = max(datamax, max(streamline))
        scalarranges.append([datamin, datamax])
        groupmin = min(groupmin, datamin)
        groupmax = max(groupmax, datamax)
    grouprange = groupmax - groupmin
    scalargrouprange = groupmin, groupmax
    scalargroup_data = [[(np.array(streamline) - groupmin) / grouprange
                         for streamline in scalar_data]
                        for scalar_data in nn_scalargroup_data]

    nb_ob = nb_ut.active_nb_object()[0]
    ca = [nb_ob.scalargroups]
    name = nb_ut.check_name(name, fpath, ca)
    sgprops = {"name": name,
               "filepath": fpath,
               "range": scalargrouprange}
    scalargroup = nb_ut.add_item(nb_ob, "scalargroups", sgprops)

    ob.data.use_uv_as_generated = True
    diffcol = [0.0, 0.0, 0.0, 1.0]
    group = make_material_overlaytract_cycles_group(diffcol, mix=0.04,
                                                    nb_ov=scalargroup)

    for j, (scalar, scalarrange) in enumerate(zip(scalargroup_data,
                                                  scalarranges)):
        # TODO: check against all other scalargroups etc
        ca = [sg.scalars for sg in nb_ob.scalargroups]
        tpname = "%s.vol%04d" % (name, j)
        scalarname = nb_ut.check_name(tpname, fpath, ca)
        sprops = {"name": scalarname,
                  "filepath": fpath,
                  "range": scalarrange}
        nb_scalar = nb_ut.add_item(scalargroup, "scalars", sprops)

        for i, (spline, streamline) in enumerate(zip(ob.data.splines, scalar)):

            # TODO: implement name check that checks for the prefix 'name'
            splname = nb_scalar.name + '_spl' + str(i).zfill(8)
            ca = [bpy.data.images, bpy.data.materials]
            splname = nb_ut.check_name(splname, fpath, ca, maxlen=52)

            img = create_overlay_tract_img(splname, streamline)

            # it seems crazy to make a material/image per streamline!
            mat = make_material_overlaytract_cycles_withgroup(splname, img, group)
            ob.data.materials.append(mat)
            spline.material_index = len(ob.data.materials) - 1


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

    timeseries = nb_im.read_surfscalar(fpath)

    timeseries, timeseriesrange = nb_im.normalize_data(timeseries)

    nb_ob = nb_ut.active_nb_object()[0]
    ca = [nb_ob.scalargroups]  # TODO: all other scalargroups etc
    name = nb_ut.check_name(name, fpath, ca)
    texdir = "//uvtex_%s" % name
    props = {"name": name,
             "filepath": fpath,
             "range": timeseriesrange,
             "texdir": texdir}
    scalargroup = nb_ut.add_item(nb_ob, "scalargroups", props)

    vg = set_vertex_group(ob, "%s.volmean" % name,
                          scalars=np.mean(timeseries, axis=0))
    mat = map_to_vertexcolours(ob, scalargroup, [vg])

    if timeseries.shape[0] == 1:
        scalargroup.icon = "FORCE_CHARGE"
    for i, scalars in enumerate(timeseries):
        tpname = "%s.vol%04d" % (name, i)
        vg = set_vertex_group(ob, tpname, scalars=scalars)
        props = {"name": tpname,
                 "filepath": fpath,
                 "range": timeseriesrange}
        nb_ov = nb_ut.add_item(scalargroup, "scalars", props)

    abstexdir = bpy.path.abspath(texdir)
    if os.path.isdir(abstexdir):
        nfiles = len(glob(os.path.join(abstexdir, '*.png')))
        if nfiles == len(scalargroup.scalars):
            load_surface_textures(name, abstexdir,
                                  len(scalargroup.scalars))


def create_vg_annot(ob, fpath, name=""):
    """Import an annotation file to vertex groups.

    TODO: decide what is the best approach:
    reading gifti and converting to freesurfer format (current) or
    have a seperate functions for handling .gii annotations
    (this can be found in commit c3b6d66)
    """

    nb_ob = nb_ut.active_nb_object()[0]
    ca = [nb_ob.labelgroups]  # TODO: all other labelgroups
    groupname = nb_ut.check_name(name, fpath, ca)
    props = {"name": groupname,
             "filepath": fpath}
    labelgroup = nb_ut.add_item(nb_ob, "labelgroups", props)
    mat = make_material_overlay_cycles(groupname, groupname,
                                       ob, labelgroup)
    set_materials(ob.data, mat)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    attr = nodes["Attribute"]
    emit = nodes["Emission"]
    diff = nodes["Diffuse BSDF"]
    links.new(attr.outputs["Color"], diff.inputs["Color"])
    links.new(attr.outputs["Color"], emit.inputs["Color"])
    attr.attribute_name = groupname

    if fpath.endswith('.border'):
        borderlist = nb_im.read_borders(fpath)
        create_polygon_layer_int(ob, borderlist)
        # (for each border?, will be expensive: do one for every file now)
        # this already takes a long time...

        new_mats = []
        for i, border in enumerate(borderlist):

            ca = [ob.data.polygon_layers_int,
                  bpy.data.materials]
            name = nb_ut.check_name(border['name'], "", ca)

            value = i + 1
            diffcol = list(border['rgb']) + [1.0]

            mat = make_material_basic_cycles(name, diffcol, mix=0.05)
            new_mats.append(mat)

            props = {"name": name,
                     "value": value,
                     "colour": diffcol}
            nb_ut.add_item(labelgroup, "labels", props)

        pl = ob.data.polygon_layers_int["pl"]
        set_materials_to_polygonlayers(ob, pl, new_mats)

    else:
        labels, ctab, names = nb_im.read_surfannot(fpath)

        new_vgs = []
        new_mats = []
        for i, labelname in enumerate(names):

            ca = [ob.vertex_groups,
                  bpy.data.materials]
            name = nb_ut.check_name(labelname, "", ca)

            label = np.where(labels == i)[0]
            value = ctab[i, 4]
            diffcol = ctab[i, 0:4]/255

            vg = set_vertex_group(ob, name, label)
            new_vgs.append(vg)

            mat = make_material_basic_cycles(name, diffcol, mix=0.05)
            new_mats.append(mat)

            props = {"name": name,
                     "value": int(value),
                     "colour": diffcol}
            nb_ut.add_item(labelgroup, "labels", props)

        set_materials_to_vertexgroups(ob, new_vgs, new_mats)


def create_border_curves(ob, fpath, name=""):
    """Import an border file and create curves."""

    borderlist = nb_im.read_borders(fpath)

    ca = [bpy.data.objects]
    groupname = nb_ut.check_name(name, fpath, ca)
    bordergroup_ob = bpy.data.objects.new(groupname, object_data=None)
    bpy.context.scene.objects.link(bordergroup_ob)
    bordergroup_ob.parent = ob
    props = {"name": groupname,
             "filepath": fpath}
    nb_ob = nb_ut.active_nb_object()[0]  # FIXME
    bordergroup = nb_ut.add_item(nb_ob, "bordergroups", props)

    for i, border in enumerate(borderlist):

        ca = [bpy.data.objects,
              bpy.data.materials]
        name = nb_ut.check_name(border['name'], "", ca)

        diffcol = list(border['rgb']) + [1.0]
        mat = make_material_basic_cycles(name, diffcol, mix=0.05)

        bevel_depth = 0.5
        bevel_resolution = 10
        iterations = 10
        factor = 0.5

        props = {"name": name,
                 "group": bordergroup.name,
                 "colour": diffcol}
        nb_ut.add_item(bordergroup, "borders", props)

        curve = bpy.data.curves.new(name=name, type='CURVE')
        curve.dimensions = '3D'
        curveob = bpy.data.objects.new(name, curve)
        bpy.context.scene.objects.link(curveob)
        nb_im.make_polyline_ob_vi(curve, ob, border['verts'][:, 0])
        curveob.data.fill_mode = 'FULL'
        curveob.data.bevel_depth = bevel_depth
        curveob.data.bevel_resolution = bevel_resolution
        curveob.parent = bordergroup_ob
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
                # note that this overwrites double entries
                pl.data[poly.index].value = bi


def create_vg_overlay(ob, fpath, name="", is_label=False, trans=1):
    """Create label/scalar overlay from a labelfile.

    Note that a (freesurfer) labelfile can contain scalars.
    If scalars are available and is_label=False (loaded from scalars-menu),
    a scalar-type overlay will be generated.
    """

    label, scalars = nb_im.read_surflabel(fpath, is_label)

    if scalars is not None:
        ca = [ob.vertex_groups,
              ob.data.vertex_colors,
              bpy.data.materials]
        name = nb_ut.check_name(name, fpath, ca)

        vgscalars, scalarrange = nb_im.normalize_data(scalars)

        vg = set_vertex_group(ob, name, label, scalars)

        scalargroup = []
        props = {"name": name,
                 "filepath": fpath,
                 "range": scalarrange}
        nb_ov = nb_ut.add_item(scalargroup, "scalars", props)

        map_to_vertexcolours(ob, nb_ov, [vg], is_label)

    else:
        nb_ob = nb_ut.active_nb_object()[0]
        ca = [nb_ob.labelgroups]  # TODO: checkagainst all other labelgroups
        groupname = nb_ut.check_name(name, fpath, ca)
        props = {"name": name,
                 "filepath": fpath}
        labelgroup = nb_ut.add_item(nb_ob, "labelgroups", props)

        ca = [ob.vertex_groups,
              bpy.data.materials]
        name = nb_ut.check_name(name, fpath, ca)
        vg = set_vertex_group(ob, name, label, scalars)

        values = [label.value for label in labelgroup.labels] or [0]
        value = max(values) + 1
        diffcol = [random.random() for _ in range(3)] + [trans]
        mat = make_material_basic_cycles(name, diffcol, mix=0.05)
        set_materials_to_vertexgroups(ob, [vg], [mat])

        props = {"name": name,
                 "value": value,
                 "colour": diffcol}
        nb_ov = nb_ut.add_item(labelgroup, "labels", props)


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

    ob.vertex_groups.active_index = vg.index

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
    else:
        mat_idxs = []
        for mat in mats:
            ob.data.materials.append(mat)
            mat_idxs.append(len(ob.data.materials) - 1)

        assign_materialslots_to_faces(ob, vgs, mat_idxs)


def assign_materialslots_to_faces(ob, vgs=None, mat_idxs=[]):
    """Assign a material slot to faces in associated with a vertexgroup."""

    vgs_idxs = [g.index for g in vgs]
    me = ob.data
    for poly in me.polygons:
        for vi in poly.vertices:
            allgroups = [g.group for g in me.vertices[vi].groups]
            for vgs_idx, mat_idx in zip(reversed(vgs_idxs), reversed(mat_idxs)):
                if vgs_idx in allgroups:
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


# =========================================================================== #
# mapping vertex weights to vertexcolours
# =========================================================================== #


def map_to_vertexcolours(ob, nb_ov, vgs=None, is_label=False, colourtype=""):
    """Write vertex group weights to a vertex colour attribute.

    A colourbar is prepared for scalar overlays.
    """

    name = nb_ov.name
    mat = make_material_overlay_cycles(name, name, ob, nb_ov)
    set_materials_to_vertexgroups(ob, vgs=None, mats=[mat])

#     set_materials_to_vertexgroups(ob, vgs, [mat])
#
#     vcs = ob.data.vertex_colors
#     vc = vcs.new(name=name)
#     ob.data.vertex_colors.active = vc
#     ob = assign_vc(ob, vc, vgs)

    return mat

def assign_vc(ob, vertexcolours, vgs, labelgroup=[], colour=[0, 0, 0]):
    """Assign RGB values to the vertex_colors attribute.

    TODO: find better ways to handle multiple assignments to vertexgroups
    """

    me = ob.data

    if labelgroup:
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
        W[m] = 1.055 * ( np.power(W[m], (1.0 / 2.4) )) - 0.055
        W[~m] = 12.92 * W[~m]
        C = np.transpose(np.tile(W, [3,1]))

    for poly in me.polygons:
        for idx, vi in zip(poly.loop_indices, poly.vertices):
            vertexcolours.data[idx].color = C[vi]

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


# =========================================================================== #
# voxelvolume texture mapping
# =========================================================================== #

def get_voxmat(name):
    """"""

    mat = bpy.data.materials.new(name)
    mat.type = "SURFACE"
    mat.use_transparency = True
    mat.alpha = 0.
    mat.volume.density = 0.
    mat.volume.reflection = 0.
    mat.use_shadeless = True
    mat.preview_render_type = 'CUBE'
    mat.use_fake_user = True

    return mat


def get_voxtex(mat, texdict, volname, item):
    """Return a textured material for voxeldata."""

    scn = bpy.context.scene

    img = texdict['img']
    dims = texdict['dims']
    texdir = texdict['texdir']
    texformat = texdict['texformat']
    is_overlay = texdict['is_overlay']
    is_label = texdict['is_label']

    tex = bpy.data.textures.new(item.name, 'VOXEL_DATA')
    tex.use_preview_alpha = True
    tex.use_color_ramp = True
    tex.use_fake_user = True
    if texformat == 'STRIP':  # TODO: this should be handled with cycles
        texformat = "IMAGE_SEQUENCE"
    tex.voxel_data.file_format = texformat
    tex.voxel_data.use_still_frame = True
    tex.voxel_data.still_frame = scn.frame_current
    tex.voxel_data.interpolation = 'NEREASTNEIGHBOR'

    if texformat == "IMAGE_SEQUENCE":
        texpath = os.path.join(texdir, texformat, volname, '0000.png')
        img = bpy.data.images.load(bpy.path.abspath(texpath))
        img.name = item.name
        img.source = 'SEQUENCE'
        img.colorspace_settings.name = 'Non-Color'  # TODO: check
        img.reload()
        tex.image_user.frame_duration = dims[2]
        tex.image_user.frame_start = 1
        tex.image_user.frame_offset = 0
        tex.image = img
    elif texformat == "8BIT_RAW":
        tex.voxel_data.filepath = bpy.path.abspath(img.filepath)
        tex.voxel_data.resolution = [int(dim) for dim in dims[:3]]

    if is_label:
        tex.voxel_data.interpolation = "NEREASTNEIGHBOR"
        if len(item.labels) < 33:
            generate_label_ramp(tex, item)
        else:  # too many labels: switching to continuous ramp
            item.colourmap_enum = "jet"
    elif is_overlay:
        item.colourmap_enum = "jet"
    else:
        item.colourmap_enum = "grey"

    return tex


def generate_label_ramp(tex, item):
    """Make a color ramp from labelcollection."""

    cr = tex.color_ramp
    cr.interpolation = 'CONSTANT'
    cre = cr.elements
    maxlabel = max([label.value for label in item.labels])
    step = 1. / maxlabel
    offset = step / 2.
    cre[1].position = item.labels[0].value / maxlabel - offset
    cre[1].color = item.labels[0].colour
    for label in item.labels[1:]:
        pos = label.value / maxlabel - offset
        el = cre.new(pos)
        el.color = label.colour


def load_surface_textures(name, directory, nframes):
    """"""

    try:
        mat = bpy.data.materials[name]
    except KeyError:
        pass
    else:
        absdir = bpy.path.abspath(directory)
        fpath = glob(os.path.join(absdir, '*.png'))[0]
        bpy.data.images.load(fpath, check_existing=False)
        fname = os.path.basename(fpath)
        img = bpy.data.images[fname]
        img.source = 'SEQUENCE'

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        itex = nodes["Image Texture"]
        srgb = nodes["Separate RGB"]
        itex.image_user.use_auto_refresh = True
        itex.image_user.frame_duration = nframes
        itex.image = img
        links.new(itex.outputs["Color"], srgb.inputs["Image"])


# ========================================================================== #
# cycles node generation
# ========================================================================== #


def make_material_basic_cycles(name, diff_col, mix=0.04,
                               diff_rn=0.1, diff_ingroup=None):
    """Create a basic Cycles material.

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
    trans.location = 0, 00

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

    if nb.mode == "scientific":
        links.new(emit.outputs["Emission"], out.inputs["Surface"])
    elif nb.mode == "artistic":
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


def make_nodegroup_rgba(name="RGBAGroup", colour=[1, 1, 1, 1]):
    """Create a nodegroup encapsulating an RGB(A)."""

    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    group.outputs.new("NodeSocketShader", "Color")
    group.outputs.new("NodeSocketShader", "Color")

    nodes = group.nodes
    links = group.links

    nodes.clear()
    prefix = ""

    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (-200, 0)

    rgb = nodes.new("ShaderNodeRGB")
    rgb.label = "RGB"
    rgb.name = prefix + "RGB"
    rgb.outputs[0].default_value = colour
    rgb.location = 0, 0

    links.new(rgba.outputs["Color"], output_node.inputs[0])
    links.new(rgba.outputs["Color"].default_value[3], output_node.inputs[1])

    return group


def make_material_emit_cycles(name, emission):
    """Create a Cycles emitter material for lighting."""

    scn = bpy.context.scene
#     if not scn.render.engine == "CYCLES":
#         scn.render.engine = "CYCLES"

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
#     if not scn.render.engine == "BLENDER_RENDER":
#         scn.render.engine = "BLENDER_RENDER"

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


def make_material_overlay_cycles(name, vcname, ob=None, nb_ov=None, img=None):
    """Create a Cycles material for colourramped vertexcolour rendering."""
    # TODO: transparency?

    scn = bpy.context.scene
    nb = scn.nb
#     if not scn.render.engine == "CYCLES":
#         scn.render.engine = "CYCLES"

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

    if hasattr(nb_ov, 'nn_elements'):
        nb_ov.colourmap_enum = 'jet'
        # calc_nn_elpos(nb_ov, vrgb)

    srgb = nodes.new("ShaderNodeSeparateRGB")
    srgb.label = "Separate RGB"
    srgb.name = prefix + "Separate RGB"
    srgb.location = -300, 100

    attr = nodes.new("ShaderNodeAttribute")
    attr.location = -500, 300
    attr.name = prefix + "Attribute"
    attr.attribute_name = vcname
    attr.label = "Attribute"

    itex = nodes.new("ShaderNodeTexImage")
    itex.location = -500, -100
    if img is not None:
        itex.image = img
    itex.label = "Image Texture"

    tval = nodes.new("ShaderNodeValue")
    tval.label = "Value"
    tval.name = prefix + "Value"
    tval.outputs[0].default_value = 1.0
    tval.location = 400, 300
    # TODO: link this with colorramp through driver?

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

    if nb.mode == "scientific":
        links.new(emit.outputs["Emission"], out.inputs["Surface"])
    elif nb.mode == "artistic":
        links.new(mix1.outputs["Shader"], out.inputs["Surface"])
    links.new(glos.outputs["BSDF"], mix1.inputs[2])
    links.new(diff.outputs["BSDF"], mix1.inputs[1])
    links.new(vrgb.outputs["Color"], emit.inputs["Color"])
    links.new(vrgb.outputs["Color"], diff.inputs["Color"])
    links.new(srgb.outputs["R"], vrgb.inputs["Fac"])
    links.new(attr.outputs["Color"], srgb.inputs["Image"])
    links.new(tval.outputs["Value"], emit.inputs["Strength"])

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


def make_material_overlaytract_cycles_group(diffcol, mix=0.04, nb_ov=None):
    """Create a basic Cycles material.

    The material mixes difffuse, transparent and glossy.
    """

    diffuse = {'colour': diffcol, 'roughness': 0.1}
    glossy = {'colour': (1.0, 1.0, 1.0, 1.0), 'roughness': 0.1}

    scn = bpy.context.scene
#     if not scn.render.engine == "CYCLES":
#         scn.render.engine = "CYCLES"

    group = bpy.data.node_groups.new("TractOvGroup", "ShaderNodeTree")
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

    scn = bpy.context.scene
    nb = scn.nb
#     if not scn.render.engine == "CYCLES":
#         scn.render.engine = "CYCLES"

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


def make_nodegroup_mapframes(name="MapFramesGroup"):
    """Create a nodegroup for mapping MR frames.

    http://blender.stackexchange.com/questions/62110
    """

    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    group.outputs.new("NodeSocketColor", "Vector")
#
#     nodes = group.nodes
#     links = group.links
#
#     nodes.clear()
#     prefix = ""
#
#     output_node = nodes.new("NodeGroupOutput")
#     output_node.location = (-200, 0)
#
#     crgb = nodes.new("ShaderNodeCombineRGB")
#     crgb.label = "Combine RGB"
#     crgb.name = prefix + "Combine RGB"
#     crgb.location = -400, 0
#     crgb.hide = True
#
#     invt = nodes.new("ShaderNodeInvert")
#     invt.label = "Invert"
#     invt.name = prefix + "Invert"
#     invt.location = -600, -150
#     invt.hide = True
#
#     math1 = nodes.new("ShaderNodeMath")
#     math1.label = "Add"
#     math1.name = prefix + "MathAdd"
#     math1.operation = 'ADD'
#     math1.location = -800, -150
#     math1.hide = True
#
#     math2 = nodes.new("ShaderNodeMath")
#     math2.label = "Absolute"
#     math2.name = prefix + "MathAbs2"
#     math2.operation = 'ABSOLUTE'
#     math2.location = -1000, -50
#     math2.hide = True
#
#     math3 = nodes.new("ShaderNodeMath")
#     math3.label = "Absolute"
#     math3.name = prefix + "MathAbs1"
#     math3.operation = 'ABSOLUTE'
#     math3.location = -1000, 0
#     math3.hide = True
#
#     srgb = nodes.new("ShaderNodeSeparateRGB")
#     srgb.label = "Separate RGB"
#     srgb.name = prefix + "Separate RGB"
#     srgb.location = -1200, 0
#     srgb.hide = True
#
#     tang = nodes.new("ShaderNodeTangent")
#     tang.label = "Tangent"
#     tang.name = prefix + "Tangent"
#     tang.direction_type = 'UV_MAP'
#     tang.location = -1400, 0
#
#     links.new(crgb.outputs["Image"], output_node.inputs[0])
#     links.new(invt.outputs["Color"], crgb.inputs[2])
#     links.new(math2.outputs["Value"], crgb.inputs[1])
#     links.new(math3.outputs["Value"], crgb.inputs[0])
#     links.new(math1.outputs["Value"], invt.inputs["Color"])
#     links.new(math2.outputs["Value"], math1.inputs[1])
#     links.new(math3.outputs["Value"], math1.inputs[0])
#     links.new(srgb.outputs["G"], math2.inputs["Value"])
#     links.new(srgb.outputs["R"], math3.inputs["Value"])
#     links.new(tang.outputs["Tangent"], srgb.inputs["Image"])

    return group
