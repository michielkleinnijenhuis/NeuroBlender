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

NeuroBlender is a Blender add-on 
to create artwork from neuroscientific data.
"""


if "bpy" in locals():
    print("Reloading NeuroBlender")
    import imp
    imp.reload(nb_an)
    imp.reload(nb_ca)
    imp.reload(nb_cm)
    imp.reload(nb_im)
    imp.reload(nb_ma)
    imp.reload(nb_ol)
    imp.reload(nb_sp)
    imp.reload(nb_se)
    imp.reload(nb_ut)
else:
    print("Importing NeuroBlender")
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
                   carvers as nb_ca,
                   colourmaps as nb_cm,
                   materials as nb_ma,
                   overlays as nb_ol,
                   panels as nb_pa,
                   properties as nb_pr,
                   scenepresets as nb_sp,
                   settings as nb_se,
                   utils as nb_ut)
    from .imports import (import_tracts as nb_it,
                          import_surfaces as nb_is,
                          import_voxelvolumes as nb_iv,
                          import_overlays as nb_im)

import os
import sys
from shutil import copy
import re
import numpy as np


bl_info = {
    "name": "NeuroBlender",
    "author": "Michiel Kleinnijenhuis",
    "version": (1, 0, 1),
    "blender": (2, 79, 1),
    "location": "Properties -> Scene -> NeuroBlender",
    "description": "Create artwork from neuroscientific data.",
    "warning": "",
    "wiki_url": "http://neuroblender.readthedocs.io/en/latest/",
    "category": "Science"}


class NB_UL_collection(UIList):

    ui = ''

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        item_icon = "CANCEL"
        if hasattr(item, 'is_valid'):
            if item.is_valid:
                item_icon = item.icon

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            if self.ui == 'CP':
                fun = self.draw_default_CP
            elif self.ui == 'TS':
                fun = self.draw_default_TS
            else:
                fun = self.draw_default

            fun(layout, item, item_icon)

            if context.scene.nb.settingprops.advanced:
                if self.ui == 'L1':
                    fun = self.draw_advanced_L1
                elif self.ui == 'L2':
                    fun = self.draw_advanced_L2
                elif self.ui == 'L3':
                    fun = self.draw_advanced_L3
                elif self.ui == 'PS':
                    fun = self.draw_advanced_PS
                elif self.ui == 'CR':
                    fun = self.draw_advanced_CR
                else:
                    fun = self.draw_advanced

                fun(layout, data, item, index)

        elif self.layout_type in {'GRID'}:

            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)

    def draw_default(self, layout, item, item_icon):

        col = layout.column()
        col.prop(item, "name", text="", emboss=False,
                 translate=False, icon=item_icon)

    def draw_default_CP(self, layout, item, item_icon):

        row = layout.row()
        row.prop(item, "co", text="cp", emboss=True, icon=item_icon)

    def draw_default_TS(self, layout, item, item_icon):

        layout.label(text="Time index:")

    def draw_advanced(self, layout, data, item, index):

        if hasattr(item, 'is_rendered'):
            col = layout.column()
            col.alignment = "RIGHT"
            col.active = item.is_rendered
            col.prop(item, "is_rendered", text="", emboss=False,
                     translate=False, icon='SCENE')

    def draw_advanced_L1(self, layout, data, item, index):

        if ((bpy.context.scene.nb.objecttype == 'tracts') or
                (bpy.context.scene.nb.objecttype == 'surfaces')):
            col = layout.column()
            col.alignment = "RIGHT"
            col.operator('nb.attach_neurons',
                         icon='CURVE_PATH',
                         text="").data_path = item.path_from_id()

        col = layout.column()
        col.alignment = "RIGHT"
        col.active = item.is_rendered
        col.prop(item, "is_rendered", text="", emboss=False,
                 translate=False, icon='SCENE')

    def draw_advanced_L2(self, layout, data, item, index):

        if bpy.context.scene.nb.overlaytype == 'labelgroups':
            col = layout.column()
            col.alignment = "RIGHT"
            col.operator('nb.separate_labels',
                         icon='PARTICLE_PATH',
                         text="").data_path = item.path_from_id()

        col = layout.column()
        col.alignment = "RIGHT"
        col.active = item.is_rendered
        col.prop(item, "is_rendered", text="", emboss=False,
                 translate=False, icon='SCENE')

    def draw_advanced_L3(self, layout, data, item, index):

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

        col = layout.column()
        col.alignment = "RIGHT"
        col.operator('nb.attach_neurons',
                     icon='CURVE_PATH',
                     text="").data_path = item.path_from_id()

    def draw_advanced_PS(self, layout, data, item, index):

        col = layout.column()
        row = col.row(align=True)
        props = [{'prop': 'location',
                  'op': "nb.reset_presetcentre",
                  'icon': 'CLIPUV_HLT',
                  'text': 'Recentre'},
                 {'prop': 'scale',
                  'op': "nb.reset_presetdims",
                  'icon': 'BBOX',
                  'text': 'Rescale'}]
        for propdict in props:
            col1 = row.column(align=True)
            col1.operator(propdict['op'],
                          icon=propdict['icon'],
                          text="").index_presets = index

    def draw_advanced_CR(self, layout, data, item, index):

        col = layout.column()
        col.prop(item, "nn_position", text="")


for ui in ['L1', 'L2', 'L3', 'PS', 'CM', 'PL', 'TB',
           'AN', 'CP', 'CV', 'CO', 'CR', 'TS']:

    uilistclass = type("NB_UL_collection_{}".format(ui),
                       (NB_UL_collection,),
                       {"ui": ui})

    bpy.utils.register_class(uilistclass)


class NB_OT_collection(Operator):
    bl_idname = "nb.nblist_ops"
    bl_label = "NBlist operations"
    bl_options = {"REGISTER", "UNDO"}

    action = StringProperty(
        name="action",
        description="Specify operator action",
        default="")
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
                info = ['removed {}'.format(collection[self.index].name)]
                info += self.remove_items(context, nb, data, collection, nb_ob)
                self.report({'INFO'}, '; '.join(info))

            elif (self.action.startswith('DOWN') and
                  self.index < len(collection) - 1):

                if self.action.endswith('_CO'):
                    nb_ob = nb_ut.active_nb_object()[0]
                    carver = nb_ob.carvers[nb_ob.index_carvers]
                    override = context.copy()
                    override['object'] = bpy.data.objects[carver.name]
                    bpy.ops.object.modifier_move_down(override,
                                                      modifier=self.name)
#                     carverob = bpy.data.objects[carver.name]
#                     if self.index == 0:  # first mod always INTERSECT
#                         carverob.modifiers[0].operation = 'INTERSECT'
#                         carver.modifiers[1].operation = 'UNION'

                collection.move(self.index, self.index + 1)
                exec("{}.index_{} += 1".format(data, self.type))

            elif self.action.startswith('UP') and self.index >= 1:

                if self.action.endswith('_CO'):
                    nb_ob = nb_ut.active_nb_object()[0]
                    carver = nb_ob.carvers[nb_ob.index_carvers]
                    override = context.copy()
                    override['object'] = bpy.data.objects[carver.name]
                    bpy.ops.object.modifier_move_up(override,
                                                    modifier=self.name)
#                     carverob = bpy.data.objects[carver.name]
#                     if self.index == 1:  # first mod always INTERSECT
#                         carverob.modifiers[1].operation = 'INTERSECT'
#                         carver.modifiers[0].operation = 'UNION'

                collection.move(self.index, self.index - 1)
                exec("{}.index_{} -= 1".format(data, self.type))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        if self.action.endswith('_L1'):
            nb_ob = nb_ut.active_nb_object()[0]
            self.type = nb.objecttype
            self.name = nb_ob.name
            data_path = "nb.{}".format(self.type)
            self.index = scn.path_resolve(data_path).find(self.name)
            self.data_path = nb_ob.path_from_id()
        elif self.action.endswith('_L2'):
            nb_ob = nb_ut.active_nb_object()[0]
            nb_ov = nb_ut.active_nb_overlay()[0]
            self.type = nb.overlaytype
            self.name = nb_ov.name
            data_path = "{}.{}".format(nb_ob.path_from_id(), self.type)
            self.index = scn.path_resolve(data_path).find(self.name)
            self.data_path = nb_ov.path_from_id()
        elif self.action.endswith('_L3'):
            nb_ob = nb_ut.active_nb_object()[0]
            nb_ov = nb_ut.active_nb_overlay()[0]
            nb_it = nb_ut.active_nb_overlayitem()[0]
            self.type = nb.overlaytype.replace("groups", "s")
            self.name = nb_it.name
            data_path = "{}.{}".format(nb_ov.path_from_id(), self.type)
            self.index = scn.path_resolve(data_path).find(self.name)
            self.data_path = nb_it.path_from_id()
        elif self.action.endswith('_PS'):
            preset_path = "nb.presets[{:d}]".format(nb.index_presets)
            preset = scn.path_resolve(preset_path)
            self.type = "presets"
            self.name = preset.name
            self.index = nb.index_presets
            self.data_path = preset.path_from_id()
        elif self.action.endswith('_CM'):
            preset_path = "nb.presets[{:d}]".format(nb.index_presets)
            preset = scn.path_resolve(preset_path)
            camera = preset.cameras[preset.index_cameras]
            self.type = "cameras"
            self.name = camera.name
            self.index = preset.index_cameras
            self.data_path = camera.path_from_id()
        elif self.action.endswith('_PL'):
            preset_path = "nb.presets[{:d}]".format(nb.index_presets)
            preset = scn.path_resolve(preset_path)
            light = preset.lights[preset.index_lights]
            self.type = "lights"
            self.name = light.name
            self.index = preset.index_lights
            self.data_path = light.path_from_id()
        elif self.action.endswith('_TB'):
            preset_path = "nb.presets[{:d}]".format(nb.index_presets)
            preset = scn.path_resolve(preset_path)
            table = preset.tables[preset.index_tables]
            self.type = "tables"
            self.name = table.name
            self.index = preset.index_tables
            self.data_path = table.path_from_id()
        elif self.action.endswith('_AN'):
            animation = nb.animations[nb.index_animations]
            self.type = "animations"
            self.name = animation.name
            self.index = nb.index_animations
            self.data_path = animation.path_from_id()
        elif self.action.endswith('_CV'):
            nb_ob = nb_ut.active_nb_object()[0]
            carver = nb_ob.carvers.get(nb_ob.carvers_enum)
#             carver = nb_ob.carvers[nb_ob.index_carvers]
            self.type = "carvers"
            self.name = carver.name
            self.index = nb_ob.index_carvers
            self.data_path = carver.path_from_id()
        elif self.action.endswith('_CO'):
            nb_ob = nb_ut.active_nb_object()[0]
            carver = nb_ob.carvers[nb_ob.index_carvers]
            carveobject = carver.carveobjects[carver.index_carveobjects]
            self.type = "carveobjects"
            self.name = carveobject.name
            self.index = carver.index_carveobjects
            self.data_path = carveobject.path_from_id()

        return self.execute(context)

    def get_collection(self, context):

        scn = context.scene

        try:
            # NOTE: this converts calls with key to index
            self.data_path = scn.path_resolve(self.data_path).path_from_id()
        except ValueError:
            info = 'invalid data path: {}'.format(self.data_path)
            self.report({'INFO'}, info)
            raise

        dp_split = re.findall(r"[\w']+", self.data_path)
        dp_indices = re.findall(r"(\[\d+\])", self.data_path)
        coll_path = self.data_path.strip(dp_indices[-1])
        collection = scn.path_resolve(coll_path)
        coll_path = collection.path_from_id()  # key to index
        data = '.'.join(coll_path.split('.')[:-1])

        if self.index == -1:
            self.index = int(dp_split[-1])
        if not self.type:
            self.type = dp_split[-2]
        if not self.name:
            self.name = collection[self.index].name

        nb_ob_path = '.'.join(self.data_path.split('.')[:2])
        nb_ob = scn.path_resolve(nb_ob_path)

        return collection, data, nb_ob

    def remove_items(self, context, nb, data, collection, nb_ob):
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
                # remove carvers
                for carver in nb_ob.carvers:
                    carver_data_path = carver.path_from_id()
                    self.remove_carvers(context, carver_data_path)
                # remove all children
                fun = eval("self.remove_%s_overlays" % self.type)
                fun(nb_ob, ob)
                # remove the object itself
                bpy.data.objects.remove(ob)
        elif self.action.endswith('_CM'): 
            try:
                ob = bpy.data.objects[name]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % name]
            else:
                bpy.data.objects.remove(ob)
                # TODO: bpy.data.cameras if no users
        elif self.action.endswith('_PL'):
            try:
                ob = bpy.data.objects[name]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % name]
            else:
                bpy.data.objects.remove(ob)
                # TODO: bpy.data.lamps if no users
        elif self.action.endswith('_TB'):
            try:
                ob = bpy.data.objects[name]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % name]
            else:
                bpy.data.meshes.remove(ob.data)
                bpy.data.objects.remove(ob)
        elif self.action.endswith('_AN'):
            anim = nb.animations[nb.index_animations]
            fun = eval("self.remove_animations_%s" %
                       anim.animationtype)
            fun(nb.animations, self.index)
        elif self.action.endswith('_CV'):
            self.remove_carvers(context, self.data_path)
        elif self.action.endswith('_CO'):
            self.remove_carveobjects(context, self.data_path)
        else:
            ob = bpy.data.objects[nb_ob.name]
            fun = eval("self.remove_%s_%s" % (nb.objecttype, self.type))
            fun(collection[self.index], ob)

        # remove the NeuroBlender collection
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

        bpy.data.textures.remove(bpy.data.textures[scalargroup.name])
        self.remove_material(ob, scalargroup.name)

    def remove_voxelvolumes_labelgroups(self, labelgroup, ob):
        """Remove labelgroup overlay from a voxelvolume."""

        bpy.data.textures.remove(bpy.data.textures[labelgroup.name])
        self.remove_material(ob, labelgroup.name)

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
        if (item is not None) and (item.users < 1):
            item.user_clear()
            coll.remove(item)

    def remove_vertexcoll(self, coll, name):
        """Remove vertexgroup or vertex_color attribute"""

        mstring = '{}.vol'.format(name)
        for item in coll:
            if item.name.startswith(mstring):
                coll.remove(item)

    def remove_animations_camerapath(self, anims, index):
        """Remove camera path animation."""

        anim = anims[index]
        cam = bpy.data.objects[anim.camera]
        acp = bpy.types.NB_OT_animate_camerapath
        acp.clear_CP_evaltime(anim)
        acp.clear_CP_followpath(anim)
        acp.remove_CP_followpath(cam, anim)
        cam_anims = [anim for i, anim in enumerate(anims)
                     if ((anim.animationtype == "camerapath") &
                         (anim.is_rendered) &
                         (i != index))]
        acp.update_cam_constraints(cam, cam_anims)

    def remove_animations_carver(self, anims, index):
        """Remove slice animation."""

        scn = bpy.context.scene

        # get the fcurve
        anim = anims[index]
        prop = "slice{}".format(anim.sliceproperty.lower())
        prop_path = '{}.{}'.format(anim.nb_object_data_path, prop)
        idx = 'XYZ'.index(anim.axis)
        prev = nb_an.get_animation_fcurve(
            anim,
            data_path=prop_path,
            idx=idx,
            remove=True)[1]
        # reset the property
        nb_an.restore_state_carver(prev)

    def remove_animations_timeseries(self, anims, index):
        """Remove timeseries animation."""

        scn = bpy.context.scene

        # get the fcurve
        anim = anims[index]
        prop = 'index_scalars'
        prop_path = '{}.{}'.format(anim.nb_object_data_path, prop)
        prev = nb_an.get_animation_fcurve(
            anim,
            data_path=prop_path,
            remove=True)[1]
        # reset the property
        nb_an.restore_state_timeseries(prev)

    def remove_carvers(self, context, data_path):
        """Remove a carver."""

        scn = context.scene

        carver = scn.path_resolve(data_path)
        carverob = bpy.data.objects[carver.name]

        for cob in carver.carveobjects:
            self.remove_carveobjects(context, cob.path_from_id())

        bpy.data.objects.remove(carverob)

    def remove_carveobjects(self, context, data_path):
        """Remove carve object from carver."""

        scn = context.scene

        nb_carveob = scn.path_resolve(data_path)
        carveob = bpy.data.objects.get(nb_carveob.name)

        carverpath = '.'.join(data_path.split('.')[:-1])
        carver = scn.path_resolve(carverpath)
        carverob = bpy.data.objects.get(carver.name)

        mod = carverob.modifiers.get(carveob.name)
        carverob.modifiers.remove(mod)
        if nb_carveob.type == 'activeob':
            group = bpy.data.groups.get(carver.name)
            group.objects.unlink(carveob)
            cmats = carveob.data.materials
            cmats.pop(cmats.find('wire'))
        else:
            bpy.data.objects.remove(carveob)

        scn.objects.active = carverob
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')


class NB_MT_mass_select(Menu):
    bl_idname = "NB_MT_mass_select"
    bl_label = "NeuroBlender collection switches"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    ui = ''

    def draw(self, context):

        layout = self.layout

        items = [('SELECT_{}'.format(self.ui), "Select All"),
                 ('DESELECT_{}'.format(self.ui), "Deselect All"),
                 ('INVERT_{}'.format(self.ui), "Invert")]

        for act, txt in items:
            layout.operator("nb.mass_select",
                            icon='SCENE',
                            text=txt).action = act


for ui in ['L1', 'L2', 'L3', 'CM', 'PL', 'TB', 'AN', 'CP', 'CO']:

    idname = "NB_MT_mass_select_{}".format(ui)

    menuclass = type("NB_MT_mass_select_{}".format(ui),
                     (NB_MT_mass_select,),
                     {"bl_idname": idname, "ui": ui})

    bpy.utils.register_class(menuclass)


class NB_OT_mass_select(Operator):
    bl_idname = "nb.mass_select"
    bl_label = "Mass select"
    bl_description = "Select/Deselect/Invert rendered objects/overlays"
    bl_options = {"REGISTER"}

    action = StringProperty(
        name="action",
        description="Specify operator action",
        default="")
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

    invoke = NB_OT_collection.invoke
    get_collection = NB_OT_collection.get_collection

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


class NB_OT_switch_to_main(Operator):
    bl_idname = "nb.switch_to_main"
    bl_label = "Switch to main"
    bl_description = "Switch to main NeuroBlender scene to import"
    bl_options = {"REGISTER"}

    def execute(self, context):

        context.window.screen.scene = bpy.data.scenes["Scene"]

        return {"FINISHED"}


class NB_OT_initialize_neuroblender(Operator):
    bl_idname = "nb.initialize_neuroblender"
    bl_label = "Initialize NeuroBlender"
    bl_description = "Initialize NeuroBlender"
    bl_options = {"REGISTER"}

    def execute(self, context):

        sp = bpy.utils.script_path_user()
        cmapdir = os.path.join(sp, 'presets', 'neuroblender_colourmaps')
        bpy.ops.nb.reset_colourmaps()

        bpy.context.scene.nb.settingprops.is_initialized = True

        return {"FINISHED"}


class NB_OT_save_blend(Operator, ExportHelper):
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

    handlers = bpy.app.handlers.frame_change_pre
    handlers.append(nb_pr.carvers_handler)
    handlers.append(nb_pr.rendertype_enum_handler)
    handlers.append(nb_pr.index_scalars_handler)

    handlers = bpy.app.handlers.load_post
    handlers.append(nb_pr.init_settings_handler)

    bpy.types.Scene.nb = PointerProperty(type=nb_pr.NeuroBlenderProperties)
    # FIXME: errors on reloading addons using F8 hotkey

    print("Registered NeuroBlender")


def unregister():

    del bpy.types.Scene.nb

    handlers = bpy.app.handlers.frame_change_pre
    handlers.remove(nb_pr.carvers_handler)
    handlers.remove(nb_pr.rendertype_enum_handler)
    handlers.remove(nb_pr.index_scalars_handler)

    handlers = bpy.app.handlers.load_post
    handlers.remove(nb_pr.init_settings_handler)

    bpy.utils.unregister_module(__name__)

    print("Unregistered NeuroBlender")


if __name__ == "__main__":
    register()
