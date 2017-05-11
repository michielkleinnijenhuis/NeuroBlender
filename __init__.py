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


"""The NeuroBlender main module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
"""


import os
import sys
from shutil import copy
import re
import numpy as np
import mathutils

if "bpy" in locals():
    import imp
    imp.reload(nb_an)
    imp.reload(nb_cm)
    imp.reload(nb_im)
    imp.reload(nb_ma)
    imp.reload(nb_ol)
    imp.reload(nb_rp)
    imp.reload(nb_sp)
    imp.reload(nb_se)
    imp.reload(nb_ut)
else:
    import bpy
    from bpy.types import (Operator,
                           OperatorFileListElement,
                           UIList,
                           Menu)
    from bpy.props import (StringProperty,
                           CollectionProperty,
                           EnumProperty,
                           IntProperty,
                           PointerProperty)
    from bpy_extras.io_utils import ExportHelper

    from . import (animations as nb_an,
                   colourmaps as nb_cm,
                   imports as nb_im,
                   materials as nb_ma,
                   overlays as nb_ol,
                   panels as nb_pa,
                   properties as nb_pr,
                   renderpresets as nb_rp,
                   scenepresets as nb_sp,
                   settings as nb_se,
                   utils as nb_ut)


bl_info = {
    "name": "NeuroBlender",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 6),
    "blender": (2, 78, 4),
    "location": "Properties -> Scene -> NeuroBlender",
    "description": "Create artwork from neuroscientific data.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}


class ObjectListL1(UIList):

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

            if bpy.context.scene.nb.settingprops.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListL2(UIList):

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

            if bpy.context.scene.nb.settingprops.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListL3(UIList):

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

            if bpy.context.scene.nb.settingprops.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.enabled = False
                col.prop(item, "value", text="", emboss=False)

                col = layout.column()
                col.alignment = "RIGHT"
                col.enabled = False
                col.prop(item, "colour", text="")

                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListOperations(Operator):
    bl_idname = "nb.oblist_ops"
    bl_label = "Objectlist operations"
    bl_options = {"REGISTER", "UNDO"}

    action = EnumProperty(
        items=(('UP_L1', "UpL1", ""),
               ('DOWN_L1', "DownL1", ""),
               ('REMOVE_L1', "RemoveL1", ""),
               ('UP_L2', "UpL2", ""),
               ('DOWN_L2', "DownL2", ""),
               ('REMOVE_L2', "RemoveL2", ""),
               ('UP_L3', "UpL3", ""),
               ('DOWN_L3', "DownL3", ""),
               ('REMOVE_L3', "RemoveL3", ""),
               ('UP_PL', "UpPL", ""),
               ('DOWN_PL', "DownPL", ""),
               ('REMOVE_PL', "RemovePL", ""),
               ('UP_CP', "UpCP", ""),
               ('DOWN_CP', "DownCP", ""),
               ('REMOVE_CP', "RemoveCP", ""),
               ('UP_AN', "UpAN", ""),
               ('DOWN_AN', "DownAN", ""),
               ('REMOVE_AN', "RemoveAN", "")))

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    type = StringProperty(
        name="type",
        description="Specify object type",
        default="")
    index = IntProperty(
        name="index",
        description="Specify object index",
        default=-1)
    name = StringProperty(
        name="name",
        description="Specify object name",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        collection, data, nb_ob = self.get_collection(context)

        try:
            collection[self.index]
        except IndexError:
            pass
        else:
            if self.action.startswith('REMOVE'):
                info = ['removed %s' % (collection[self.index].name)]
                info += self.remove_items(nb, data, collection, nb_ob)
                self.report({'INFO'}, '; '.join(info))
            elif (self.action.startswith('DOWN') and
                  self.index < len(collection) - 1):
                collection.move(self.index, self.index + 1)
                exec("%s.index_%s += 1" % (data, self.type))
            elif self.action.startswith('UP') and self.index >= 1:
                collection.move(self.index, self.index - 1)
                exec("%s.index_%s -= 1" % (data, self.type))

        if self.type == "voxelvolumes":
            self.update_voxelvolume_drivers(nb)

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        if self.action.endswith('_L1'):
            nb_ob = nb_ut.active_nb_object()[0]
            self.type = nb.objecttype
            self.name = nb_ob.name
            self.index = eval("nb.%s.find(self.name)" % self.type)
            self.data_path = nb_ob.path_from_id()
        elif self.action.endswith('_L2'):
            nb_ob = nb_ut.active_nb_object()[0]
            nb_ov = nb_ut.active_nb_overlay()[0]
            self.type = nb.overlaytype
            self.name = nb_ov.name
            self.index = eval("nb_ob.%s.find(self.name)" % self.type)
            self.data_path = nb_ov.path_from_id()
        elif self.action.endswith('_L3'):
            nb_ob = nb_ut.active_nb_object()[0]
            nb_ov = nb_ut.active_nb_overlay()[0]
            nb_it = nb_ut.active_nb_overlayitem()[0]
            self.type = nb.overlaytype.replace("groups", "s")
            self.name = nb_it.name
            self.index = eval("nb_ov.%s.find(self.name)" % self.type)
            self.data_path = nb_it.path_from_id()
        elif self.action.endswith('_PL'):
            preset = eval("nb.presets[%d]" % nb.index_presets)
            light = preset.lights[preset.index_lights]
            self.type = "lights"
            self.name = light.name
            self.index = preset.index_lights
            self.data_path = light.path_from_id()
        elif self.action.endswith('_AN'):
            preset = eval("nb.presets[%d]" % nb.index_presets)
            animation = preset.animations[preset.index_animations]
            self.type = "animations"
            self.name = animation.name
            self.index = preset.index_animations
            self.data_path = animation.path_from_id()

        return self.execute(context)

    def get_collection(self, context):

        try:
            self.data_path = eval("%s.path_from_id()" % self.data_path)
        except SyntaxError:
            self.report({'INFO'}, 'empty data path')
#             # try to construct data_path from type, index, name?
#             if type in ['tracts', 'surfaces', 'voxelvolumes']:
#                 self.data_path = ''
            return {"CANCELLED"}
        except NameError:
            self.report({'INFO'}, 'invalid data path: %s' % self.data_path)
            return {"CANCELLED"}

        dp_split = re.findall(r"[\w']+", self.data_path)
        dp_indices = re.findall(r"(\[\d+\])", self.data_path)
        collection = eval(self.data_path.strip(dp_indices[-1]))
        coll_path = collection.path_from_id()
        data = '.'.join(coll_path.split('.')[:-1])

        if self.index == -1:
            self.index = int(dp_split[-1])
        if not self.type:
            self.type = dp_split[-2]
        if not self.name:
            self.name = collection[self.index].name

        nb_ob = eval('.'.join(self.data_path.split('.')[:2]))

        return collection, data, nb_ob

    def remove_items(self, nb, data, collection, nb_ob):
        """Remove items from NeuroBlender."""

        info = []

        name = collection[self.index].name

        if self.action.endswith('_L1'):
            try:
                ob = bpy.data.objects[name]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % name]
            else:
                if self.type == 'voxelvolumes':
                    self.remove_material(ob, name)
                    try:
                        slicebox = bpy.data.objects[name+"SliceBox"]
                    except KeyError:
                        infostring = 'slicebox "%s" not found'
                        info += [infostring % name+"SliceBox"]
                    else:
                        for ms in ob.material_slots:
                            self.remove_material(ob, ms.name)
                        bpy.data.objects.remove(slicebox)
                # remove all children
                fun = eval("self.remove_%s_overlays" % self.type)
                fun(nb_ob, ob)
                # remove the object itself
                bpy.data.objects.remove(ob)
        elif self.action.endswith('_PL'):
            try:
                ob = bpy.data.objects[name]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % name]
            else:
                bpy.data.objects.remove(ob)
        elif self.action.endswith('_AN'):
            nb_preset = eval("nb.presets[%d]" % nb.index_presets)
            anim = nb_preset.animations[nb_preset.index_animations]
            fun = eval("self.remove_animations_%s" %
                       anim.animationtype.lower())
            fun(nb_preset.animations, self.index)
        else:
            ob = bpy.data.objects[nb_ob.name]
            fun = eval("self.remove_%s_%s" % (nb.objecttype, self.type))
            fun(collection[self.index], ob)

        collection.remove(self.index)
        exec("%s.index_%s -= 1" % (data, self.type))

        return info

    def remove_tracts_overlays(self, tract, ob):
        """Remove tract scalars and labels."""

        for sg in tract.scalargroups:
            self.remove_tracts_scalargroups(sg, ob)

    def remove_surfaces_overlays(self, surface, ob):
        """Remove surface scalars, labels and borders."""

        for sg in surface.scalargroups:
            self.remove_surfaces_scalargroups(sg, ob)
        for lg in surface.labelgroups:
            self.remove_surfaces_labelgroups(lg, ob)
        for bg in surface.bordergroups:
            self.remove_surfaces_bordergroups(bg, ob)

    def remove_voxelvolumes_overlays(self, nb_ob, ob):
        """Remove voxelvolume scalars and labels."""

        for sg in nb_ob.scalargroups:
            self.remove_voxelvolumes_scalargroups(sg, ob)
        for lg in nb_ob.labelgroups:
            self.remove_voxelvolumes_labelgroups(lg, ob)

    def remove_tracts_scalargroups(self, scalargroup, ob):
        """Remove scalar overlay from tract."""

        for scalar in scalargroup.scalars:
            for i, _ in enumerate(ob.data.splines):
                splname = scalar.name + '_spl' + str(i).zfill(8)
                self.remove_material(ob, splname)
                self.remove_image(ob, splname)

    def remove_surfaces_scalargroups(self, scalargroup, ob):  # TODO: check
        """Remove scalar overlay from a surface."""

        vgs = ob.vertex_groups
        vcs = ob.data.vertex_colors
        self.remove_vertexcoll(vgs, scalargroup.name)
        self.remove_vertexcoll(vcs, scalargroup.name)
        self.remove_material(ob, scalargroup.name)
        # TODO: remove colourbars

    def remove_surfaces_labelgroups(self, labelgroup, ob):
        """Remove label group."""

        for label in labelgroup.labels:
            self.remove_surfaces_labels(label, ob)

    def remove_surfaces_labels(self, label, ob):
        """Remove label from a labelgroup."""

        vgs = ob.vertex_groups
        self.remove_vertexcoll(vgs, label.name)
        self.remove_material(ob, label.name)

    def remove_surfaces_bordergroups(self, bordergroup, ob):
        """Remove a bordergroup overlay from a surface."""

        for border in bordergroup.borders:
            self.remove_surfaces_borders(border, ob)
        bg_ob = bpy.data.objects.get(bordergroup.name)
        bpy.data.objects.remove(bg_ob)

    def remove_surfaces_borders(self, border, ob):
        """Remove border from a bordergroup."""

        self.remove_material(ob, border.name)
        b_ob = bpy.data.objects[border.name]
        bpy.data.objects.remove(b_ob)

    def remove_voxelvolumes_scalargroups(self, scalargroup, ob):
        """Remove scalar overlay from a voxelvolume."""

        self.remove_material(ob, scalargroup.name)
        sg_ob = bpy.data.objects[scalargroup.name]
        bpy.data.objects.remove(sg_ob)
        sg_ob = bpy.data.objects[scalargroup.name + 'SliceBox']
        bpy.data.objects.remove(sg_ob)

    def remove_voxelvolumes_labelgroups(self, labelgroup, ob):
        """Remove labelgroup overlay from a voxelvolume."""

        self.remove_material(ob, labelgroup.name)
        lg_ob = bpy.data.objects[labelgroup.name]
        bpy.data.objects.remove(lg_ob)
        lg_ob = bpy.data.objects[labelgroup.name + 'SliceBox']
        bpy.data.objects.remove(lg_ob)

    def remove_voxelvolumes_labels(self, label, ob):
        """Remove label from a labelgroup."""

        self.remove_material(ob, label.name)
        l_ob = bpy.data.objects[label.name]
        bpy.data.objects.remove(l_ob)

    def remove_material(self, ob, name):
        """Remove a material."""

        ob_mats = ob.data.materials
        mat_idx = ob_mats.find(name)
        if mat_idx != -1:
            ob_mats.pop(mat_idx, update_data=True)

        self.remove_data(bpy.data.materials, name)

    def remove_image(self, ob, name):
        """Remove an image."""

        self.remove_data(bpy.data.images, name)

    def remove_data(self, coll, name):
        """Remove data if it is only has a single user."""

        item = coll.get(name)
        if (item is not None) and (item.users < 2):
            item.user_clear()
            coll.remove(item)

    def remove_vertexcoll(self, coll, name):
        """Remove vertexgroup or vertex_color attribute"""

        mstring = '{}.vol....'.format(name)
        for item in coll:
            if re.match(mstring, item.name) is not None:
                coll.remove(item)

    def update_voxelvolume_drivers(self, nb):
        """Update the data path in the drivers of voxelvolumes slicers."""

        for i, vvol in enumerate(nb.voxelvolumes):
            slicebox = bpy.data.objects[vvol.name+"SliceBox"]
            for dr in slicebox.animation_data.drivers:
                for var in dr.driver.variables:
                    for tar in var.targets:
                        dp = tar.data_path
                        idx = 16
                        if dp.index("nb.voxelvolumes[") == 0:
                            tar.data_path = dp[:idx] + "%d" % i + dp[idx + 1:]

    def remove_animations_camerapath(self, anims, index):
        """Remove camera path animation."""

        cam = bpy.data.objects['Cam']
        nb_rp.clear_camera_path_animation(cam, anims[index])
        cam_anims = [anim for i, anim in enumerate(anims)
                     if ((anim.animationtype == "CameraPath") &
                         (anim.is_rendered) &
                         (i != index))]
        nb_rp.update_cam_constraints(cam, cam_anims)

    def remove_animations_slices(self, anims, index):
        """Remove slice animation."""

        anim = anims[index]
        vvol = bpy.data.objects[anim.anim_voxelvolume]
        vvol.animation_data_clear()

    def remove_animations_timeseries(self, anims, index):
        """Remove timeseries animation."""

        pass  # TODO


class MassIsRenderedL1(Menu):
    bl_idname = "nb.mass_is_rendered_L1"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L1'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L1'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L1'


class MassIsRenderedL2(Menu):
    bl_idname = "nb.mass_is_rendered_L2"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L2'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L2'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L2'


class MassIsRenderedL3(Menu):
    bl_idname = "nb.mass_is_rendered_L3"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L3'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L3'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L3'


class MassSelect(Operator):
    bl_idname = "nb.mass_select"
    bl_label = "Mass select"
    bl_description = "Select/Deselect/Invert rendered objects/overlays"
    bl_options = {"REGISTER"}

    action = EnumProperty(
        items=(('SELECT_L1', "Select_L1", ""),
               ('DESELECT_L1', "Deselect_L1", ""),
               ('INVERT_L1', "Invert_L1", ""),
               ('SELECT_L2', "Select_L2", ""),
               ('DESELECT_L2', "Deselect_L2", ""),
               ('INVERT_L2', "Invert_L2", ""),
               ('SELECT_L3', "Select_L3", ""),
               ('DESELECT_L3', "Deselect_L3", ""),
               ('INVERT_L3', "Invert_L3", ""),
               ('SELECT_PL', "Select_PL", ""),
               ('DESELECT_PL', "Deselect_PL", ""),
               ('INVERT_PL', "Invert_PL", ""),
               ('SELECT_CP', "Select_CP", ""),
               ('DESELECT_CP', "Deselect_CP", ""),
               ('INVERT_CP', "Invert_CP", ""),
               ('SELECT_AN', "Select_AN", ""),
               ('DESELECT_AN', "Deselect_AN", ""),
               ('INVERT_AN', "Invert_AN", "")))

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    type = StringProperty(
        name="type",
        description="Specify object type",
        default="")
    index = IntProperty(
        name="index",
        description="Specify object index",
        default=-1)
    name = StringProperty(
        name="name",
        description="Specify object name",
        default="")

    invoke = ObjectListOperations.invoke
    get_collection = ObjectListOperations.get_collection

    def execute(self, context):

        collection = self.get_collection(context)[0]

        for item in collection:
            if self.action.startswith('SELECT'):
                item.is_rendered = True
            elif self.action.startswith('DESELECT'):
                item.is_rendered = False
            elif self.action.startswith('INVERT'):
                item.is_rendered = not item.is_rendered

        return {"FINISHED"}


class SwitchToMainScene(Operator):
    bl_idname = "nb.switch_to_main"
    bl_label = "Switch to main"
    bl_description = "Switch to main NeuroBlender scene to import"
    bl_options = {"REGISTER"}

    def execute(self, context):

        context.window.screen.scene = bpy.data.scenes["Scene"]

        return {"FINISHED"}


class SaveBlend(Operator, ExportHelper):
    bl_idname = "nb.save_blend"
    bl_label = "Save blend file"
    bl_description = "Prompt to save a blend file"
    bl_options = {"REGISTER"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filename_ext = StringProperty(subtype="NONE")

    def execute(self, context):

        bpy.ops.wm.save_as_mainfile(filepath=self.properties.filepath)

        return {"FINISHED"}

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.nb = PointerProperty(type=nb_pr.NeuroBlenderProperties)


def unregister():  # TODO: unregister handlers
    bpy.utils.unregister_module(__name__)
    del bpy.types.Scene.nb


if __name__ == "__main__":
    register()
