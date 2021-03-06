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


"""The NeuroBlender properties module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements all of NeuroBlender's custom property classes,
as well as there callback and update functions.
"""

import os
import re
from glob import glob

import mathutils

import bpy
from bpy.types import PropertyGroup as pg
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       IntProperty,
                       IntVectorProperty,
                       PointerProperty)
from bpy.app.handlers import persistent

from . import (animations as nb_an,
               materials as nb_ma,
               utils as nb_ut)


# ========================================================================== #
# handler functions
# ========================================================================== #

@persistent
def carvers_handler(dummy):
    """Update carvers."""

    scn = bpy.context.scene
    nb = scn.nb

    def update_object_carvers(nb_ob):
        for carver in nb_ob.carvers:
            for carveob in carver.carveobjects:
                carvers_update(carveob, bpy.context)

    for surf in nb.surfaces:
        update_object_carvers(surf)
    for vvol in nb.voxelvolumes:
        update_object_carvers(vvol)

@persistent
def rendertype_enum_handler(dummy):
    """Set surface or volume rendering for the voxelvolume."""

    scn = bpy.context.scene
    nb = scn.nb

    for vvol in nb.voxelvolumes:
        rendertype_enum_update(vvol, bpy.context)
        for scalargroup in vvol.scalargroups:
            rendertype_enum_update(scalargroup, bpy.context)
        for labelgroup in vvol.labelgroups:
            rendertype_enum_update(labelgroup, bpy.context)


@persistent
def index_scalars_handler(dummy):
    """Update scalar overlays."""

    scn = bpy.context.scene
    nb = scn.nb

    for anim in nb.animations:
        if anim.animationtype == "timeseries":
            sg = scn.path_resolve(anim.nb_object_data_path)
            index_scalars_update_func(group=sg)


@persistent
def init_settings_handler(dummy):
    """Force update on NeuroBlender settings."""

    scn = bpy.context.scene
    nb = scn.nb

    nb.settingprops.projectdir = nb.settingprops.projectdir
    nb.settingprops.esp_path = nb.settingprops.esp_path
    nb.settingprops.mode = nb.settingprops.mode
    nb.settingprops.engine = nb.settingprops.engine
    nb.settingprops.texformat = nb.settingprops.texformat
    nb.settingprops.texmethod = nb.settingprops.texmethod
    nb.settingprops.uv_resolution = nb.settingprops.uv_resolution
    nb.settingprops.advanced = nb.settingprops.advanced
    nb.settingprops.verbose = nb.settingprops.verbose
    nb.settingprops.goboxy = nb.settingprops.goboxy
    nb.settingprops.switches = nb.settingprops.switches


# ========================================================================== #
# update and callback functions: settings
# ========================================================================== #


def engine_update(self, context):
    """Update materials when switching between engines."""

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        mat.use_nodes = nb.settingprops.engine == "CYCLES"
        if nb.settingprops.engine.startswith("BLENDER"):
            nb_ma.CR2BR(mat)
        else:
            nb_ma.BR2CR(mat)

    scn.render.engine = nb.settingprops.engine
    # TODO: handle lights


def esp_path_update(self, context):
    """Add external site-packages path to sys.path."""

    nb_ut.add_path(self.esp_path)


def mode_enum_update(self, context):
    """Perform actions for updating mode."""

    # TODO: switch colourbars
    # TODO: general update of this functionality

    def switch_mode_preset(lights, tables, newmode, cam_view):
        """Toggle rendering of lights and table."""

        for light in lights:
            light.hide = newmode == "scientific"
            light.hide_render = newmode == "scientific"
        for table in tables:
            state = (cam_view[2] < 0) | (newmode == "scientific")
            table.hide = state
            table.hide_render = state

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        nb_ma.switch_mode_mat(mat, self.mode)

    try:
        nb_preset = nb.presets[self.index_presets]
        nb_cam = nb_preset.cameras[nb_preset.index_cameras]
        light_obs = [bpy.data.objects.get(light.name)
                     for light in nb_preset.lights]
        table_obs = [bpy.data.objects.get(table.name)
                     for table in nb_preset.tables]
    except:
        pass
    else:
        switch_mode_preset(light_obs, table_obs,
                           nb.settingprops.mode,
                           nb_cam.cam_view)


def managecmap_update(self, context):
    """Generate/delete dummy objects to manage colour maps."""

    scn = context.scene
    nb = scn.nb

    def gen_dummies(name="manage_colourmaps"):

        ivv = bpy.types.NB_OT_import_voxelvolumes
        cube = ivv.voxelvolume_box_ob(name, [2, 2, 2])
        cube.hide = cube.hide_render = True
        bpy.data.materials.new(name)
        mat = bpy.data.materials.get(name)
        mat.volume.density = 0

        bpy.data.textures.new(name, type='DISTORTED_NOISE')
        tex = bpy.data.textures.get(name)
        tex.use_preview_alpha = True
        tex.use_color_ramp = True

        texslot = mat.texture_slots.add()
        texslot.texture = tex

        texslot.use_map_density = True
        texslot.texture_coords = 'ORCO'
        texslot.use_map_emission = True

        cube.data.materials.append(mat)

    def del_dummies(name="manage_colourmaps"):

        tex = bpy.data.textures.get(name)
        bpy.data.textures.remove(tex)
        mat = bpy.data.materials.get(name)
        bpy.data.materials.remove(mat)
        me = bpy.data.meshes.get(name)
        bpy.data.meshes.remove(me)

    name = "manage_colourmaps"

    if bpy.data.objects.get(name):
        del_dummies(name)
    else:
        gen_dummies(name)

        # load preset
        cr_parentpath = "bpy.data.textures['{}']".format(name)
        nb.cr_path = '{}.color_ramp'.format(cr_parentpath)
        preset_class = getattr(bpy.types, "NB_MT_colourmap_presets")
        preset_class.bl_label = bpy.path.display_name("Grey")


# ========================================================================== #
# update and callback functions: animations
# ========================================================================== #


def campaths_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(cp.name, cp.name, "List the camera paths", i)
             for i, cp in enumerate(nb.campaths)]
    if not items:
        items = [("no_camerapaths", "No camera trajectories found", "", 0)]

    return items


def campathtype_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [("Circular", "Circular",
              "Circular trajectory from camera position", 0),
             ("Create", "Create",
              "Create a path from camera positions", 1)]
    if self.anim_tract:
        items += [("Streamline", "Streamline",
                   "Curvilinear trajectory from a streamline", 2)]
    if self.anim_curve:
        items += [("Select", "Select",
                   "Curvilinear trajectory from curve", 3)]

    return items


def curves_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    campaths = [cp.name for cp in nb.campaths]
    tracts = [tract.name for tract in nb.tracts]
    items = [(cu.name, cu.name, "List the curves", i)
             for i, cu in enumerate(bpy.data.curves)
             if ((cu.name not in campaths) and
                 (cu.name not in tracts))]
    if not items:
        items = [("no_curves", "No curves found", "No curves found", 0)]

    return items


def trackobject_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = [("None", "None", "None", 0)]
    items += [(ob.name, ob.name, "List all objects", i+1)
              for i, ob in enumerate(bpy.data.objects)]

    return items


def anim_nb_object_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    if self.animationtype == 'carver':
        items = [(cob.path_from_id(),
                  cob.name,
                  "List all carveobjects")
                 for nb_coll in [nb.surfaces, nb.voxelvolumes]
                 for nb_ob in nb_coll
                 for carver in nb_ob.carvers
                 for cob in carver.carveobjects]
        items += [(tract.path_from_id(),
                   tract.name,
                   "List all carveobjects")
                  for tract in nb.tracts]
        if not items:
            items = [("no_carveobjects", "No carveobjects found", "")]

    if self.animationtype == 'timeseries':
        items = [(sg.path_from_id(),
                  '{}.{}'.format(nb_ob.name, sg.name),
                  "List all timeseries")
                 for nb_coll in [nb.tracts, nb.surfaces, nb.voxelvolumes]
                 for nb_ob in nb_coll
                 for sg in nb_ob.scalargroups
                 if len(sg.scalars) > 1]
        if not items:
            items = [("no_timeseries", "No timeseries found", "")]

#     if self.animationtype == 'grow':
#         items = [(nb_ob.path_from_id(),
#                   '{}'.format(nb_ob.name),
#                   "List all objects")
#                  for nb_coll in [nb.tracts, nb.surfaces, nb.voxelvolumes]
#                  for nb_ob in nb_coll]
#         if not items:
#             items = [("no_objects", "No objects found", "")]

    if self.animationtype == 'morph':
        items = [(nb_ob.path_from_id(),
                  '{}'.format(nb_ob.name),
                  "List all objects")
                 for nb_coll in [nb.surfaces]
                 for nb_ob in nb_coll]
        if not items:
            items = [("no_objects", "No objects found", "")]

    return items


def anim_nb_target_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    if self.animationtype == 'morph':
        items = [(nb_ob.path_from_id(),
                  '{}'.format(nb_ob.name),
                  "List all objects")
                 for nb_coll in [nb.surfaces]
                 for nb_ob in nb_coll]
        items += [('from_point', "From point", "From point")]

        if not items:
            items = [("no_objects", "No objects found", "")]

    return items


def timings_enum_update(self, context):
    """Update the animation timings."""

    scn = context.scene
    nb = scn.nb

    if self.animationtype == "camerapath":
        nb_preset = nb.presets[nb.index_presets]
        nb_cam = nb_preset.cameras[nb_preset.index_cameras]
        cam = bpy.data.objects[nb_cam.name]
        acp = bpy.types.NB_OT_animate_camerapath
        # change the eval time keyframes on the new campath
        acp.clear_CP_evaltime(self)
        acp.animate_campath(self)

        # redo the keyframing of the cam constraints
        cam_anims = [anim for anim in nb.animations
                     if ((anim.animationtype == "camerapath") &
                         (anim.campaths_enum != "no_camerapaths") &
                         (anim.is_rendered))]
        acp.clear_CP_followpath(self)
        cns = cam.constraints[self.cnsname]
        acp.animate_camera(self, cns=cns)
        acp.update_cam_constraints(cam, cam_anims)

        nb_ut.validate_anims_campath(nb.animations)

    elif self.animationtype == "carver":
        aca = bpy.types.NB_OT_animate_carver
        aca.animate(self)

    elif self.animationtype == "timeseries":
        ats = bpy.types.NB_OT_animate_timeseries
        ats.animate(self)

    elif self.animationtype == "morph":
        amo = bpy.types.NB_OT_animate_morph
        amo.update_fcurve(self)


def direction_toggle_update(self, context):
    """Update the direction of animation on a curve."""

    scn = context.scene
    nb = scn.nb

    if self.animationtype == "camerapath":
        try:
            campath = bpy.data.objects[self.campaths_enum]
        except KeyError:
            pass
        else:
            animdata = campath.data.animation_data
            fcu = animdata.action.fcurves.find("eval_time")
            mod = fcu.modifiers[0]  # FIXME: this is sloppy
            intercept, slope, _ = nb_an.calculate_coefficients(campath, self)
            mod.coefficients = (intercept, slope)

    elif self.animationtype == "carver":
        aca = bpy.types.NB_OT_animate_carver
        aca.animate(self)

    elif self.animationtype == "timeseries":
        ats = bpy.types.NB_OT_animate_timeseries
        ats.animate(self)

    elif self.animationtype == "morph":
        amo = bpy.types.NB_OT_animate_morph
        amo.update_fcurve(self)


def campaths_enum_update(self, context):
    """Update the camera path."""

    scn = context.scene
    nb = scn.nb

    if not nb_ut.validate_campath(self.campaths_enum):
        return

    acp = bpy.types.NB_OT_animate_camerapath
    # change the eval time keyframes on the new campath
    acp.clear_CP_evaltime(self)
    acp.animate_campath(self)
    # change the campath on the camera constraint
    try:
        cam = bpy.data.objects[self.camera]
    except KeyError:
        return
    try:
        cns = cam.constraints[self.cnsname]
    except KeyError:
        acp.animate_camera(self)
    else:
        cns.target = bpy.data.objects.get(self.campaths_enum)

    anims = acp.select_animations(nb.animations, self.camera)
    nb_ut.validate_anims_campath(anims)


def tracktype_enum_update(self, context):
    """Update the camera path constraints."""

    scn = context.scene
    nb = scn.nb

    nb_preset = nb.presets[nb.index_presets]
    cam = bpy.data.objects[self.camera]

    cam_anims = [anim for anim in nb.animations
                 if ((anim.animationtype == "camerapath") &
                     (anim.is_rendered) &
                     (anim.camera == self.camera))]

    anim_blocks = [[anim.anim_block[0], anim.anim_block[1]]
                   for anim in cam_anims]

    timeline = nb_an.generate_timeline(scn, cam_anims, anim_blocks)
    cnsTT = cam.constraints["TrackToObject"]
    nb_an.restrict_incluence_timeline(scn, cnsTT, timeline, group="TrackTo")

    # TODO: if not yet executed/exists
    cns = cam.constraints[self.cnsname]
    cns.use_curve_follow = self.tracktype == "TrackPath"
    if self.tracktype == 'TrackPath':
        cns.forward_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
    else:
        cns.forward_axis = 'TRACK_NEGATIVE_Y'
        cns.up_axis = 'UP_Z'


def trackobject_enum_update(self, context):
    """Update the camera."""

    # TODO: evaluate against animations
    scn = context.scene
    nb = scn.nb

    cam = bpy.data.objects[self.name]
    cns = cam.constraints["TrackToObject"]
    if self.trackobject == "None":
        cns.mute = True
    else:
        try:
            cns.mute = False
            cns.target = bpy.data.objects[self.trackobject]
        except KeyError:
            infostring = "Object {} not found: disabling tracking"
            print(infostring.format(self.trackobject))


def anim_update(self, context):
    """Update the animation."""

    if self.animationtype != 'camerapath':  # handled differently for now
        cls = eval('bpy.types.NB_OT_animate_{}'.format(self.animationtype))
        cls.animate(self)


# ========================================================================== #
# update and callback functions: scene presets
# ========================================================================== #


def index_presets_update(self, context):
    """Update to a different preset."""

    scn = context.scene
    nb = scn.nb

    try:
        preset = self.presets[self.index_presets]
    except IndexError:
        pass
    else:
        index_cameras_update(preset, context)
        for layer in range(10, 20):
            scn.layers[layer] = (layer == preset.layer)


def cam_view_enum_XX_update(self, context):
    """Set the camview property from enum options."""

    scn = context.scene
    nb = scn.nb

    lud = {'C': 0,
           'R': 1, 'L': -1,
           'A': 1, 'P': -1,
           'S': 1, 'I': -1}

    LR = lud[self.cam_view_enum_LR]
    AP = lud[self.cam_view_enum_AP]
    IS = lud[self.cam_view_enum_IS]

    cv_unit = mathutils.Vector([LR, AP, IS]).normalized()

    self.cam_view = list(cv_unit * self.cam_distance)

    cam = bpy.data.objects[self.name]
    cam.location = self.cam_view


def light_update(self, context):
    """Update light."""

    scn = context.scene
    nb = scn.nb

    # on creation, not all properties have been set yet
    # FIXME: find a less ugly approach and generalize to all update functions
    if self.name:
        light_ob = bpy.data.objects[self.name]
        if self.is_rendered:
            light_ob.hide = not self.is_rendered
            light_ob.hide_render = not self.is_rendered

        light = bpy.data.lamps[self.name]
        if self.type:
            light.type = self.type

        if self.strength:
            if scn.render.engine == "CYCLES":
                light.use_nodes = True
                node = light.node_tree.nodes["Emission"]
                node.inputs[1].default_value = self.strength
            elif scn.render.engine == "BLENDER_RENDER":
                light.energy = self.strength


def table_update(self, context):
    """Update table."""

    scn = context.scene
    nb = scn.nb

    table = bpy.data.objects[self.name]

    table.hide = not self.is_rendered
    table.hide_render = not self.is_rendered


def index_cameras_update(self, context):
    """Update the scene camera."""

    try:
        nb_cam = self.cameras[self.index_cameras]
        cam_ob = bpy.data.objects[nb_cam.name]
    except (KeyError, IndexError):
        pass
    else:
        bpy.context.scene.camera = cam_ob


# ========================================================================== #
# update and callback functions: overlays
# ========================================================================== #


def overlay_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = []
    items.append(("scalargroups", "scalars",
                  "List the scalar overlays", 0))
    items.append(("labelgroups", "labels",
                  "List the label overlays", 1))
    if self.objecttype == 'surfaces':
        items.append(("bordergroups", "borders",
                      "List the border overlays", 2))

    return items


def index_scalars_update(self, context):
    """Switch views on updating scalar index."""

    try:
        pg_sc1 = bpy.types.TractProperties
        pg_sc2 = bpy.types.SurfaceProperties
        pg_sc3 = bpy.types.VoxelvolumeProperties
    except AttributeError:
        pg_sc1 = pg.bl_rna_get_subclass_py("TractProperties")
        pg_sc2 = pg.bl_rna_get_subclass_py("SurfaceProperties")
        pg_sc3 = pg.bl_rna_get_subclass_py("VoxelvolumeProperties")
    if isinstance(self, (pg_sc1, pg_sc2, pg_sc3)):
        try:
            sg = self.scalargroups[self.index_scalargroups]
        except IndexError:
            pass
        else:
            index_scalars_update_func(sg)
    else:
        sg = self
        index_scalars_update_func(sg)


def index_scalars_update_func(group=None):
    """Switch views on updating overlay index."""

    scn = bpy.context.scene
    nb = scn.nb

    if group is None:
        group = nb_ut.active_nb_overlay()[0]

    nb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    nb_ob = scn.path_resolve(nb_ob_path)
    ob = bpy.data.objects[nb_ob.name]

    try:
        scalar = group.scalars[group.index_scalars]
    except IndexError:
        # prevents setting index too high in 'COMPACT' uilist mode
        group.index_scalars = len(group.scalars) - 1
    else:

        try:
            pg_sc1 = bpy.types.TractProperties
            pg_sc2 = bpy.types.SurfaceProperties
            pg_sc3 = bpy.types.VoxelvolumeProperties
            pg_sc4 = bpy.types.ScalarGroupProperties
        except AttributeError:
            pg_sc1 = pg.bl_rna_get_subclass_py("TractProperties")
            pg_sc2 = pg.bl_rna_get_subclass_py("SurfaceProperties")
            pg_sc3 = pg.bl_rna_get_subclass_py("VoxelvolumeProperties")
            pg_sc4 = pg.bl_rna_get_subclass_py("ScalarGroupProperties")

        if isinstance(nb_ob, pg_sc1):
            disable_tract_overlay(ob, ob.data.splines)
            render_tracts_scalargroup(group, ob)

        elif isinstance(nb_ob, pg_sc2):

            vg_idx = ob.vertex_groups.find(scalar.name)
            ob.vertex_groups.active_index = vg_idx

            mat = bpy.data.materials[group.name]

            # update Image Sequence Texture index
            itex = mat.node_tree.nodes["Image Texture"]
            offset = group.index_scalars - scn.frame_current
            itex.image_user.frame_offset = offset

            # update Vertex Color attribute
            vcname = scalar.name
            vc_idx = ob.data.vertex_colors.find(vcname)
            if vc_idx == -1:
                vcname = group.name + '.volmean'
                vc_idx = ob.data.vertex_colors.find(vcname)
            if vc_idx > -1:
                ob.data.vertex_colors.active_index = vc_idx
                for vc in ob.data.vertex_colors:
                    vc.active_render = vc.name == vcname
                attr = mat.node_tree.nodes["Attribute"]
                attr.attribute_name = vcname

        # FIXME: used texture slots
        elif isinstance(nb_ob, pg_sc3):
            index_scalars_update_vvolscalar_func(group, scalar,
                                                 nb.settingprops.texmethod)


def index_scalars_update_vvolscalar_func(group, scalar, method=1):
    """Switch views on updating overlay index."""

    if method == 1:  # simple filepath switching

        try:
            img = bpy.data.images[group.name]
        except KeyError:
            pass
        else:
            # this reloads the sequence/updates the viewport
            try:
                tex = bpy.data.textures[group.name]
            except KeyError:
                pass
            else:
                img.filepath = scalar.filepath
                tex.voxel_data.file_format = group.texformat

    elif method == 2:

        props = ("density_factor", "emission_factor", "emission_color_factor",
                 "emit_factor", "diffuse_color_factor", "alpha_factor")

        for sc in group.scalars:
            mat = bpy.data.materials[sc.matname]
            ts = mat.texture_slots[sc.tex_idx]
            ts.use = True
            for prop in props:
                exec('ts.%s = 0' % prop)

        mat = bpy.data.materials[scalar.matname]
        ts = mat.texture_slots[scalar.tex_idx]
        for prop in props:
            exec('ts.%s = 1' % prop)

    elif method == 3:
        mat = bpy.data.materials[group.name]
        tss = [(i, ts) for i, ts in enumerate(mat.texture_slots)
               if ts is not None]
        props = ("density_factor", "emission_factor", "emission_color_factor",
                 "emit_factor", "diffuse_color_factor", "alpha_factor")
        for i, ts in tss:
            ts.use = group.index_scalars == i
            for prop in props:
                exec('ts.%s = 1' % prop)

    elif method == 4:  # simple texture switching in slot 0
        try:
            mat = bpy.data.materials[scalar.matname]
            tex = bpy.data.textures[scalar.texname]
        except:
            pass
        else:
            mat.texture_slots[0].texture = tex


def index_labels_update(self, context):
    """Switch views on updating label index."""

    try:
        pg_sc1 = bpy.types.TractProperties
        pg_sc2 = bpy.types.SurfaceProperties
        pg_sc3 = bpy.types.VoxelvolumeProperties
    except AttributeError:
        pg_sc1 = pg.bl_rna_get_subclass_py("TractProperties")
        pg_sc2 = pg.bl_rna_get_subclass_py("SurfaceProperties")
        pg_sc3 = pg.bl_rna_get_subclass_py("VoxelvolumeProperties")
    if isinstance(self, (pg_sc1, pg_sc2, pg_sc3)):
        try:
            lg = self.labelgroups[self.index_labelgroups]
        except IndexError:
            pass
        else:
            index_labels_update_func(lg)
    else:
        lg = self
        index_labels_update_func(lg)


def index_labels_update_func(group=None):
    """Switch views on updating overlay index."""

    scn = bpy.context.scene
    nb = scn.nb

    nb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    nb_ob = scn.path_resolve(nb_ob_path)
    ob = bpy.data.objects[nb_ob.name]

    if group is None:
        group = nb_ut.active_nb_overlay()[0]

    try:
        label = group.labels[group.index_labels]
    except IndexError:
        pass
    else:
        name = label.name
        try:
            pg_sc = bpy.types.SurfaceProperties
        except AttributeError:
            pg_sc = pg.bl_rna_get_subclass_py("SurfaceProperties")
        if isinstance(nb_ob, pg_sc):
            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx


# ========================================================================== #
# update and callback functions: base geometry
# ========================================================================== #


def tracts_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(tract.name, tract.name, "List the tracts", i)
             for i, tract in enumerate(nb.tracts)]
    if not items:
        items = [("no_tracts", "No tracts loaded", "No tracts loaded", 0)]

    return items


def surfaces_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(surface.name, surface.name, "List the surfaces", i)
             for i, surface in enumerate(nb.surfaces)]

    return items


def voxelvolumes_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(vvol.name, vvol.name, "List the voxelvolumes", i)
             for i, vvol in enumerate(nb.voxelvolumes)]

    return items


def sphere_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [("Select", "Select from file",
              "Select file to unwrap without importing sphere", 0)]
    items += [(surface.name, surface.name, "List the surfaces", i+1)
              for i, surface in enumerate(nb.surfaces)]

    return items


def sformfile_update(self, context):
    """Set the sform transformation matrix for the object."""

    try:
        ob = bpy.data.objects[self.name]
    except:
        pass
    else:
        sformfile = bpy.path.abspath(self.sformfile)
        affine = nb_ut.read_affine_matrix(sformfile)
        ob.matrix_world = affine


def carvers_update(self, context):
    """Set scaling, positions and rotations for the carveobject."""

    scn = context.scene
    nb = scn.nb

    ob = bpy.data.objects.get(self.name, [])
    try:
        pg_sc = bpy.types.CarveObjectProperties
    except AttributeError:
        pg_sc = pg.bl_rna_get_subclass_py("CarveObjectProperties")
    if ob and isinstance(self, pg_sc):
        ob.scale = self.slicethickness
        # TODO: calculate position regarding the slicethickness
        ob.location = self.sliceposition
        ob.rotation_euler = self.sliceangle


# ========================================================================== #
# update and callback functions: general
# ========================================================================== #


def name_update(self, context):  # FIXME! there's no name checks!
    """Update the name of a NeuroBlender collection item.

    TODO: fcurve data paths
    """

    scn = context.scene
    nb = scn.nb

    def rename_voxelvolume(vvol):  # FIXME: update for carver
        colls = [bpy.data.objects,
                 bpy.data.meshes]
        rename_group(self, bpy.data.materials)
        rename_group(self, bpy.data.textures)
        rename_group(self, bpy.data.images)

        return colls

    def rename_group(coll, group):
        for item in group:
            if item.name.startswith(coll.name_mem):
#                 newname = item.name.replace(coll.name_mem, coll.name)
                item_split = item.name.split('.')
                # FIXME: there can be multiple dots in name
                if len(item_split) > 1:
                    newname = '.'.join([coll.name, item_split[-1]])
                else:
                    newname = coll.name
                item.name = newname

    dp_split = re.findall(r"[\w']+", self.path_from_id())
    colltype = dp_split[-2]

    if colltype == "tracts":
        # TODO: rename scalargroups, (node_groups, textures (images)), labelgroups (items)
        colls = [bpy.data.objects,
                 bpy.data.curves]
        rename_group(self, bpy.data.materials)

    elif colltype == "surfaces":
        # NOTE/TODO: ref to sphere
        # TODO: rename carvers on surface rename
        colls = [bpy.data.objects,
                 bpy.data.meshes]
        rename_group(self, bpy.data.materials)

    elif colltype == "voxelvolumes":
        # TODO: rename carvers on voxelvolume rename
        colls = rename_voxelvolume(self)

    elif colltype == "scalargroups":
        parent = '.'.join(self.path_from_id().split('.')[:-1])
        parent_coll = eval(parent)
        parent_ob = bpy.data.objects[parent_coll.name]
        if parent.startswith("nb.tracts"):
            # FIXME: make sure collection name and matnames agree!
            rename_group(self, bpy.data.materials)
            colls = []
        elif parent.startswith("nb.surfaces"):
            rename_group(self, parent_ob.vertex_groups)
            colls = [bpy.data.materials]
        elif parent.startswith("nb.voxelvolumes"):
            colls = rename_voxelvolume(self)
        rename_group(self, self.scalars)

    elif colltype == "labelgroups":
        parent = '.'.join(self.path_from_id().split('.')[:-1])
        if parent.startswith("nb.tracts"):
            colls = []
#             rename_group(self, bpy.data.materials)
#             rename_group(self, self.labels)  # FIXME: causes recursion
        elif parent.startswith("nb.surfaces"):
            colls = [bpy.data.materials]
        elif parent.startswith("nb.voxelvolumes"):
            colls = rename_voxelvolume(self)

    elif colltype == "bordergroups":
        colls = [bpy.data.objects]

    elif colltype == "scalars":
        colls = []  # irrelevant: name not referenced

    elif colltype == "labels":
        parent = '.'.join(self.path_from_id().split('.')[:-2])
        parent_coll = eval(parent)
        parent_ob = bpy.data.objects[parent_coll.name]
        if parent.startswith("nb.tracts"):
            colls = []  # N/A
        elif parent.startswith("nb.surfaces"):
            vg = parent_ob.vertex_groups.get(self.name_mem)
            vg.name = self.name
            colls = [bpy.data.materials]
        elif parent.startswith("nb.voxelvolumes"):
            colls = []  # irrelevant: name not referenced

    elif colltype == "borders":
        colls = [bpy.data.objects,
                 bpy.data.curves,
                 bpy.data.materials]

    elif colltype == "presets":  # TODO: camera data
        colls = [bpy.data.objects]

    elif colltype == "cameras":
        colls = [bpy.data.objects]  # animations?

    elif colltype == "lights":
        colls = [bpy.data.objects,
                 bpy.data.lamps]

    elif colltype == "tables":  # not implemented via Panels
        colls = [bpy.data.objects,
                 bpy.data.meshes,
                 bpy.data.materials]

    elif colltype == "lights":
        colls = [bpy.data.objects,
                 bpy.data.lamps]

    elif colltype == "animations":
        if self.animationtype == "camerapath":
            cam = bpy.data.objects[self.camera]
            cns = cam.constraints.get(self.cnsname)
            if cns is not None:
                cnsname = "FollowPath_{}".format(self.name)
                self.cnsname = cns.name = cnsname
        colls = []  # TODO

    elif colltype == "campaths":  # not implemented via Panels
        colls = [bpy.data.objects,
                 bpy.data.curves]  # FollowPath constraints

    elif colltype == "carvers":  # TODO: self.carveobjects + mods
        colls = [bpy.data.objects,
                 bpy.data.meshes,
                 bpy.data.groups]

    elif colltype == "carveobjects":

        carveob = bpy.data.objects[self.name_mem]
        carverob = carveob.parent
        mod = carverob.modifiers.get(self.name_mem)
        mod.name = self.name
        colls = [bpy.data.objects,
                 bpy.data.meshes]

    else:
        colls = []

    for coll in colls:
        coll[self.name_mem].name = self.name

    self.name_mem = self.name


# ========================================================================== #
# update and callback functions: materials
# ========================================================================== #


def material_update(self, context):
    """Assign a new preset material to the object."""

    scn = context.scene
    nb = scn.nb

    try:
        mat = bpy.data.materials[self.name]
    except KeyError:
        pass
    else:
        if nb.settingprops.engine.startswith("BLENDER"):
            nb_ma.CR2BR(mat)


def material_enum_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    nb_ma.link_innode(mat, self.colourtype)


def rendertype_enum_update(self, context):
    """Set surface or volume rendering for the voxelvolume."""

    try:
        mat = bpy.data.materials[self.name]
    except KeyError:
        pass
    else:
        tc = {'SURFACE': 'ORCO', 'VOLUME': 'OBJECT'}
        mat.type = self.rendertype
        for ts in mat.texture_slots:
            if ts is not None:
                ts.texture_coords = tc[self.rendertype]


def colourmap_enum_callback(self, context):
    """Populate the enum based on available options."""

    def order_cmaps(mapnames, pref_order):
        """Order a list starting with with a prefered ordering."""

        mapnames_ordered = []
        for mapname in pref_order:
            if mapname in mapnames:
                mapnames_ordered.append(mapname)
                mapnames.pop(mapnames.index(mapname))
        if mapnames:
            mapnames_ordered += mapnames

        return mapnames_ordered

    cmap_dir = os.path.join("presets", "neuroblender_colourmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    files = glob(os.path.join(preset_path, '*.py'))

    mapnames = [os.path.splitext(os.path.basename(f))[0]
                for i, f in enumerate(files)]

    pref_order = ["grey", "jet", "hsv", "hot", "cool",
                  "spring", "summer", "autumn", "winter",
                  "parula"]
    mapnames = order_cmaps(mapnames, pref_order)

    items = []
    for i, mapname in enumerate(mapnames):
        displayname = bpy.path.display_name(mapname)
        items.append((mapname, displayname, "", i))

    return items


def colourmap_enum_update(self, context):
    """Assign a new colourmap to the object."""

    scn = context.scene
    nb = scn.nb

    if self.path_from_id().startswith("nb.tracts"):
        ngname = "TractOvGroup.{}".format(self.name)
        ng = bpy.data.node_groups.get(ngname)
        cr = ng.nodes["ColorRamp"].color_ramp
        ng_path = 'bpy.data.node_groups["{}"]'.format(ngname)
        cr_parentpath = '{}.nodes["ColorRamp"]'.format(ng_path)
    elif self.path_from_id().startswith("nb.surfaces"):
        nt = bpy.data.materials[self.name].node_tree
        cr = nt.nodes["ColorRamp"].color_ramp
        nt_path = 'bpy.data.materials["{}"].node_tree'.format(self.name)
        cr_parentpath = '{}.nodes["ColorRamp"]'.format(nt_path)
    elif self.path_from_id().startswith("nb.voxelvolumes"):
        cr = bpy.data.textures[self.name].color_ramp
        cr_parentpath = 'bpy.data.textures["{}"]'.format(self.name)

    colourmap = self.colourmap_enum

    # load preset
    cr_path = '{}.color_ramp'.format(cr_parentpath)
    nb.cr_path = cr_path
    menu_idname = "NB_MT_colourmap_presets"

    cmap_dir = os.path.join("presets", "neuroblender_colourmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    filepath = os.path.join(preset_path, '{}.py'.format(colourmap))

    bpy.ops.script.execute_preset_cr(filepath=filepath,
                                     menu_idname=menu_idname,
                                     cr_path=cr_path)


def texture_directory_update(self, context):
    """Update the texture."""

    if "surfaces" in self.path_from_id():
        nb_ma.load_surface_textures(self.name, self.texdir, len(self.scalars))
    elif "voxelvolumes" in self.path_from_id():
        pass  # TODO


def mat_is_yoked_bool_update(self, context):
    """Add or remove drivers linking overlay's materials."""

    pass
#     nb_ob = nb_utils.active_nb_object()[0]
#     for prop in ['slicethickness', 'sliceposition', 'sliceangle']:
#         for idx in range(0, 3):
#             if self.is_yoked:
#                 nb_imp.voxelvolume_slice_drivers_yoke(nb_ob, self, prop, idx)
#             else:
#                 self.driver_remove(prop, idx)


def carvers_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    try:
        self.carvers
    except:
        items = []
    else:
        items = [(carver.name, carver.name, "List the carvers", i)
                 for i, carver in enumerate(self.carvers)]

    return items


def carveobjects_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    try:
        self.objects[self.index_objects]
    except:
        items = []
    else:
        items = [(carveob.name, carveob.name, "List the carve objects", i+1)
                 for i, carveob in enumerate(self.objects)]

    return items


def carveobject_is_rendered_update(self, context):
    """Update the render status of the boolean modifier."""

    scn = context.scene
    nb = scn.nb

    carveob = bpy.data.objects.get(self.name)
    carverob = carveob.parent

    mod = carverob.modifiers.get(carveob.name)
    mod.show_render = mod.show_viewport = self.is_rendered


def disable_tract_overlay(ob, coll=[]):
    """Remove all materials but the first."""

    for _ in range(1, len(ob.data.materials)):
        ob.data.materials.pop(1)

    for item in coll:
        item.material_index = 0


def render_tracts_scalargroup(scalargroup, ob):
    """Enable tract scalargroup materials."""

    scalar = scalargroup.scalars[scalargroup.index_scalars]
    splformat = '{}.'.format(scalar.name) + scalargroup.spline_postfix
    for i, spl in enumerate(ob.data.splines):
        mat = bpy.data.materials[splformat.format(i)]
        ob.data.materials.append(mat)
        spl.material_index = i + 1


def render_tracts_labelgroup(labelgroup, ob):
    """Enable tract scalargroup materials."""

    for label in labelgroup.labels:
        if label.is_rendered:
            mat = bpy.data.materials[label.name]
        else:
            mat = None
            # FIXME: will turn it grey:
            # either replace with default tract material or with trans=0?
        ob.data.materials.append(mat)
        for splidx in label.spline_indices:
            spl = ob.data.splines[splidx.spline_index]
            spl.material_index = label.value


def render_surfaces_scalargroup(scalargroup, ob):
    """Enable surface scalargroup materials."""

    scalar = scalargroup.scalars[scalargroup.index_scalars]
    mat = bpy.data.materials[scalargroup.name]
    ob.data.materials.append(mat)
    vg = ob.vertex_groups[scalar.name]
    nb_ma.assign_materialslots_to_faces(ob, [vg], [1])


def render_surfaces_labelgroup(labelgroup, ob):
    """Enable surface labelgroup materials."""

    vgs = []
    mat_idxs = []
    for label in labelgroup.labels:
        if label.is_rendered:
            mat = bpy.data.materials[label.name]
        else:
            mat = None
            # FIXME: will turn it grey:
            # either replace with default tract material or with trans=0?
        ob.data.materials.append(mat)
        vgs.append(ob.vertex_groups[label.name])
        mat_idxs.append(len(ob.data.materials) - 1)

    nb_ma.assign_materialslots_to_faces(ob, vgs, mat_idxs)


def overlay_is_rendered_update(self, context):
    """Update the render status of the overlay."""

    scn = context.scene

    split_path = self.path_from_id().split('.')
    parent = scn.path_resolve('.'.join(split_path[:2]))

    try:
        pg_sc1 = bpy.types.VoxelvolumeProperties
    except AttributeError:
        pg_sc1 = pg.bl_rna_get_subclass_py("VoxelvolumeProperties")

    if isinstance(parent, pg_sc1):
        mat = bpy.data.materials[parent.name]
        ts_idx = mat.texture_slots.find(self.name)
        mat.use_textures[ts_idx] = self.is_rendered


def label_is_rendered_update(self, context):
    """Update the render status of the overlay."""

    scn = context.scene

    split_path = self.path_from_id().split('.')
    nb_ob = scn.path_resolve('.'.join(split_path[:2]))
    nb_ov = scn.path_resolve('.'.join(split_path[:3]))

    try:
        pg_sc1 = bpy.types.VoxelvolumeProperties
    except AttributeError:
        pg_sc1 = pg.bl_rna_get_subclass_py("VoxelvolumeProperties")

    if isinstance(nb_ob, pg_sc1):
        tex = bpy.data.textures[nb_ov.name]
        el_idx = nb_ov.labels.find(self.name) + 1
        el = tex.color_ramp.elements[el_idx]
        if any(list(el.color)):
            self.colour_custom = el.color
        if self.is_rendered:
            el.color = self.colour_custom
        else:
            el.color = [0, 0, 0, 0]
        # FIXME: doesnt work for many-labeled cr option


def bordergroup_is_rendered_update(self, context):
    """Update the render status of the overlay."""

    for border in self.borders:
        ob = bpy.data.objects[border.name]
        if self.is_rendered:
            ob.hide = ob.hide_render = not border.is_rendered
        else:
            ob.hide = ob.hide_render = True


def border_is_rendered_update(self, context):
    """Update the render status of the overlay."""

    ob = bpy.data.objects[self.name]
    ob.hide = ob.hide_render = not self.is_rendered


def active_overlay_update(self, context):
    """Update the render status of the overlay."""

    scn = context.scene
    nb = scn.nb

    ob = bpy.data.objects[self.name]

    try:
        pg_sc1 = bpy.types.TractProperties
        pg_sc2 = bpy.types.SurfaceProperties
        pg_sc4 = bpy.types.ScalarGroupProperties
        pg_sc5 = bpy.types.LabelGroupProperties
    except AttributeError:
        pg_sc1 = pg.bl_rna_get_subclass_py("TractProperties")
        pg_sc2 = pg.bl_rna_get_subclass_py("SurfaceProperties")
        pg_sc4 = pg.bl_rna_get_subclass_py("ScalarGroupProperties")
        pg_sc5 = pg.bl_rna_get_subclass_py("LabelGroupProperties")

    if self.active_overlay == 'no_overlay':
        nb_ov = None
    else:
        nb_ov_format = '{}.{}["{}"]'.format(self.path_from_id(), '{}',
                                            self.active_overlay)
        try:
            nb_ov_path = nb_ov_format.format('scalargroups')
            nb_ov = scn.path_resolve(nb_ov_path)
        except:
            nb_ov_path = nb_ov_format.format('labelgroups')
            nb_ov = scn.path_resolve(nb_ov_path)

    if isinstance(self, pg_sc1):

        disable_tract_overlay(ob, ob.data.splines)

        if isinstance(nb_ov, pg_sc4):
            render_tracts_scalargroup(nb_ov, ob)
        elif isinstance(nb_ov, pg_sc5):
            render_tracts_labelgroup(nb_ov, ob)

    elif isinstance(self, pg_sc2):

        disable_tract_overlay(ob, ob.data.polygons)

        if isinstance(nb_ov, pg_sc4):
            render_surfaces_scalargroup(nb_ov, ob)
        elif isinstance(nb_ov, pg_sc5):
            render_surfaces_labelgroup(nb_ov, ob)

        for carver in self.carvers:
            carveob = bpy.data.objects[carver.name]
            disable_tract_overlay(carveob)
            for mat in ob.data.materials[1:]:
                carveob.data.materials.append(mat)


def overlays_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    overlays = [sg for sg in self.scalargroups]
    overlays += [lg for lg in self.labelgroups]
    items = [("no_overlay", "No overlay", "No overlay", 0)]
    items += [(ov.name, ov.name, "List the overlays", i + 1)
              for i, ov in enumerate(overlays)]

    return items


def sliceproperty_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    nb_ob = scn.path_resolve(self.nb_object_data_path)
    # TODO: return if not defined

    try:
        pg_sc1 = bpy.types.TractProperties
    except AttributeError:
        pg_sc1 = pg.bl_rna_get_subclass_py("TractProperties")

    if isinstance(nb_ob, pg_sc1):
        items = [("bevel_depth", "Bevel depth", "Bevel depth", 0),
                 ("bevel_factor_start", "Bevel factor start",
                  "Bevel factor start", 1)]
    else:
        items = [("Thickness", "Thickness", "Thickness", 0),
                 ("Position", "Position", "Position", 1),
                 ("Angle", "Angle", "Angle", 2)]

    return items


# ========================================================================== #
# NeuroBlender custom properties
# ========================================================================== #


class SettingsProperties(pg):
    """Properties for the NeuroBlender settings."""

    nb_initialized = True
    sp = bpy.utils.script_path_user()
    cmapdir = os.path.join(sp, 'presets', 'neuroblender_colourmaps')
    if (not os.path.isdir(cmapdir)):
        nb_initialized = False

    is_initialized = BoolProperty(
        name="Show/hide NeuroBlender",
        description="Show/hide the NeuroBlender panel contents",
        default=nb_initialized)

    sp_presetlabel = StringProperty(
        name="SP label",
        default="")

    projectdir = StringProperty(
        name="Project directory",
        description="The path to the NeuroBlender project",
        subtype="DIR_PATH",
        default=os.path.expanduser('~'))

    try:
        import nibabel as nib
        nib_valid = True
        nib_dir = os.path.dirname(nib.__file__)
        esp_path = os.path.dirname(nib_dir)
    except:
        nib_valid = False
        esp_path = ""

    nibabel_valid = BoolProperty(
        name="nibabel valid",
        description="Indicates whether nibabel has been detected",
        default=nib_valid)

    esp_path = StringProperty(
        name="External site-packages",
        description=""""
            The path to the site-packages directory
            of an equivalent python version with nibabel installed
            e.g. using:
            >>> conda create --name blender python=3.5.1
            >>> source activate blender
            >>> pip install git+git://github.com/nipy/nibabel.git@master
            on Mac this would be the directory:
            <conda root dir>/envs/blender/lib/python3.5/site-packages
            """,
        default=esp_path,
        subtype="DIR_PATH",
        update=esp_path_update)

    mode = EnumProperty(
        name="mode",
        description="switch between NeuroBlender modes",
        items=[("artistic", "artistic", "artistic", 1),
               ("scientific", "scientific", "scientific", 2)],
        default="artistic",
        update=mode_enum_update)

    engine = EnumProperty(
        name="engine",
        description="""Engine to use for rendering""",
        items=[("BLENDER_RENDER", "Blender Render",
                "Blender Render: required for voxelvolumes", 0),
               ("CYCLES", "Cycles Render",
                "Cycles Render: required for most overlays", 2)],
        update=engine_update)

    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])
    texmethod = IntProperty(
        name="texmethod",
        description="",
        default=1,
        min=1, max=3)
    uv_resolution = IntProperty(
        name="utexture resolution",
        description="the resolution of baked textures",
        default=4096,
        min=1)
    uv_bakeall = BoolProperty(
        name="Bake all",
        description="Bake single or all scalars in a group",
        default=True)

    advanced = BoolProperty(
        name="Advanced mode",
        description="Advanced NeuroBlender layout",
        default=False)

    verbose = BoolProperty(
        name="Verbose",
        description="Verbose reporting",
        default=False)

    switches = BoolProperty(
        name="Show switchbar",
        description="Show a small bar with switches in each panel",
        default=True)

    goboxy = BoolProperty(
        name="Show boxes",
        description="Show items in boxes when expanded",
        default=False)

    camera_rig = EnumProperty(
        name="Camera rig",
        description="The number of default cameras to add in a preset",
        default="single",
        items=[("single", "single", "single", 0),
               ("double_diag", "double_diag", "double_diag", 1),
               ("double_LR", "double_LR", "double_LR", 2),
               ("double_AP", "double_AP", "double_AP", 3),
               ("double_IS", "double_IS", "double_IS", 4),
               ("sextet", "sextet", "sextet", 5),
               ("quartet", "quartet", "quartet", 6),
               ("octet", "octet", "octet", 7)])

    lighting_rig = EnumProperty(
        name="Lighting rig",
        description="The number of default lights to add in a preset",
        default="triple",
        items=[("single", "single", "single", 0),
               ("triple", "triple", "triple", 1)])

    table_rig = EnumProperty(
        name="Table rig",
        description="The default table to add in a preset",
        default="none",
        items=[("none", "none", "none", 0),
               ("simple", "simple", "simple", 1)])


class CameraProperties(pg):
    """Properties of cameras."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="CAMERA_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the camera is used for rendering",
        default=True)

    cam_view = FloatVectorProperty(
        name="Numeric input",
        description="Setting of the LR-AP-IS viewpoint of the camera",
        default=[2.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")

    cam_view_enum_LR = EnumProperty(
        name="Camera LR viewpoint",
        description="Choose a LR position for the camera",
        default="R",
        items=[("L", "L", "Left", 0),
               ("C", "C", "Centre", 1),
               ("R", "R", "Right", 2)],
        update=cam_view_enum_XX_update)
    cam_view_enum_AP = EnumProperty(
        name="Camera AP viewpoint",
        description="Choose a AP position for the camera",
        default="A",
        items=[("A", "A", "Anterior", 0),
               ("C", "C", "Centre", 1),
               ("P", "P", "Posterior", 2)],
        update=cam_view_enum_XX_update)
    cam_view_enum_IS = EnumProperty(
        name="Camera IS viewpoint",
        description="Choose a IS position for the camera",
        default="S",
        items=[("I", "I", "Inferior", 0),
               ("C", "C", "Centre", 1),
               ("S", "S", "Superior", 2)],
        update=cam_view_enum_XX_update)
    cam_distance = FloatProperty(
        name="Camera distance",
        description="Relative distance of the camera (to bounding box)",
        default=5,
        min=0,
        update=cam_view_enum_XX_update)

    trackobject = EnumProperty(
        name="Track object",
        description="Choose an object to track with the camera",
        items=trackobject_enum_callback,
        update=trackobject_enum_update)


class LightProperties(pg):
    """Properties of light."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the lights",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="OUTLINER_OB_LAMP")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the light is rendered",
        default=True,
        update=light_update)

    type = EnumProperty(
        name="Light type",
        description="type of lighting",
        items=[("POINT", "POINT", "POINT", 0),
               ("SUN", "SUN", "SUN", 1),
               ("SPOT", "SPOT", "SPOT", 2),
               ("HEMI", "HEMI", "HEMI", 3),
               ("AREA", "AREA", "AREA", 4)],
        default="HEMI",
        update=light_update)
    colour = FloatVectorProperty(
        name="Colour",
        description="Colour of the light",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR",
        update=light_update)
    strength = FloatProperty(
        name="Strength",
        description="Strength of the light",
        default=1,
        min=0,
        update=light_update)
    size = FloatVectorProperty(
        name="Size",
        description="Relative size of the plane light (to bounding box)",
        size=2,
        default=[1.0, 1.0],
        update=light_update)
    location = FloatVectorProperty(
        name="Location",
        description="",
        default=[3.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")


class TableProperties(pg):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the table",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="SURFACE_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the table is rendered",
        default=True,
        update=table_update)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR",
        update=material_update)

    scale = FloatVectorProperty(
        name="Table scale",
        description="Relative size of the table",
        default=[4.0, 4.0, 1.0],
        subtype="TRANSLATION")
    location = FloatVectorProperty(
        name="Table location",
        description="Relative location of the table",
        default=[0.0, 0.0, -1.0],
        subtype="TRANSLATION")


class CamPathProperties(pg):
    """Properties of a camera path."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for camera path",
        default="CAMERA_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the camera path passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the camera path is rendered",
        default=True)


class AnimationProperties(pg):
    """Properties of animation."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for animation",
        default="RENDER_ANIMATION")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the animation is rendered",
        default=True)

    animationtype = EnumProperty(
        name="Animation type",
        description="Switch between animation types",
        items=[("camerapath", "Camera trajectory",
                "Let the camera follow a trajectory", 0),
               ("carver", "Carver",
                "Animate a carver", 1),
               ("timeseries", "Time series",
                "Play a time series", 2),
               ("morph", "Morph",
                "Morph an object over time", 3),
               ])

    frame_start = IntProperty(
        name="startframe",
        description="first frame of the animation",
        min=1,
        default=1,
        update=timings_enum_update)
    frame_end = IntProperty(
        name="endframe",
        description="last frame of the animation",
        min=2,
        default=100,
        update=timings_enum_update)
    repetitions = FloatProperty(
        name="repetitions",
        description="number of repetitions",
        default=1,
        update=timings_enum_update)
    offset = FloatProperty(
        name="offset",
        description="offset (relative to full cycle)",
        default=0,
        min=0,
        max=1,
        update=timings_enum_update)

    anim_range = FloatVectorProperty(
        name="anim range",
        description="Relative limits on the values of the property",
        size=2,
        default=[0, 1],
        min=0,
        max=1,
        update=timings_enum_update)

    anim_block = IntVectorProperty(
        name="anim block",
        description="",
        size=2,
        default=[1, 100])

    reverse = BoolProperty(
        name="Reverse",
        description="Toggle direction of trajectory traversal",
        default=False,
        update=direction_toggle_update)

    reverse_action = BoolProperty(
        name="Reverse action",
        description="Toggle direction of action grow/eat",
        default=False,
        update=direction_toggle_update)

    mirror = BoolProperty(
        name="Mirror",
        description="Mirror repetition cycles",
        default=False,
        update=direction_toggle_update)

    noise_scale = FloatProperty(
        name="scale",
        description="amplitude of added noise",
        default=1,
        update=direction_toggle_update)
    noise_strength = FloatProperty(
        name="strength",
        description="amplitude of added noise",
        default=0,
        update=direction_toggle_update)

    default_value = FloatProperty(
        name="Default value",
        description="Default value for animated property",
        default=0)

    camera = StringProperty(
        name="Camera",
        description="The camera to animate")
    campaths_enum = EnumProperty(
        name="Camera trajectory",
        description="Choose the camera trajectory",
        items=campaths_enum_callback,
        update=campaths_enum_update)
    tracktype = EnumProperty(
        name="Tracktype",
        description="Camera rotation options",
        items=[("TrackNone", "None", "Use the camera rotation property", 0),
               ("TrackObject", "Object", "Track an object", 1),
               ("TrackPath", "Path", "Orient along the trajectory", 2)],
        default="TrackObject",
        update=tracktype_enum_update)
    pathtype = EnumProperty(
        name="Pathtype",
        description="Trajectory types for the camera animation",
        items=campathtype_enum_callback)

    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="Z",
        update=anim_update)

    anim_tract = EnumProperty(
        name="Animation streamline",
        description="Select tract to animate",
        items=tracts_enum_callback)
    spline_index = IntProperty(
        name="streamline index",
        description="index of the streamline to animate",
        min=0,
        default=0)

    anim_curve = EnumProperty(
        name="Animation curves",
        description="Select curve to animate",
        items=curves_enum_callback)

    nb_object_data_path = EnumProperty(
        name="Animation object",
        description="Specify path to object to animate",
        items=anim_nb_object_enum_callback,
        update=anim_update)

    nb_target_data_path = EnumProperty(
        name="Target object",
        description="Specify path to object to animate",
        items=anim_nb_target_enum_callback,
        update=anim_update)

    sliceproperty = EnumProperty(
        name="Property to animate",
        description="Select property to animate",
        items=sliceproperty_enum_callback,
        update=anim_update)

    cnsname = StringProperty(
        name="Constraint Name",
        description="Name of the campath constraint",
        default="")

    interpolation = StringProperty(
        name="FCurve interpolation",
        description="Specify the interpolation to use for the fcurve",
        default='LINEAR')

    rna_data_path = StringProperty(
        name="RNA path",
        description="Path to this animation's RNA")
    fcurve_data_path = StringProperty(
        name="FCurve path",
        description="Path to this animation's fcurve")
    fcurve_array_index = IntProperty(
        name="index property",
        description="index of the animated property",
        default=-1)


class CarveObjectProperties(pg):
    """Properties of carver."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the carver",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for animation",
        default="MOD_BOOLEAN")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the carver is rendered",
        default=True,
        update=carveobject_is_rendered_update)

    slicethickness = FloatVectorProperty(
        name="Slice thickness",
        description="The thickness of the slices",
        default=(0.9999, 0.9999, 0.9999),
        size=3,
        precision=4,
        min=0.0001,
        max=0.9999,
        subtype="TRANSLATION",
        update=carvers_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0, 0, 0),
        size=3,
        precision=4,
        min=-0.9999,
        max=0.9999,
        subtype="TRANSLATION",
        update=carvers_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=4,
        min=-1.5708,
        max=1.5708,
        subtype="TRANSLATION",
        update=carvers_update)

    type = StringProperty(
        name="Type",
        description="Specify a type for the carve object")


class CarverProperties(pg):
    """Properties of carver."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the carver",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for animation",
        default="MOD_BOOLEAN")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the carver is rendered",
        default=True)

    carveobjects = CollectionProperty(
        type=CarveObjectProperties,
        name="Carve objects",
        description="The collection of carve objects")
    index_carveobjects = IntProperty(
        name="object index",
        description="index of the objects collection",
        default=0,
        min=0)

    carveobjects_enum = EnumProperty(
        name="Object selector",
        description="Select carve objects",
        items=carveobjects_enum_callback)

    carveobject_type_enum = EnumProperty(
        name="Type",
        description="Type of carve object",
        default="slice",
        items=[("slice", "Slice", "Slice", 0),
               ("orthoslices", "Orthogonal slices", "Orthogonal slices", 1),
               ("cube", "Cube", "Cube", 2),
               ("cylinder", "Cylinder", "Cylinder", 3),
               ("sphere", "Sphere", "Sphere", 4),
               ("suzanne", "Suzanne", "Suzanne", 5),
               ("activeob", "Active object", "Active object", 6)])


class PresetProperties(pg):
    """Properties of a preset."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
#     filepath = StringProperty(
#         name="Filepath",
#         description="The filepath to the preset")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="STICKY_UVS_LOC")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the preset passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the preset is rendered",
        default=True)

    layer = IntProperty(
        name="preset renderlayer",
        description="the renderlayer for this preset",
        default=10,
        min=0)

    centre = StringProperty(
        name="Centre",
        description="Scene centre",
        default="Centre")
    box = StringProperty(
        name="Box",
        description="Scene box",
        default="Box")

    cam = StringProperty(
        name="Camera",
        description="Scene camera",
        default="")
    camerasempty = StringProperty(
        name="CamerasEmpty",
        description="Scene cameras empty",
        default="PresetCameras")
    campathsempty = StringProperty(
        name="CamPathsEmpty",
        description="Scene camera paths empty",
        default="PresetCampaths")
    lightsempty = StringProperty(
        name="LightsEmpty",
        description="Scene lights empty",
        default="PresetLights")
    tablesempty = StringProperty(
        name="TablesEmpty",
        description="Scene tables empty",
        default="PresetTables")
    dims = FloatVectorProperty(
        name="dims",
        description="Dimension of the scene",
        default=[100, 100, 100],
        subtype="TRANSLATION")

    cameras = CollectionProperty(
        type=CameraProperties,
        name="cameras",
        description="The collection of loaded cameras")
    index_cameras = IntProperty(
        name="camera index",
        description="index of the cameras collection",
        default=0,
        min=0,
        update=index_cameras_update)
    lights = CollectionProperty(
        type=LightProperties,
        name="lights",
        description="The collection of loaded lights")
    index_lights = IntProperty(
        name="light index",
        description="index of the lights collection",
        default=0,
        min=0)
    tables = CollectionProperty(
        type=TableProperties,
        name="tables",
        description="The collection of loaded tables")
    index_tables = IntProperty(
        name="table index",
        description="index of the tables collection",
        default=0,
        min=0)

    frame_start = IntProperty(
        name="startframe",
        description="first frame of the animation",
        min=1,
        default=1)
    frame_end = IntProperty(
        name="endframe",
        description="last frame of the animation",
        min=2,
        default=100)


class ColorRampProperties(pg):
    """Custom properties of color ramps."""

    name = StringProperty(
        name="Name",
        description="The name of the color stop",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for colorramp elements",
        default="FULLSCREEN_ENTER")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    nn_position = FloatProperty(
        name="nn_position",
        description="The non-normalized position of the color stop",
        default=0,
        precision=4)

    def calc_nn_position(self, position, datarange):
        """Calculate the non-normalized positions of elements."""

        dmin = datarange[0]
        dmax = datarange[1]
        drange = dmax - dmin
        self.nn_position = position * drange + dmin


class SplineGroupProperties(pg):
    """Custom properties of splinegroups."""

    spline_index = IntProperty(
        name="Spline index",
        description="Index of spline in the labelgroup",
        default=0)


class ScalarProperties(pg):
    """Properties of scalar overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the scalar overlay",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the scalar overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for scalar overlays",
        default="FORCE_CHARGE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=colourmap_enum_callback,
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)

    showcolourbar = BoolProperty(
        name="Render colourbar",
        description="Show/hide colourbar in rendered image",
        default=False)
    colourbar_placement = EnumProperty(
        name="Colourbar placement",
        description="Choose where to show the colourbar",
        default="top-right",
        items=[("top-right", "top-right",
                "Place colourbar top-right"),
               ("top-left", "top-left",
                "Place colourbar top-left"),
               ("bottom-right", "bottom-right",
                "Place colourbar bottom-right"),
               ("bottom-left", "bottom-left",
                "Place colourbar bottom-left")])  # update=colourbar_update
    colourbar_size = FloatVectorProperty(
        name="size",
        description="Set the size of the colourbar",
        default=[0.25, 0.05],
        size=2, min=0., max=1.)
    colourbar_position = FloatVectorProperty(
        name="position",
        description="Set the position of the colourbar",
        default=[1., 1.],
        size=2, min=-1., max=1.)
    textlabel_colour = FloatVectorProperty(
        name="Textlabel colour",
        description="Pick a colour",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    textlabel_placement = EnumProperty(
        name="Textlabel placement",
        description="Choose where to show the label",
        default="out",
        items=[("out", "out", "Place labels outside"),
               ("in", "in", "Place labels inside")])  # update=textlabel_update
    textlabel_size = FloatProperty(
        name="Textlabel size",
        description="Set the size of the textlabel (relative to colourbar)",
        default=0.5,
        min=0.,
        max=1.)

    matname = StringProperty(
        name="Material name",
        description="The name of the scalar overlay")
    texname = StringProperty(
        name="Texture name",
        description="The name of the scalar overlay")
    tex_idx = IntProperty(
        name="Texture index",
        description="The name of the scalar overlay")


class LabelProperties(pg):
    """Properties of label overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for label overlays",
        default="BRUSH_VERTEXDRAW")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the label is rendered",
        default=True,
        update=label_is_rendered_update)

    value = IntProperty(
        name="Label value",
        description="The value of the label",
        default=0)
    colour = FloatVectorProperty(
        name="Label color",
        description="The color of the label",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        update=material_update)
    colour_custom = FloatVectorProperty(
        name="Custom label color",
        description="The color of the label",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        update=material_update)

    spline_indices = CollectionProperty(
        type=SplineGroupProperties,
        name="spline indices",
        description="The collection of splines belonging to this label")


class BorderProperties(pg):
    """Properties of border overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for border overlays",
        default="CURVE_BEZCIRCLE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the border is rendered",
        default=True,
        update=border_is_rendered_update)

    value = IntProperty(
        name="Label value",
        description="The value of the label in vertexgroup 'scalarname'",
        default=0)
    colour = FloatVectorProperty(
        name="Border color",
        description="The color of the border",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        update=material_update)
    colour_custom = FloatVectorProperty(
        name="Custom label color",
        description="The color of the label",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        update=material_update)


class ScalarGroupProperties(pg):
    """Properties of time series overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the time series overlay",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the time series overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for time series overlays",
        default="TIME")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True,
        update=overlay_is_rendered_update)

    scalars = CollectionProperty(
        type=ScalarProperties,
        name="scalars",
        description="The collection of loaded scalars")
    index_scalars = IntProperty(
        name="scalar index",
        description="index of the scalars collection",
        default=0,
        min=0,
        update=index_scalars_update)

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=colourmap_enum_callback,
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)

    showcolourbar = BoolProperty(
        name="Render colourbar",
        description="Show/hide colourbar in rendered image",
        default=False)
    colourbar_placement = EnumProperty(
        name="Colourbar placement",
        description="Choose where to show the colourbar",
        default="top-right",
        items=[("top-right", "top-right",
                "Place colourbar top-right"),
               ("top-left", "top-left",
                "Place colourbar top-left"),
               ("bottom-right", "bottom-right",
                "Place colourbar bottom-right"),
               ("bottom-left", "bottom-left",
                "Place colourbar bottom-left")])  # update=colourbar_update
    colourbar_size = FloatVectorProperty(
        name="size",
        description="Set the size of the colourbar",
        default=[0.25, 0.05],
        size=2, min=0., max=1.)
    colourbar_position = FloatVectorProperty(
        name="position",
        description="Set the position of the colourbar",
        default=[1., 1.],
        size=2, min=-1., max=1.)
    textlabel_colour = FloatVectorProperty(
        name="Textlabel colour",
        description="Pick a colour",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    textlabel_placement = EnumProperty(
        name="Textlabel placement",
        description="Choose where to show the label",
        default="out",
        items=[("out", "out", "Place labels outside"),
               ("in", "in", "Place labels inside")])  # update=textlabel_update
    textlabel_size = FloatProperty(
        name="Textlabel size",
        description="Set the size of the textlabel (relative to colourbar)",
        default=0.5,
        min=0.,
        max=1.)

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])

    prefix_parentname = BoolProperty(
        name="Prefix parentname",
        default=True,
        description="Prefix the name of the parent on overlays and items")
    timepoint_postfix = StringProperty(
        name="Timepoint postfix",
        description="Specify an re for the timepoint naming",
        default='vol{:04d}')
    spline_postfix = StringProperty(
        name="Spline postfix",
        description="Specify an re for the streamline naming",
        default='spl{:08d}')


class LabelGroupProperties(pg):
    """Properties of label groups."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the label overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for label overlays",
        default="BRUSH_VERTEXDRAW")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the label is rendered",
        default=True,
        update=overlay_is_rendered_update)

    labels = CollectionProperty(
        type=LabelProperties,
        name="labels",
        description="The collection of loaded labels")
    index_labels = IntProperty(
        name="label index",
        description="index of the labels collection",
        default=0,
        min=0,
        update=index_labels_update)

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=colourmap_enum_callback,
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])

    prefix_parentname = BoolProperty(
        name="Prefix parentname",
        default=True,
        description="Prefix the name of the parent on overlays and items")
    timepoint_postfix = StringProperty(
        name="Timepoint postfix",
        description="Specify an re for the timepoint naming",
        default='vol{:04d}')
    spline_postfix = StringProperty(
        name="Spline postfix",
        description="Specify an re for the streamline naming",
        default='spl{:08d}')


class BorderGroupProperties(pg):
    """Properties of border groups."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the border overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for border overlays",
        default="CURVE_BEZCIRCLE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the border is rendered",
        default=True,
        update=bordergroup_is_rendered_update)

    borders = CollectionProperty(
        type=BorderProperties,
        name="borders",
        description="The collection of loaded borders")
    index_borders = IntProperty(
        name="border index",
        description="index of the borders collection",
        default=0,
        min=0)

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])

    prefix_parentname = BoolProperty(
        name="Prefix parentname",
        default=True,
        description="Prefix the name of the parent on overlays and items")
    timepoint_postfix = StringProperty(
        name="Timepoint postfix",
        description="Specify an re for the timepoint naming",
        default='vol{:04d}')
    spline_postfix = StringProperty(
        name="Spline postfix",
        description="Specify an re for the streamline naming",
        default='spl{:08d}')


class TractProperties(pg):
    """Properties of tracts."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the tract (default: filename)",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the tract",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for tract objects",
        default="CURVE_BEZCURVE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)

    sformfile = StringProperty(
        name="Transform",
        description="""
            A file with transformation matrix
            It can be a nifti file (through nibabel)
            or an ascii with a space-delimited 4x4 matrix
            For .nii, it will only use the sform for now
            """,
        subtype="FILE_PATH",
        update=sformfile_update)

    active_overlay = EnumProperty(
        name="Active overlay",
        description="Select the active overlay",
        items=overlays_enum_callback,
        update=active_overlay_update)
    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded scalargroups")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0,
        update=index_scalars_update)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0,
        update=index_labels_update)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR",
        update=material_update)
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.,
        update=material_update)

    nstreamlines = IntProperty(
        name="Nstreamlines",
        description="Number of streamlines in the tract (before weeding)",
        min=0)
    streamlines_interpolated = FloatProperty(
        name="Interpolate streamlines",
        description="Interpolate the individual streamlines",
        default=1.,
        min=0.,
        max=1.)
    tract_weeded = FloatProperty(
        name="Tract weeding",
        description="Retain a random selection of streamlines",
        default=1.,
        min=0.,
        max=1.)

    carvers = CollectionProperty(
        type=CarverProperties,
        name="carvers",
        description="The collection of carvers")
    index_carvers = IntProperty(
        name="carver index",
        description="index of the carvers collection",
        default=0,
        min=0)
    carvers_enum = EnumProperty(
        name="carvers",
        description="select carver",
        items=carvers_enum_callback)


class SurfaceProperties(pg):
    """Properties of surfaces."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the surface (default: filename)",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the surface",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for surface objects",
        default="MESH_MONKEY")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)

    sformfile = StringProperty(
        name="Transform",
        description="""
            A file with transformation matrix
            It can be a nifti file (through nibabel)
            or an ascii with a space-delimited 4x4 matrix
            For .nii, it will only use the sform for now
            """,
        subtype="FILE_PATH",
        update=sformfile_update)

    active_overlay = EnumProperty(
        name="Active overlay",
        description="Select the active overlay",
        items=overlays_enum_callback,
        update=active_overlay_update)
    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded timeseries")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0,
        update=index_scalars_update)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0,
        update=index_labels_update)
    bordergroups = CollectionProperty(
        type=BorderGroupProperties,
        name="bordergroups",
        description="The collection of loaded bordergroups")
    index_bordergroups = IntProperty(
        name="bordergroup index",
        description="index of the bordergroups collection",
        default=0,
        min=0)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR",
        update=material_update)
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.0,
        update=material_update)

    sphere = EnumProperty(
        name="Unwrapping sphere",
        description="Select sphere for unwrapping",
        items=sphere_enum_callback)
    is_unwrapped = BoolProperty(
        name="Is unwrapped",
        description="Indicates if the surface has been unwrapped",
        default=False)

    carvers = CollectionProperty(
        type=CarverProperties,
        name="carvers",
        description="The collection of carvers")
    index_carvers = IntProperty(
        name="carver index",
        description="index of the carvers collection",
        default=0,
        min=0)
    carvers_enum = EnumProperty(
        name="carvers",
        description="select carver",
        items=carvers_enum_callback)


class VoxelvolumeProperties(pg):
    """Properties of voxelvolumes."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the voxelvolume (default: filename)",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the voxelvolume",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for surface objects",
        default="MESH_GRID")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)

    sformfile = StringProperty(
        name="Transform",
        description="""
            A file with transformation matrix
            It can be a nifti file (through nibabel)
            or an ascii with a space-delimited 4x4 matrix
            For .nii, it will only use the sform for now
            """,
        subtype="FILE_PATH",
        update=sformfile_update)
    dimensions = FloatVectorProperty(
        name="dimensions",
        description="",
        default=[0.0, 0.0, 0.0, 0.0],
        size=4,
        subtype="TRANSLATION")

    active_overlay = EnumProperty(
        name="Active overlay",
        description="Select the active overlay",
        items=overlays_enum_callback,
        update=active_overlay_update)
    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded scalargroups")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0,
        update=index_scalars_update)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0)

    rendertype = EnumProperty(
        name="rendertype",
        description="Surface or volume rendering of texture",
        items=[("SURFACE", "Surface",
                "Switch to surface rendering", 0),
               ("VOLUME", "Volume",
                "Switch to volume rendering", 2)],
        update=rendertype_enum_update,
        default="VOLUME")

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max in the data",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=colourmap_enum_callback,
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)

    showcolourbar = BoolProperty(
        name="Render colourbar",
        description="Show/hide colourbar in rendered image",
        default=False)
    colourbar_placement = EnumProperty(
        name="Colourbar placement",
        description="Choose where to show the colourbar",
        default="top-right",
        items=[("top-right", "top-right",
                "Place colourbar top-right"),
               ("top-left", "top-left",
                "Place colourbar top-left"),
               ("bottom-right", "bottom-right",
                "Place colourbar bottom-right"),
               ("bottom-left", "bottom-left",
                "Place colourbar bottom-left")])  # update=colourbar_update
    colourbar_size = FloatVectorProperty(
        name="size",
        description="Set the size of the colourbar",
        default=[0.25, 0.05],
        size=2, min=0., max=1.)
    colourbar_position = FloatVectorProperty(
        name="position",
        description="Set the position of the colourbar",
        default=[1., 1.],
        size=2, min=-1., max=1.)
    textlabel_colour = FloatVectorProperty(
        name="Textlabel colour",
        description="Pick a colour",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    textlabel_placement = EnumProperty(
        name="Textlabel placement",
        description="Choose where to show the label",
        default="out",
        items=[("out", "out", "Place labels outside"),
               ("in", "in", "Place labels inside")])  # update=textlabel_update
    textlabel_size = FloatProperty(
        name="Textlabel size",
        description="Set the size of the textlabel (relative to colourbar)",
        default=0.5,
        min=0.,
        max=1.)

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])

    matname = StringProperty(
        name="Material name",
        description="The name of the voxelvolume material")
    texname = StringProperty(
        name="Texture name",
        description="The name of the voxelvolume texture")

    carvers = CollectionProperty(
        type=CarverProperties,
        name="carvers",
        description="The collection of carvers")
    index_carvers = IntProperty(
        name="carver index",
        description="index of the carvers collection",
        default=0,
        min=0)
    carvers_enum = EnumProperty(
        name="carvers",
        description="select carver",
        items=carvers_enum_callback)


class NeuroBlenderProperties(pg):
    """Properties for the NeuroBlender panel."""

    is_enabled = BoolProperty(
        name="Show/hide NeuroBlender",
        description="Show/hide the NeuroBlender panel contents",
        default=True)

    settingprops = PointerProperty(type=SettingsProperties)

    show_carvers = BoolProperty(
        name="Carvers",
        default=False,
        description="Show/hide the preset's carver properties")
    show_material = BoolProperty(
        name="Material",
        default=False,
        description="Show/hide the object's materials options")
    show_transform = BoolProperty(
        name="Transform",
        default=False,
        description="Show/hide the object's transform options")
    show_info = BoolProperty(
        name="Info",
        default=False,
        description="Show/hide the object's info")
    show_overlay_material = BoolProperty(
        name="Overlay material",
        default=False,
        description="Show/hide the object's overlay material")
    show_overlay_info = BoolProperty(
        name="Overlay info",
        default=False,
        description="Show/hide the overlay's info")
    show_items = BoolProperty(
        name="Items",
        default=False,
        description="Show/hide the group overlay's items")
    show_itemprops = BoolProperty(
        name="Item properties",
        default=True,
        description="Show/hide the properties of the item")
    show_bounds = BoolProperty(
        name="Bounds",
        default=False,
        description="Show/hide the preset's centre and dimensions")
    show_cameras = BoolProperty(
        name="Cameras",
        default=False,
        description="Show/hide the preset's camera properties")
    show_lights = BoolProperty(
        name="Lights",
        default=False,
        description="Show/hide the preset's lights properties")
    show_tables = BoolProperty(
        name="Tables",
        default=False,
        description="Show/hide the preset's table properties")
    show_animations = BoolProperty(
        name="Animation",
        default=False,
        description="Show/hide the preset's animations")
    show_timings = BoolProperty(
        name="Timings",
        default=True,
        description="Show/hide the animation's timings")
    show_carver_properties = BoolProperty(
        name="Animation properties",
        default=False,
        description="Show/hide the animation properties")
    show_animcamerapath = BoolProperty(
        name="CameraPath",
        default=True,
        description="Show/hide the animation's camera path properties")
    show_animslices = BoolProperty(
        name="Slices",
        default=True,
        description="Show/hide the animation's slice properties")
    show_timeseries = BoolProperty(
        name="Time Series",
        default=True,
        description="Show/hide the animation's time series properties")
    show_camerapath = BoolProperty(
        name="Camera trajectory",
        default=True,
        description="Show/hide the animation's camera path properties")
    show_tracking = BoolProperty(
        name="Tracking",
        default=False,
        description="Show/hide the camera path's tracking properties")
    show_newpath = BoolProperty(
        name="New trajectory",
        default=False,
        description="Show/hide the camera trajectory generator")
    show_points = BoolProperty(
        name="Points",
        default=False,
        description="Show/hide the camera path points")
    show_unwrap = BoolProperty(
        name="Unwrap",
        default=False,
        description="Show/hide the unwrapping options")
    show_manage_colourmaps = BoolProperty(
        name="Manage colour maps",
        default=False,
        description="Show/hide the colour map management",
        update=managecmap_update)
    show_texture_preferences = BoolProperty(
        name="Texture preferences",
        default=False,
        description="Show/hide the texture preferences")
    show_panel_preferences = BoolProperty(
        name="Panel preferences",
        default=False,
        description="Show/hide the panel preferences")
    show_scene_preferences = BoolProperty(
        name="Scene preferences",
        default=False,
        description="Show/hide the scene preferences")

    tracts = CollectionProperty(
        type=TractProperties,
        name="tracts",
        description="The collection of loaded tracts")
    index_tracts = IntProperty(
        name="tract index",
        description="index of the tracts collection",
        default=0,
        min=0)
    surfaces = CollectionProperty(
        type=SurfaceProperties,
        name="surfaces",
        description="The collection of loaded surfaces")
    index_surfaces = IntProperty(
        name="surface index",
        description="index of the surfaces collection",
        default=0,
        min=0)
    voxelvolumes = CollectionProperty(
        type=VoxelvolumeProperties,
        name="voxelvolumes",
        description="The collection of loaded voxelvolumes")
    index_voxelvolumes = IntProperty(
        name="voxelvolume index",
        description="index of the voxelvolumes collection",
        default=0,
        min=0)

    presets = CollectionProperty(
        type=PresetProperties,
        name="presets",
        description="The collection of presets")
    index_presets = IntProperty(
        name="preset index",
        description="index of the presets",
        default=0,
        min=0,
        update=index_presets_update)

    animations = CollectionProperty(
        type=AnimationProperties,
        name="animations",
        description="The collection of animations")
    index_animations = IntProperty(
        name="animation index",
        description="index of the animations collection",
        default=0,
        min=0)

    campaths = CollectionProperty(
        type=CamPathProperties,
        name="camera paths",
        description="The collection of camera paths")
    index_campaths = IntProperty(
        name="camera path index",
        description="index of the camera paths collection",
        default=0,
        min=0)

    objecttype = EnumProperty(
        name="object type",
        description="switch between object types",
        items=[("tracts", "tracts", "List the tracts", 1),
               ("surfaces", "surfaces", "List the surfaces", 2),
               ("voxelvolumes", "voxelvolumes", "List the voxelvolumes", 3)],
        default="tracts")
    overlaytype = EnumProperty(
        name="overlay type",
        description="switch between overlay types",
        items=overlay_enum_callback)

    animationtype = EnumProperty(
        name="Animation type",
        description="Switch between animation types",
        items=[("camerapath", "Camera trajectory",
                "Let the camera follow a trajectory", 0),
               ("carver", "Carver",
                "Animate a carver", 1),
               ("timeseries", "Time series",
                "Play a time series", 2),
               ("morph", "Morph",
                "Morph an object over time", 3),
               ])

    # TODO: move elsewhere
    cr_keeprange = BoolProperty(
        name="Keep range",
        description="Keep/discard the current range of the colour ramp",
        default=True)
    cr_path = StringProperty(
        name="CR path")
    cm_presetlabel = StringProperty(
        name="CM label",
        default="Grey")
