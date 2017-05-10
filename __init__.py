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


"""The NeuroBlender main module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
"""


# =========================================================================== #


import os
import sys
from shutil import copy
import re
import numpy as np
import mathutils

if "bpy" in locals():
    import imp
    imp.reload(nb_an)
    imp.reload(nb_ba)
    imp.reload(nb_be)
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
    from bpy.app.handlers import persistent
    from bpy_extras.io_utils import ImportHelper, ExportHelper
    from bl_operators.presets import AddPresetBase, ExecutePreset

    from . import (animations as nb_an,
                   base as nb_ba,
                   beautify as nb_be,
                   colourmaps as nb_cm,
                   imports as nb_im,
                   materials as nb_ma,
                   overlays as nb_ol,
                   panels as nb_pa,
                   renderpresets as nb_rp,
                   scenepresets as nb_sp,
                   settings as nb_se,
                   utils as nb_ut)

# from .colourmaps import managecmap_update
# from .scenepresets import (PresetProperties,
#                            presets_enum_callback,
#                            presets_enum_update)
# from .settings import (esp_path_update,
#                        mode_enum_update,
#                        engine_update)
# from .renderpresets import (clear_camera_path_animation,
#                             update_cam_constraints)
# from .utils import (active_nb_object,
#                     active_nb_overlay,
#                     active_nb_overlayitem)
# from .animations import CamPathProperties
# from .overlays import overlay_enum_callback
# from .base import (TractProperties,
#                    SurfaceProperties,
#                    VoxelvolumeProperties)


# =========================================================================== #


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


# =========================================================================== #


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

            if bpy.context.scene.nb.advanced:
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

            if bpy.context.scene.nb.advanced:
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

            if bpy.context.scene.nb.advanced:
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

    action = bpy.props.EnumProperty(
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
            item = collection[self.index]
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

        scn = context.scene
        nb = scn.nb

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
            nb_ov, ov_idx = nb_ut.active_nb_overlay()
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
            for i, spline in enumerate(ob.data.splines):
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
                            newpath = dp[:idx] + "%d" % i + dp[idx + 1:]
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

    action = bpy.props.EnumProperty(
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


def overlay_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = []
    items.append(("scalargroups", "scalars",
                  "List the scalar overlays", 0))
    if self.objecttype != 'tracts':
        items.append(("labelgroups", "labels",
                      "List the label overlays", 1))
    if self.objecttype == 'surfaces':
        items.append(("bordergroups", "borders",
                      "List the border overlays", 2))

    return items


def engine_update(self, context):
    """Update materials when switching between engines."""

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        mat.use_nodes = nb.engine == "CYCLES"
        if nb.engine.startswith("BLENDER"):
            nb_ma.CR2BR(mat)
        else:
            nb_ma.BR2CR(mat)

    scn.render.engine = nb.engine
    # TODO: handle lights


def engine_driver():

    scn = bpy.context.scene
    nb = scn.nb

    driver = nb.driver_add("engine", -1).driver
    driver.type = 'AVERAGE'

    nb_rp.create_var(driver, "type", 'SINGLE_PROP', 'SCENE', scn, "render.engine")


def esp_path_update(self, context):
    """Add external site-packages path to sys.path."""

    nb_ut.add_path(self.esp_path)


def mode_enum_update(self, context):
    """Perform actions for updating mode."""

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        nb_ma.switch_mode_mat(mat, self.mode)

    try:
        nb_preset = nb.presets[self.index_presets]
        nb_cam = nb_preset.cameras[0]
        light_obs = [bpy.data.objects.get(light.name)
                     for light in nb_preset.lights]
        table_obs = [bpy.data.objects.get(table.name)
                     for table in nb_preset.tables]
    except:
        pass
    else:
        nb_rp.switch_mode_preset(light_obs, table_obs, nb.mode, nb_cam.cam_view)

    # TODO: switch colourbars


def managecmap_update(self, context):
    """Generate/delete dummy objects to manage colour maps."""

    scn = context.scene
    nb = scn.nb

    def gen_dummies(name="manage_colourmaps"):

        cube = nb_im.voxelvolume_box_ob([2,2,2], "SliceBox")
        cube.hide = cube.hide_render = True
        cube.name = cube.data.name = name
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

    name="manage_colourmaps"

    if self.show_manage_colourmaps:
        gen_dummies(name)

        # FIXME: this is unsafe
        cr_parentpath = "bpy.data.textures['{}']".format(name)
        cr_path = '{}.color_ramp'.format(cr_parentpath)
        context.scene.nb.cr_path = cr_path

        # load preset
        cr_path = '{}.color_ramp'.format(cr_parentpath)
        nb.cr_path = cr_path
        menu_idname = "OBJECT_MT_colourmap_presets"

        preset_class = getattr(bpy.types, menu_idname)
        preset_class.bl_label = bpy.path.display_name(basename(filepath))

    else:
        del_dummies(name)





class NeuroBlenderProperties(PropertyGroup):
    """Properties for the NeuroBlender panel."""

    is_enabled = BoolProperty(
        name="Show/hide NeuroBlender",
        description="Show/hide the NeuroBlender panel contents",
        default=True)

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
        min=1, max=4)
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

    show_transform = BoolProperty(
        name="Transform",
        default=False,
        description="Show/hide the object's transform options")
    show_material = BoolProperty(
        name="Material",
        default=False,
        description="Show/hide the object's materials options")
    show_slices = BoolProperty(
        name="Slices",
        default=False,
        description="Show/hide the object's slice options")
    show_info = BoolProperty(
        name="Info",
        default=False,
        description="Show/hide the object's info")
    show_overlay_material = BoolProperty(
        name="Overlay material",
        default=False,
        description="Show/hide the object's overlay material")
    show_overlay_slices = BoolProperty(
        name="Overlay slices",
        default=False,
        description="Show/hide the object's overlay slices")
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
    show_additional = BoolProperty(
        name="Additional options",
        default=False,
        description="Show/hide the object's additional options")
    show_bounds = BoolProperty(
        name="Bounds",
        default=False,
        description="Show/hide the preset's centre and dimensions")
    show_cameras = BoolProperty(
        name="Camera",
        default=False,
        description="Show/hide the preset's camera properties")
    show_lights = BoolProperty(
        name="Lights",
        default=False,
        description="Show/hide the preset's lights properties")
    show_key = BoolProperty(
        name="Key",
        default=False,
        description="Show/hide the Key light properties")
    show_back = BoolProperty(
        name="Back",
        default=False,
        description="Show/hide the Back light properties")
    show_fill = BoolProperty(
        name="Fill",
        default=False,
        description="Show/hide the Fill light properties")
    show_tables = BoolProperty(
        name="Table",
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

    tracts = CollectionProperty(
        type=nb_ba.TractProperties,
        name="tracts",
        description="The collection of loaded tracts")
    index_tracts = IntProperty(
        name="tract index",
        description="index of the tracts collection",
        default=0,
        min=0)
    surfaces = CollectionProperty(
        type=nb_ba.SurfaceProperties,
        name="surfaces",
        description="The collection of loaded surfaces")
    index_surfaces = IntProperty(
        name="surface index",
        description="index of the surfaces collection",
        default=0,
        min=0)
    voxelvolumes = CollectionProperty(
        type=nb_ba.VoxelvolumeProperties,
        name="voxelvolumes",
        description="The collection of loaded voxelvolumes")
    index_voxelvolumes = IntProperty(
        name="voxelvolume index",
        description="index of the voxelvolumes collection",
        default=0,
        min=0)

    presets = CollectionProperty(
        type=nb_sp.PresetProperties,
        name="presets",
        description="The collection of presets")
    index_presets = IntProperty(
        name="preset index",
        description="index of the presets",
        default=0,
        min=0)
    presets_enum = EnumProperty(
        name="presets",
        description="switch between presets",
        items=nb_sp.presets_enum_callback,
        update=nb_sp.presets_enum_update)

    campaths = CollectionProperty(
        type=nb_an.CamPathProperties,
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

    # TODO: move to elsewhere
    cr_keeprange = BoolProperty(
        name="Keep range",
        description="Keep/discard the current range of the colour ramp",
        default=True)

    cr_path = StringProperty(
        name="CR path")

# @persistent
# def projectdir_update(dummy):
#     """"""
#
#     scn = bpy.context.scene
#     nb = scn.nb
#
# #     nb.projectdir = os.path.
#
# bpy.app.handlers.load_post(projectdir_update)

# @persistent
# def engine_driver_handler(dummy):
#     """"""
#
#     engine_driver()
#
# bpy.app.handlers.load_post.append(engine_driver_handler)

# =========================================================================== #


classes = (

    nb_pa.NeuroBlenderBasePanel,
    nb_pa.NeuroBlenderOverlayPanel,
    nb_pa.NeuroBlenderScenePanel,
    nb_pa.NeuroBlenderAnimationPanel,
    nb_pa.NeuroBlenderSettingsPanel,

    nb_an.SetAnimations,
    nb_an.AddAnimation,
    nb_an.AddCamPoint,
    nb_an.AddCamPath,
    nb_an.DelCamPath,
    nb_an.ObjectListAN,
    nb_an.ObjectListCP,
    nb_an.MassIsRenderedAN,
    nb_an.MassIsRenderedCP,
    nb_an.AnimationProperties,
    nb_an.CamPathProperties,

    nb_cm.OBJECT_MT_colourmap_presets,
    nb_cm.ExecutePreset_CR,
    nb_cm.AddPresetNeuroBlenderColourmap,
    nb_cm.ResetColourmaps,
    nb_cm.ObjectListCR,
    nb_cm.ColorRampProperties,

    nb_se.OBJECT_MT_setting_presets,
    nb_se.AddPresetNeuroBlenderSettings,
    nb_se.Reload,

    nb_sp.ResetPresetCentre,
    nb_sp.ResetPresetDims,
    nb_sp.AddPreset,
    nb_sp.DelPreset,
    nb_sp.AddLight,
    nb_sp.ScenePreset,
    nb_sp.ObjectListPL,
    nb_sp.MassIsRenderedPL,
    nb_sp.CameraProperties,
    nb_sp.LightsProperties,
    nb_sp.TableProperties,
    nb_sp.PresetProperties,

    nb_ol.ImportScalarGroups,
    nb_ol.ImportLabelGroups,
    nb_ol.ImportBorderGroups,
    nb_ol.RevertLabel,
    nb_ol.WeightPaintMode,
    nb_ol.VertexWeight2VertexColors,
    nb_ol.VertexWeight2UV,
    nb_ol.UnwrapSurface,
    nb_ol.ObjectListTS,
    nb_ol.ScalarProperties,
    nb_ol.LabelProperties,
    nb_ol.BorderProperties,
    nb_ol.ScalarGroupProperties,
    nb_ol.LabelGroupProperties,
    nb_ol.BorderGroupProperties,

    nb_ba.ImportTracts,
    nb_ba.ImportSurfaces,
    nb_ba.ImportVoxelvolumes,
    nb_ba.TractProperties,
    nb_ba.SurfaceProperties,
    nb_ba.VoxelvolumeProperties,

    ObjectListL1,
    ObjectListL2,
    ObjectListL3,
    ObjectListOperations,
    MassIsRenderedL1,
    MassIsRenderedL2,
    MassIsRenderedL3,
    MassSelect,
    SwitchToMainScene,
    SaveBlend,
    NeuroBlenderProperties
    )

def register():

#     bpy.utils.register_module(__name__, verbose=True)
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.nb = PointerProperty(type=NeuroBlenderProperties)


def unregister():  # TODO: unregister handlers

#     bpy.utils.unregister_module(__name__)
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.nb

if __name__ == "__main__":
    register()
