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


"""The NeuroBlender scene presets module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements the scene building system for NeuroBlender.
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

from . import animations as nb_an
from . import base as nb_ba
from . import beautify as nb_be
from . import colourmaps as nb_cm
from . import imports as nb_im
from . import materials as nb_ma
from . import overlays as nb_ol
from . import panels as nb_pa
from . import renderpresets as nb_rp
# from . import scenepresets as nb_sp
from . import settings as nb_se
from . import utils as nb_ut

# from .renderpresets import (get_render_objects,
#                             get_brainbounds,
#                             scene_preset_init,
#                             create_light,
#                             scene_preset)  # create_table, cam_view_update
# from .utils import (check_name,
#                     add_item,
#                     update_name)
# from .animations import AnimationProperties
# from .materials import (material_update,
#                         material_enum_update)

# =========================================================================== #


class ResetPresetCentre(Operator):
    bl_idname = "nb.reset_presetcentre"
    bl_label = "Reset preset centre"
    bl_description = "Revert location changes to preset centre"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = nb_rp.get_render_objects(nb)
        centre_location = nb_rp.get_brainbounds(obs)[0]

        nb_preset = nb.presets[nb.index_presets]
        name = nb_preset.centre
        centre = bpy.data.objects[name]
        centre.location = centre_location

        infostring = 'reset location of preset "%s"'
        info = [infostring % nb_preset.name]
        infostring = 'location is now "%s"'
        info += [infostring % ' '.join('%.2f' % l for l in centre_location)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class ResetPresetDims(Operator):
    bl_idname = "nb.reset_presetdims"
    bl_label = "Recalculate scene dimensions"
    bl_description = "Recalculate scene dimension"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = nb_rp.get_render_objects(nb)
        dims = nb_rp.get_brainbounds(obs)[1]

        nb_preset = nb.presets[nb.index_presets]
        name = nb_preset.centre
        centre = bpy.data.objects[name]
        centre.scale = 0.5 * mathutils.Vector(dims)

        nb.presets[nb.index_presets].dims = dims

        infostring = 'reset dimensions of preset "%s"'
        info = [infostring % nb_preset.name]
        infostring = 'dimensions are now "%s"'
        info += [infostring % ' '.join('%.2f' % d for d in dims)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class AddPreset(Operator):
    bl_idname = "nb.add_preset"
    bl_label = "New preset"
    bl_description = "Create a new preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="Preset")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.presets]
        name = nb_ut.check_name(self.name, "", ca, firstfill=1)

        nb_rp.scene_preset_init(name)
        nb.presets_enum = name

        infostring = 'added preset "%s"'
        info = [infostring % name]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class DelPreset(Operator):
    bl_idname = "nb.del_preset"
    bl_label = "Delete preset"
    bl_description = "Delete a preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="")
    index = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        info = []

        if self.name:  # got here through cli
            try:
                nb.presets[self.name]
            except KeyError:
                infostring = 'no preset with name "%s"'
                info = [infostring % self.name]
                self.report({'INFO'}, info[0])
                return {"CANCELLED"}
            else:
                self.index = nb.presets.find(self.name)
        else:  # got here through invoke
            self.name = nb.presets[self.index].name

        info = self.delete_preset(nb.presets[self.index], info)
        nb.presets.remove(self.index)
        nb.index_presets -= 1
        infostring = 'removed preset "%s"'
        info = [infostring % self.name] + info

        try:
            name = nb.presets[0].name
        except IndexError:
            infostring = 'all presets have been removed'
            info += [infostring]
        else:
            nb.presets_enum = name
            infostring = 'preset is now "%s"'
            info += [infostring % name]

        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index = nb.index_presets
        self.name = ""

        return self.execute(context)

    def delete_preset(self, nb_preset, info=[]):
        """Delete a preset."""

        # unlink all objects from the rendering scenes
        for s in ['_cycles', '_internal']:
            sname = nb_preset.name + s
            try:
                scn = bpy.data.scenes[sname]
            except KeyError:
                infostring = 'scene "%s" not found'
                info += [infostring % sname]
            else:
                for ob in scn.objects:
                    scn.objects.unlink(ob)
                bpy.data.scenes.remove(scn)

        # delete all preset objects and data
        ps_obnames = [nb_ob.name
                      for nb_coll in [nb_preset.cameras,
                                      nb_preset.lights,
                                      nb_preset.tables]
                      for nb_ob in nb_coll]
        ps_obnames += [nb_preset.lightsempty,
                       nb_preset.box,
                       nb_preset.centre,
                       nb_preset.name]
        for ps_obname in ps_obnames:
            try:
                ob = bpy.data.objects[ps_obname]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % ps_obname]
            else:
                bpy.data.objects.remove(ob)

        for ps_cam in nb_preset.cameras:
            try:
                cam = bpy.data.cameras[ps_cam.name]
            except KeyError:
                infostring = 'camera "%s" not found'
                info += [infostring % ps_cam.name]
            else:
                bpy.data.cameras.remove(cam)

        for ps_lamp in nb_preset.lights:
            try:
                lamp = bpy.data.lamps[ps_lamp.name]
            except KeyError:
                infostring = 'lamp "%s" not found'
                info += [infostring % ps_lamp.name]
            else:
                bpy.data.lamps.remove(lamp)

        for ps_mesh in nb_preset.tables:
            try:
                mesh = bpy.data.meshes[ps_mesh.name]
            except KeyError:
                infostring = 'mesh "%s" not found'
                info += [infostring % ps_mesh.name]
            else:
                bpy.data.meshes.remove(mesh)

        # TODO:
        # delete animations from objects
        # delete colourbars
        # delete campaths?

        return info


class AddLight(Operator):
    bl_idname = "nb.import_lights"
    bl_label = "New light"
    bl_description = "Create a new light"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)
    name = StringProperty(
        name="Name",
        description="Specify a name for the light",
        default="Light")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    type = EnumProperty(
        name="Light type",
        description="type of lighting",
        items=[("PLANE", "PLANE", "PLANE", 1),
               ("POINT", "POINT", "POINT", 2),
               ("SUN", "SUN", "SUN", 3),
               ("SPOT", "SPOT", "SPOT", 4),
               ("HEMI", "HEMI", "HEMI", 5),
               ("AREA", "AREA", "AREA", 6)],
        default="SPOT")
    colour = FloatVectorProperty(
        name="Colour",
        description="Colour of the light",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    strength = FloatProperty(
        name="Strength",
        description="Strength of the light",
        default=1,
        min=0)
    size = FloatVectorProperty(
        name="Size",
        description="Relative size of the plane light (to bounding box)",
        size=2,
        default=[1.0, 1.0])
    location = FloatVectorProperty(
        name="Location",
        description="",
        default=[3.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[self.index]
        preset = bpy.data.objects[nb_preset.name]
        centre = bpy.data.objects[nb_preset.centre]
        box = bpy.data.objects[nb_preset.box]
        lights = bpy.data.objects[nb_preset.lightsempty]

        ca = [nb_preset.lights]
        name = nb_ut.check_name(self.name, "", ca)

        lp = {'name': name,
              'type': self.type,
              'size': self.size,
              'colour': self.colour,
              'strength': self.strength,
              'location': self.location}
        nb_light = nb_ut.add_item(nb_preset, "lights", lp)
        nb_rp.create_light(preset, centre, box, lights, lp)

        infostring = 'added light "%s" in preset "%s"'
        info = [infostring % (name, nb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index = nb.index_presets

        return self.execute(context)


class ScenePreset(Operator):
    bl_idname = "nb.scene_preset"
    bl_label = "Load scene preset"
    bl_description = "Setup up camera and lighting for this brain"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        nb_rp.scene_preset()

        return {"FINISHED"}


class ObjectListPL(UIList):

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


class MassIsRenderedPL(Menu):
    bl_idname = "nb.mass_is_rendered_PL"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_PL'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_PL'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_PL'


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


def material_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    if context.scene.nb.engine.startswith("BLENDER"):
        CR2BR(mat)


def material_enum_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    link_innode(mat, self.colourtype)





def cam_view_enum_XX_update(self, context):
    """Set the camview property from enum options."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]

    lud = {'Centre': 0,
           'Left': -1, 'Right': 1,
           'Anterior': 1, 'Posterior': -1,
           'Superior': 1, 'Inferior': -1}

    LR = lud[self.cam_view_enum_LR]
    AP = lud[self.cam_view_enum_AP]
    IS = lud[self.cam_view_enum_IS]

    cv_unit = mathutils.Vector([LR, AP, IS]).normalized()

    self.cam_view = list(cv_unit * self.cam_distance)

    cam = bpy.data.objects[self.name]
    centre = bpy.data.objects[nb_preset.centre]

#     cam_view_update(cam, centre, self.cam_view, nb_preset.dims)
    cam.location = self.cam_view

    scn.frame_set(0)


def presets_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = [(ps.name, ps.name, "List the presets", i)
             for i, ps in enumerate(self.presets)]

    return items


def presets_enum_update(self, context):
    """Update the preset enum."""

    scn = context.scene
    nb = scn.nb

    self.index_presets = self.presets.find(self.presets_enum)
    preset = self.presets[self.index_presets]
    scn.camera = bpy.data.objects[preset.cameras[0].name]
    # TODO:
    # switch cam view etc


def trackobject_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = [(ob.name, ob.name, "List all objects", i+1)
             for i, ob in enumerate(bpy.data.objects)]
    items.insert(0, ("None", "None", "None", 0))

    return items


def trackobject_enum_update(self, context):
    """Update the camera."""

    # TODO: evaluate against animations
    scn = context.scene
    nb = scn.nb

    preset = nb.presets[nb.index_presets]
    cam = bpy.data.objects[self.name]
    cns = cam.constraints["TrackToCentre"]
    if self.trackobject == "None":
        cns.mute = True
    else:
        try:
            cns.mute = False
            cns.target = bpy.data.objects[self.trackobject]
        except KeyError:
            infostring = "Object {} not found: disabling tracking"
            print(infostring.format(self.trackobject))


def light_update(self, context):
    """Update light."""

    scn = context.scene
    nb = scn.nb

    light_ob = bpy.data.objects[self.name]

    light_ob.hide = not self.is_rendered
    light_ob.hide_render = not self.is_rendered

    light = bpy.data.lamps[self.name]

    light.type = self.type

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


class CameraProperties(PropertyGroup):
    """Properties of cameras."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera",
        update=update_name)
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
        default="Right",
        items=[("Left", "L", "Left", 0),
               ("Centre", "C", "Centre", 1),
               ("Right", "R", "Right", 2)],
        update=cam_view_enum_XX_update)

    cam_view_enum_AP = EnumProperty(
        name="Camera AP viewpoint",
        description="Choose a AP position for the camera",
        default="Anterior",
        items=[("Anterior", "A", "Anterior", 0),
               ("Centre", "C", "Centre", 1),
               ("Posterior", "P", "Posterior", 2)],
        update=cam_view_enum_XX_update)

    cam_view_enum_IS = EnumProperty(
        name="Camera IS viewpoint",
        description="Choose a IS position for the camera",
        default="Superior",
        items=[("Inferior", "I", "Inferior", 0),
               ("Centre", "C", "Centre", 1),
               ("Superior", "S", "Superior", 2)],
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


class LightsProperties(PropertyGroup):
    """Properties of light."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the lights",
        update=update_name)
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
        items=[("PLANE", "PLANE", "PLANE", 1),
               ("POINT", "POINT", "POINT", 2),
               ("SUN", "SUN", "SUN", 3),
               ("SPOT", "SPOT", "SPOT", 4),
               ("HEMI", "HEMI", "HEMI", 5),
               ("AREA", "AREA", "AREA", 6)],
        default="SPOT",
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


class TableProperties(PropertyGroup):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the table",
        update=update_name)
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
        description="Indicates if the overlay is rendered",
        default=False,
        update=table_update)
    beautified = BoolProperty(
        name="Beautify",
        description="",
        default=True)

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


class PresetProperties(PropertyGroup):
    """Properties of a preset."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
#     filepath = StringProperty(
#         name="Filepath",
#         description="The filepath to the preset")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="CAMERA_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the preset passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the preset is rendered",
        default=True)

    centre = StringProperty(
        name="Centre",
        description="Scene centre",
        default="PresetCentre")
    box = StringProperty(
        name="Box",
        description="Scene box",
        default="PresetBox")
    cam = StringProperty(
        name="Camera",
        description="Scene camera",
        default="PresetCam")
    lightsempty = StringProperty(
        name="LightsEmpty",
        description="Scene lights empty",
        default="PresetLights")
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
        min=0)
    lights = CollectionProperty(
        type=LightsProperties,
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
    animations = CollectionProperty(
        type=nb_an.AnimationProperties,
        name="animations",
        description="The collection of animations")
    index_animations = IntProperty(
        name="animation index",
        description="index of the animations collection",
        default=0,
        min=0)

    lights_enum = EnumProperty(
        name="Light switch",
        description="switch between lighting modes",
        items=[("Key", "Key", "Use Key lighting only", 1),
               ("Key-Back-Fill", "Key-Back-Fill",
                "Use Key-Back-Fill lighting", 2),
               ("Free", "Free", "Set up manually", 3)],
        default="Key")

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
