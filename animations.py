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


"""The NeuroBlender animations module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements simple animations in NeuroBlender.
"""


# =========================================================================== #


import bpy

from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.types import (Panel,
                       Operator,
                       OperatorFileListElement,
                       PropertyGroup,
                       UIList,
                       Menu)
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       IntProperty,
                       IntVectorProperty,
                       PointerProperty)
from bl_operators.presets import AddPresetBase, ExecutePreset

import os
import sys
from shutil import copy
import numpy as np
import mathutils
import re

# from . import animations as nb_an
from . import base as nb_ba
from . import beautify as nb_be
from . import colourmaps as nb_cm
from . import imports as nb_im
from . import materials as nb_ma
from . import overlays as nb_ol
from . import panels as nb_pa
from . import renderpresets as nb_rp
from . import scenepresets as nb_sp
from . import settings as nb_se
from . import utils as nb_ut

# from .imports import (add_animation_to_collection,
#                       make_polyline_ob,
#                       add_campath_to_collection)
# from .renderpresets import (set_animations,
#                             clear_camera_path_animations,
#                             create_camera_path_animations,
#                             generate_timeline,
#                             restrict_incluence_timeline,
#                             calculate_coefficients)  # find_ts_scalargroups
# from .utils import (check_name,
#                     update_name)


# =========================================================================== #


class SetAnimations(Operator):
    bl_idname = "nb.set_animations"
    bl_label = "Set animations"
    bl_description = "(Re)set all animation in the preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        nb_rp.set_animations()

        return {"FINISHED"}


class AddAnimation(Operator):
    bl_idname = "nb.import_animations"
    bl_label = "New animation"
    bl_description = "Create a new animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="index presets",
        description="Specify preset index",
        default=-1)
    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="Anim")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [preset.animations for preset in nb.presets]
        name = nb_ut.check_name(self.name, "", ca, forcefill=True)
        nb_im.add_animation_to_collection(name)

        nb_preset = nb.presets[nb.index_presets]  # FIXME: self
        infostring = 'added animation "%s" in preset "%s"'
        info = [infostring % (name, nb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets

        return self.execute(context)


class AddCamPoint(Operator):
    bl_idname = "nb.add_campoint"
    bl_label = "New camera position"
    bl_description = "Create a new camera position in campath"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="index presets",
        description="Specify preset index",
        default=-1)
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)
    co = FloatVectorProperty(
        name="camera coordinates",
        description="Specify camera coordinates",
        default=[0.0, 0.0, 0.0])

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        preset = nb.presets[self.index_presets]
        anim = preset.animations[self.index_animations]
        campath = bpy.data.objects[anim.campaths_enum]

        try:
            spline = campath.data.splines[0]
            spline.points.add()
        except:
            spline = campath.data.splines.new('POLY')

        spline.points[-1].co = tuple(self.co) + (1,)
        spline.order_u = len(spline.points) - 1
        spline.use_endpoint_u = True

        infostring = 'added campoint "%02f, %02f, %02f"'
        info = [infostring % tuple(self.co)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]

        self.index_animations = preset.index_animations

        cam = bpy.data.objects[preset.cameras[0].name]
        centre = bpy.data.objects[preset.centre]

        self.co[0] = cam.location[0] * preset.dims[0] / 2 + centre.location[0]
        self.co[1] = cam.location[1] * preset.dims[1] / 2 + centre.location[1]
        self.co[2] = cam.location[2] * preset.dims[2] / 2 + centre.location[2]

        return self.execute(context)


class AddCamPath(Operator):
    bl_idname = "nb.add_campath"
    bl_label = "New camera path"
    bl_description = "Create a new path for the camera"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        default="")
    index_presets = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)
    pathtype = EnumProperty(
        name="Pathtype",
        description="Trajectory types for the camera animation",
        items=[("Circular", "Circular",
                "Circular trajectory from camera position", 0),
               ("Streamline", "Streamline",
                "Curvilinear trajectory from a streamline", 1),
               ("Select", "Select",
                "Curvilinear trajectory from curve", 2),
               ("Create", "Create",
                "Create a path from camera positions", 3)],
        default="Circular")
    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="Z")
    anim_tract = StringProperty(
        name="Animation streamline",
        description="Tract to animate",
        default="")
    spline_index = IntProperty(
        name="streamline index",
        description="index of the streamline to animate",
        min=0,
        default=0)
    anim_curve = StringProperty(
        name="Animation curves",
        description="Curve to animate",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        preset = nb.presets[self.index_presets]
        anim = preset.animations[self.index_animations]

        if self.pathtype == "Circular":
            name = "CP_%s" % (self.axis)
        elif self.pathtype == "Streamline":
            name = "CP_%s_%05d" % (self.anim_tract, self.spline_index)
        elif self.pathtype == "Select":
            name = "CP_%s" % (anim.anim_curve)
        elif self.pathtype == "Create":
            name = "CP_%s" % ("fromCam")

        ca = [nb.campaths]
        name = self.name or name
        name = nb_ut.check_name(name, "", ca)
        fun = eval("self.campath_%s" % self.pathtype.lower())
        campath, info = fun(name)

        if campath is not None:
            campath.hide_render = True
            campath.parent = bpy.data.objects[preset.name]
            nb_im.add_campath_to_collection(name)
            infostring = 'added camera path "%s" to preset "%s"'
            info = [infostring % (name, preset.name)] + info

            infostring = 'switched "%s" camera path to "%s"'
            info += [infostring % (anim.name, campath.name)]
            anim.campaths_enum = campath.name
            status = "FINISHED"
        else:
            status = "CANCELLED"

        self.report({'INFO'}, '; '.join(info))

        return {status}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]
        self.index_animations = preset.index_animations
        anim = preset.animations[self.index_animations]
        self.pathtype = anim.pathtype
        self.axis = anim.axis
        self.anim_tract = anim.anim_tract
        self.spline_index = anim.spline_index
        self.anim_curve = anim.anim_curve

        return self.execute(context)

    def campath_circular(self, name):
        """Generate a circular trajectory from the camera position."""

        scn = bpy.context.scene
        nb = scn.nb

        preset = nb.presets[self.index_presets]
        cam = bpy.data.objects[preset.cameras[0].name]
        centre = bpy.data.objects[preset.centre]
        box = bpy.data.objects[preset.box]

        camview = cam.location * box.matrix_world

        if 'X' in self.axis:
            idx = 0
            rotation_offset = np.arctan2(camview[2], camview[1])
            r = np.sqrt(camview[1]**2 + camview[2]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, 0, r), (0, h, r), (0, -h, r)),
                      ((0, -r, 0), (0, -r, h), (0, -r, -h)),
                      ((0, 0, -r), (0, -h, -r), (0, h, -r)),
                      ((0, r, 0), (0, r, -h), (0, r, h))]
        elif 'Y' in self.axis:
            idx = 1
            rotation_offset = np.arctan2(camview[0], camview[2])
            r = np.sqrt(camview[0]**2 + camview[2]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, 0, r), (h, 0, r), (-h, 0, r)),
                      ((-r, 0, 0), (-r, 0, h), (-r, 0, -h)),
                      ((0, 0, -r), (-h, 0, -r), (h, 0, -r)),
                      ((r, 0, 0), (r, 0, -h), (r, 0, h))]
        elif 'Z' in self.axis:
            idx = 2
            rotation_offset = np.arctan2(camview[1], camview[0])
            r = np.sqrt(camview[0]**2 + camview[1]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, r, 0), (h, r, 0), (-h, r, 0)),
                      ((-r, 0, 0), (-r, h, 0), (-r, -h, 0)),
                      ((0, -r, 0), (-h, -r, 0), (h, -r, 0)),
                      ((r, 0, 0), (r, -h, 0), (r, h, 0))]

        ob = self.create_circle(name, coords=coords)

        ob.rotation_euler[idx] = rotation_offset
        ob.location = centre.location
        ob.location[idx] = camview[idx] + centre.location[idx]

        origin = mathutils.Vector(coords[0][0]) + centre.location
        o = "%s" % ', '.join('%.2f' % co for co in origin)
        infostring = 'created path around %s with radius %.2f starting at [%s]'
        info = [infostring % (self.axis, r, o)]

        return ob, info

    def campath_streamline(self, name):
        """Generate a curvilinear trajectory from a streamline."""

        scn = bpy.context.scene

        try:
            nb_ob = bpy.data.objects[self.anim_tract]
            spline = nb_ob.data.splines[self.spline_index]
        except KeyError:
            ob = None
            infostring = 'tract "%s:spline[%s]" not found'
        except IndexError:
            ob = None
            infostring = 'streamline "%s:spline[%s]" not found'
        else:
            curve = bpy.data.curves.new(name=name, type='CURVE')
            curve.dimensions = '3D'
            ob = bpy.data.objects.new(name, curve)
            scn.objects.link(ob)

            streamline = [point.co[0:3] for point in spline.points]
            nb_im.make_polyline_ob(curve, streamline)
            ob.matrix_world = nb_ob.matrix_world
            ob.select = True
            bpy.context.scene.objects.active = ob
            bpy.ops.object.transform_apply(location=False,
                                           rotation=False,
                                           scale=True)

            infostring = 'copied path from tract "%s:spline[%s]"'

        info = [infostring % (self.anim_tract, self.spline_index)]

        return ob, info

    def campath_select(self, name):
        """Generate a campath by copying it from a curve object."""

        scn = bpy.context.scene

        try:
            cubase = bpy.data.objects[self.anim_curve]
        except KeyError:
            ob = None
            infostring = 'curve "%s" not found'
        else:
            cu = cubase.data.copy()
            cu.name = name
            ob = bpy.data.objects.new(name, cu)
            scn.objects.link(ob)
            scn.update()
            ob.matrix_world = cubase.matrix_world
            ob.select = True
            bpy.context.scene.objects.active = ob
            bpy.ops.object.transform_apply(location=False,
                                           rotation=False,
                                           scale=True)
            infostring = 'copied camera path from "%s"'

        info = [infostring % self.anim_curve]

        return ob, info

    def campath_create(self, name):
        """Generate an empty trajectory."""

        scn = bpy.context.scene

        curve = bpy.data.curves.new(name=name, type='CURVE')
        curve.dimensions = '3D'
        ob = bpy.data.objects.new(name, curve)
        scn.objects.link(ob)

        infostring = 'created empty path'

        info = [infostring]

        return ob, info

    def create_circle(self, name, coords):
        """Create a bezier circle from a list of coordinates."""

        scn = bpy.context.scene

        cu = bpy.data.curves.new(name, type='CURVE')
        cu.dimensions = '3D'
        ob = bpy.data.objects.new(name, cu)
        scn.objects.link(ob)
        scn.objects.active = ob
        ob.select = True

        polyline = cu.splines.new('BEZIER')
        polyline.bezier_points.add(len(coords) - 1)
        for i, coord in enumerate(coords):
            polyline.bezier_points[i].co = coord[0]
            polyline.bezier_points[i].handle_left = coord[1]
            polyline.bezier_points[i].handle_right = coord[2]

        polyline.use_cyclic_u = True

        return ob


class DelCamPath(Operator):
    bl_idname = "nb.del_campath"
    bl_label = "Delete camera path"
    bl_description = "Delete a camera path"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        default="")
    index_presets = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        try:
            campath = bpy.data.objects[self.name]
            cu = bpy.data.curves[self.name]
        except KeyError:
            infostring = 'camera path curve "%s" not found'
        else:
            bpy.data.curves.remove(cu)
            bpy.data.objects.remove(campath)
            nb.campaths.remove(nb.campaths.find(self.name))
            nb.index_campaths = 0
            # TODO: find and reset all animations that use campath
            infostring = 'removed camera path curve "%s"'

        info = [infostring % self.name]

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]
        self.index_animations = preset.index_animations
        anim = preset.animations[self.index_animations]
        self.name = anim.campaths_enum

        return self.execute(context)


class ObjectListAN(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListCP(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        item_icon = "CANCEL"
        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            row = layout.row()
            row.prop(item, "co", text="cp", emboss=True, icon=item_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class MassIsRenderedAN(Menu):
    bl_idname = "nb.mass_is_rendered_AN"
    bl_label = "Animation Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_AN'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_AN'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_AN'


class MassIsRenderedCP(Menu):
    bl_idname = "nb.mass_is_rendered_CP"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_CP'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_CP'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_CP'


def update_name(self, context):
    """Update the name of a NeuroBlender collection item."""

    scn = context.scene
    nb = scn.nb

    def rename_voxelvolume(vvol):
        colls = [bpy.data.objects,
                 bpy.data.meshes,
                 bpy.data.materials,
                 bpy.data.textures,
                 bpy.data.images]
        bpy.data.objects[vvol.name_mem+"SliceBox"].name = vvol.name+"SliceBox"
        return colls

    def rename_group(coll, group):
        for item in group:
            if item.name.startswith(coll.name_mem):
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
        colls = [bpy.data.objects,
                 bpy.data.curves,
                 bpy.data.materials]

    elif colltype == "surfaces":
        # NOTE/TODO: ref to sphere
        colls = [bpy.data.objects,
                 bpy.data.meshes,
                 bpy.data.materials]

    elif colltype == "voxelvolumes":
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
            colls = []  # N/A
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

    elif colltype == "presets":
        colls = [bpy.data.objects]

    elif colltype == "cameras":  # not implemented via Panels
        colls = [bpy.data.objects,
                 bpy.data.cameras]  # animations?

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

    elif colltype == "campaths":  # not implemented via Panels
        colls = [bpy.data.objects,
                 bpy.data.curves]  # FollowPath constraints

    else:
        colls = []

    for coll in colls:
        coll[self.name_mem].name = self.name

    self.name_mem = self.name





def campaths_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(cp.name, cp.name, "List the camera paths", i)
             for i, cp in enumerate(nb.campaths)]

    return items


def campaths_enum_update(self, context):
    """Update the camera path."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]
    cam = bpy.data.objects[nb_preset.cameras[0].name]
    anim = nb_preset.animations[nb_preset.index_animations]

    if anim.animationtype == "CameraPath": # FIXME: overkill?
        cam_anims = [anim for anim in nb_preset.animations
                     if ((anim.animationtype == "CameraPath") &
                         (anim.is_rendered))]
        nb_rp.clear_camera_path_animations(cam, nb_preset.animations,
                                           [nb_preset.index_animations])
        nb_rp.create_camera_path_animations(cam, cam_anims)


def tracktype_enum_update(self, context):
    """Update the camera path constraints."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]
    cam = bpy.data.objects[nb_preset.cameras[0].name]
    centre = bpy.data.objects[nb_preset.centre]
    anim = nb_preset.animations[nb_preset.index_animations]

    cam_anims = [anim for anim in nb_preset.animations
                 if ((anim.animationtype == "CameraPath") &
                     (anim.is_rendered))]

    anim_blocks = [[anim.anim_block[0], anim.anim_block[1]]
                   for anim in cam_anims]

    timeline = nb_rp.generate_timeline(scn, cam_anims, anim_blocks)
    cnsTT = cam.constraints["TrackToCentre"]
    nb_rp.restrict_incluence_timeline(scn, cnsTT, timeline, group="TrackTo")

    # TODO: if not yet executed/exists
    cns = cam.constraints["FollowPath" + anim.campaths_enum]
    cns.use_curve_follow = anim.tracktype == "TrackPath"
    if anim.tracktype == 'TrackPath':
        cns.forward_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
    else:
        cns.forward_axis = 'TRACK_NEGATIVE_Y'
        cns.up_axis = 'UP_Z'


def direction_toggle_update(self, context):
    """Update the direction of animation on a curve."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]
    anim = nb_preset.animations[nb_preset.index_animations]

    try:
        campath = bpy.data.objects[anim.campaths_enum]
    except:
        pass
    else:
        animdata = campath.data.animation_data
        fcu = animdata.action.fcurves.find("eval_time")
        mod = fcu.modifiers[0]  # TODO: sloppy
        intercept, slope, _ = nb_rp.calculate_coefficients(campath, anim)
        mod.coefficients = (intercept, slope)


def tracts_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(tract.name, tract.name, "List the tracts", i)
             for i, tract in enumerate(nb.tracts)]

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


def timeseries_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    # FIXME: crash when commenting/uncommenting this
    aliases = {'T': 'tracts', 'S': 'surfaces', 'V': 'voxelvolumes'}
    try:
        coll = eval('nb.%s' % aliases[self.timeseries_object[0]])
        sgs = coll[self.timeseries_object[3:]].scalargroups
    except:
        items = []
    else:
#     sgs = find_ts_scalargroups(self)
        items = [(scalargroup.name, scalargroup.name, "List the timeseries", i)
                 for i, scalargroup in enumerate(sgs)]

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

    return items


def timeseries_object_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    nb_obs = ["%s: %s" % (l, ob.name)
              for l, coll in zip(['T', 'S', 'V'], [nb.tracts,
                                                   nb.surfaces,
                                                   nb.voxelvolumes])
              for ob in coll if len(ob.scalargroups)]
    items = [(obname, obname, "List the objects", i)
             for i, obname in enumerate(nb_obs)]

    return items


class AnimationProperties(PropertyGroup):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        update=update_name)
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
        items=[("CameraPath", "Trajectory", "Animate a camera trajectory", 1),
               ("Slices", "Slices", "Animate voxelvolume slices", 2),
               ("TimeSeries", "Time series", "Play a time series", 3)])

    frame_start = IntProperty(
        name="startframe",
        description="first frame of the animation",
        min=0,
        default=1,
        update=campaths_enum_update)
    frame_end = IntProperty(
        name="endframe",
        description="last frame of the animation",
        min=1,
        default=100,
        update=campaths_enum_update)
    repetitions = FloatProperty(
        name="repetitions",
        description="number of repetitions",
        default=1,
        update=campaths_enum_update)
    offset = FloatProperty(
        name="offset",
        description="offset",
        default=0,
        update=campaths_enum_update)

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

    campaths_enum = EnumProperty(
        name="Camera trajectory",
        description="Choose the camera trajectory",
        items=campaths_enum_callback,
        update=campaths_enum_update)
    tracktype = EnumProperty(
        name="Tracktype",
        description="Camera rotation options",
        items=[("TrackNone", "None", "Use the camera rotation property", 0),
               ("TrackCentre", "Centre", "Track the preset centre", 1),
               ("TrackPath", "Path", "Orient along the trajectory", 2)],
        default="TrackCentre",
        update=tracktype_enum_update)
    pathtype = EnumProperty(
        name="Pathtype",
        description="Trajectory types for the camera animation",
        items=[("Circular", "Circular",
                "Circular trajectory from camera position", 0),
               ("Streamline", "Streamline",
                "Curvilinear trajectory from a streamline", 1),
               ("Select", "Select",
                "Curvilinear trajectory from curve", 2),
               ("Create", "Create",
                "Create a path from camera positions", 3)],
        default="Circular")

    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="Z")

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

    anim_surface = EnumProperty(
        name="Animation surface",
        description="Select surface to animate",
        items=surfaces_enum_callback)
    anim_timeseries = EnumProperty(
        name="Animation timeseries",
        description="Select timeseries to animate",
        items=timeseries_enum_callback)

    anim_voxelvolume = EnumProperty(
        name="Animation voxelvolume",
        description="Select voxelvolume to animate",
        items=voxelvolumes_enum_callback)
    sliceproperty = EnumProperty(
        name="Property to animate",
        description="Select property to animate",
        items=[("Thickness", "Thickness", "Thickness", 0),
               ("Position", "Position", "Position", 1),
               ("Angle", "Angle", "Angle", 2)],
        default="Position")

    timeseries_object = EnumProperty(
        name="Object",
        description="Select object to animate",
        items=timeseries_object_enum_callback)

    cnsname = StringProperty(
        name="Constraint Name",
        description="Name of the campath constraint",
        default="")

    # TODO: TimeSeries props


# class CamPointProperties(PropertyGroup):
#
#     location = FloatVectorProperty(
#         name="campoint",
#         description="...",
#         default=[0.0, 0.0, 0.0],
#         subtype="TRANSLATION")


class CamPathProperties(PropertyGroup):
    """Properties of a camera path."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        update=update_name)
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
#
#     bezier_points = CollectionProperty(
#         type=CamPointProperties,
#         name="campoints",
#         description="The collection of camera positions")
#     index_bezier_points = IntProperty(
#         name="campoint index",
#         description="index of the campoints collection",
#         default=0,
#         min=0)
