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


"""The NeuroBlender scene presets module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements the scene building system.
"""

import mathutils

import bpy
from bpy.types import (Operator,
                       UIList,
                       Menu)
from bpy.props import (StringProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       IntProperty)

from . import (renderpresets as nb_rp,
               utils as nb_ut)


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
