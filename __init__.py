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

from bpy_extras.io_utils import ImportHelper
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
                       PointerProperty)

from os.path import dirname, join
from shutil import copy
import numpy as np
import mathutils

from . import tractblender_import as tb_imp
from . import tractblender_materials as tb_mat
from . import tractblender_renderpresets as tb_rp
from . import tractblender_utils as tb_utils
from . import external_sitepackages as ext_sp


# =========================================================================== #


bl_info = {
    "name": "TractBlender",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 5),
    "blender": (2, 77, 0),
    "location": "Properties -> Scene -> TractBlender",
    "description": """"
        This add-on focusses on visualising dMRI tractography results.
        Brain surfaces can be addded with overlays and labels.
        Camera, material and lighting presets can be loaded.
        """,
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}


# =========================================================================== #


class TractBlenderImportPanel(Panel):
    """Host the TractBlender geometry import"""
    bl_idname = "OBJECT_PT_tb_geometry"
    bl_label = "TractBlender - Geometry"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):

        scn = context.scene
        tb = scn.tb

        if tb.is_enabled:
            self.draw_tb_geom(self.layout, tb)
        else:
            switch_to_main_scene(self.layout, tb)

    def draw_tb_geom(self, layout, tb):

        obtype = tb.objecttype

        row = layout.row()
        row.prop(tb, "objecttype", expand=True)

        self.drawunit_UIList(layout, "L1", tb, obtype)

        try:
            idx = eval("tb.index_%s" % obtype)
            tb_ob = eval("tb.%s[%d]" % (obtype, idx))
        except IndexError:
            pass
        else:
            self.drawunit_tri(layout, "transform", tb, tb_ob)
            self.drawunit_tri(layout, "info", tb, tb_ob)

    def drawunit_UIList(self, layout, uilistlevel, data, type, addopt=True):

        row = layout.row()
        row.template_list("ObjectList" + uilistlevel, "",
                          data, type,
                          data, "index_" + type,
                          rows=2)
        col = row.column(align=True)
        if addopt:
            col.operator("tb.import_" + type,
                         icon='ZOOMIN',
                         text="")
        col.operator("tb.oblist_ops",
                     icon='ZOOMOUT',
                     text="").action = 'REMOVE_' + uilistlevel
        col.menu("tb.mass_is_rendered_objects",
                 icon='DOWNARROW_HLT',
                 text="")
        col.separator()
        col.operator("tb.oblist_ops",
                     icon='TRIA_UP',
                     text="").action = 'UP_' + uilistlevel
        col.operator("tb.oblist_ops",
                     icon='TRIA_DOWN',
                     text="").action = 'DOWN_' + uilistlevel

    def drawunit_tri(self, layout, triflag, tb, data):

        row = layout.row()
        prop = "show_%s" % triflag
        if eval("tb.%s" % prop):
            exec("self.drawunit_tri_%s(layout, tb, data)" % triflag)
            icon='TRIA_DOWN'
        else:
            icon='TRIA_RIGHT'
        row.prop(tb, prop, icon=icon, emboss=False)

    def drawunit_tri_transform(self, layout, tb, tb_ob):

        row = layout.row()
        row.prop(tb_ob, "sformfile")

        ob = bpy.data.objects[tb_ob.name]
        mw = ob.matrix_world
        txts = ["srow_%s  %8.3f %8.3f %8.3f %8.3f" % (dim,
                mw[i][0], mw[i][1], mw[i][2], mw[i][3])
                for i, dim in enumerate('xyz')]
        row = layout.row()
        row.enabled = False
        row.label(text=txts[0])
        row = layout.row()
        row.enabled = False
        row.label(text=txts[1])
        row = layout.row()
        row.enabled = False
        row.label(text=txts[2])

    def drawunit_tri_info(self, layout, tb, tb_ob):

        if tb.objecttype == "tracts":
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "filepath",
                     text="Path", emboss=False)
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "nstreamlines",
                     text="Number of streamlines", emboss=False)
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "streamlines_interpolated",
                     text="Interpolation factor", emboss=False)
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "tract_weeded",
                     text="Tract weeding factor", emboss=False)
        elif tb.objecttype == 'surfaces':
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "filepath",
                     text="Path", emboss=False)
        elif tb.objecttype == 'voxelvolumes':
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "filepath",
                     text="Path", emboss=False)
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "range",
                     text="Datarange", emboss=False)


class TractBlenderAppearancePanel(Panel):
    """Host the TractBlender materials functions"""
    bl_idname = "OBJECT_PT_tb_materials"
    bl_label = "TractBlender - Materials"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):

        scn = bpy.context.scene
        tb = scn.tb

        if tb.is_enabled:
            self.draw_tb_mats(self.layout, tb)
        else:
            switch_to_main_scene(self.layout, tb)

    def draw_tb_mats(self, layout, tb):

        obtype = tb.objecttype

        try:
            idx = eval("tb.index_%s" % obtype)
            tb_ob = eval("tb.%s[%d]" % (obtype, idx))
        except IndexError:
            row = self.layout.row()
            row.label(text="No " + obtype + " loaded ...")
        else:
            row = self.layout.row()
            row.label(text="Properties of %s:" % tb_ob.name,
                      icon=tb_ob.icon)
            self.drawunit_tri(self.layout, "appearance", tb, tb_ob)
            self.drawunit_tri(self.layout, "overlays", tb, tb_ob)

    def drawunit_tri(self, layout, triflag, tb, data):

        row = layout.row()
        prop = "show_%s" % triflag
        if eval("tb.%s" % prop):
            exec("self.drawunit_tri_%s(layout, tb, data)" % triflag)
            icon='TRIA_DOWN'
        else:
            icon='TRIA_RIGHT'
        row.prop(tb, prop, icon=icon, emboss=False)

    def drawunit_tri_appearance(self, layout, tb, tb_ob):

        if tb.objecttype == "voxelvolumes":

            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "range")  # TODO: move to info?

            box = layout.box()
            tex = bpy.data.textures[tb_ob.name]
            text = "Convenience access to '" + tb_ob.name + \
                   "' texture basics:"
            # FIXME: nn_range display does not work here
#                 self.drawunit_texture(box, tex, tb_ob, text)
            self.drawunit_texture(box, tex, text=text)
        else:
            self.drawunit_new_material(layout, tb_ob)

    def drawunit_tri_overlays(self, layout, tb, tb_ob):

        ovtype = tb.overlaytype

        row = layout.row()
        row.prop(tb, "overlaytype", expand=True)

        self.drawunit_UIList(layout, "L2", tb_ob, ovtype)

        try:
            ov_idx = eval("tb_ob.index_%s" % ovtype)
            tb_ov = eval("tb_ob.%s[%d]" % (ovtype, ov_idx))
        except IndexError:
            pass
        else:
            if ovtype == "scalars":
                self.drawunit_scalars(layout, tb, tb_ov)
            else:
                self.drawunit_tri(layout, "items", tb, tb_ov)

    def drawunit_UIList(self, layout, uilistlevel, data, type, addopt=True):

        row = layout.row()
        row.template_list("ObjectList" + uilistlevel, "",
                          data, type,
                          data, "index_" + type,
                          rows=2)
        col = row.column(align=True)
        if addopt:
            col.operator("tb.import_" + type,
                         icon='ZOOMIN',
                         text="")
        col.operator("tb.oblist_ops",
                     icon='ZOOMOUT',
                     text="").action = 'REMOVE_' + uilistlevel
        col.menu("tb.mass_is_rendered_objects",
                 icon='DOWNARROW_HLT',
                 text="")
        col.separator()
        col.operator("tb.oblist_ops",
                     icon='TRIA_UP',
                     text="").action = 'UP_' + uilistlevel
        col.operator("tb.oblist_ops",
                     icon='TRIA_DOWN',
                     text="").action = 'DOWN_' + uilistlevel

    def drawunit_tri_items(self, layout, tb, tb_ov):

        type = tb.overlaytype.replace("groups", "s")

        row = layout.row()
        text = type + " in group '" + tb_ov.name + "'."
        row.label(text=text)

        self.drawunit_UIList(layout, "L3", tb_ov, type, addopt=False)
        self.drawunit_tri(layout, "itemprops", tb, tb_ov)

    def drawunit_scalars(self, layout, tb, tb_ov):

        # TODO: create 'info' dropdown?
        row = layout.row()
        row.enabled = False
        row.prop(tb_ov, "range")

        row = layout.row()
        row.prop(tb_ov, "showcolourbar")

        box = layout.box()
        if tb.objecttype == "tracts":
            ng = bpy.data.node_groups.get("TractOvGroup")
            ramp = ng.nodes["ColorRamp"]
            text = "Convenience access to color ramp:"
            self.drawunit_colourramp(box, ramp, tb_ov, text)
        elif tb.objecttype == "surfaces":
            text = "Convenience access to '" + tb_ov.name + \
                   "' material basics:"
            nt = bpy.data.materials[tb_ov.name].node_tree
            self.drawunit_material(box, nt, tb_ov, text)
        if tb.objecttype == "voxelvolumes":
            tex = bpy.data.textures[tb_ov.name]
            text = "Convenience access to '" + tb_ov.name + \
                   "' texture basics:"
            self.drawunit_texture(box, tex, tb_ov, text)

    def drawunit_tri_itemprops(self, layout, tb, tb_ov):

        type = tb.overlaytype.replace("groups", "s")

        try:
            idx = eval("tb_ov.index_%s" % type)
            data = eval("tb_ov.%s[%d]" % (type, idx))
        except IndexError:
            pass
        else:
            if type == "labels":
                self.drawunit_labels(layout, tb, data)
            elif type == "borders":
                self.drawunit_borders(layout, tb, data)

    def drawunit_labels(self, layout, tb, tb_ov):

        row = layout.row()
        row.enabled = False
        row.prop(tb_ov, "value")
        row.prop(tb_ov, "colour", text="")

        box = layout.box()
        row = box.row()
        if tb.objecttype == "voxelvolumes":
            tb_overlay = tb_utils.active_tb_overlay()[0]
            row.label(text="Convenience access to label properties:")
            tex = bpy.data.textures[tb_overlay.name]
            el = tex.color_ramp.elements[tb_overlay.index_labels + 1]
            row = box.row()
            row.prop(el, "color")
            mat = bpy.data.materials[tb_overlay.name]
            row = box.row()
            row.prop(mat.texture_slots[0], "emission_factor")
            row.prop(mat.texture_slots[0], "emission_color_factor")
        else:
            row.label(text="Convenience access to label material:")
            row = box.row()
            mat = bpy.data.materials[tb_ov.name]
            colour = mat.node_tree.nodes["Diffuse BSDF"].inputs[0]
            trans = mat.node_tree.nodes["Mix Shader.001"].inputs[0]
            row.prop(colour, "default_value", text="Colour")
            row.prop(trans, "default_value", text="Transparency")
            row.operator("tb.revert_label", icon='BACK', text="")
            row = box.row()
            nt = mat.node_tree
            row.prop(nt.nodes["Diffuse BSDF"].inputs[1], 
                     "default_value", text="diffuse")
            row.prop(nt.nodes["Glossy BSDF"].inputs[1], 
                     "default_value", text="glossy")
            row.prop(nt.nodes["Mix Shader"].inputs[0], 
                     "default_value", text="mix")
            # TODO: copy transparency from colourpicker (via driver?)
#             nt.nodes["Diffuse BSDF"].inputs[0].default_value = (0.627451, 0.392157, 0.196078, 0.6)

    def drawunit_borders(self, layout, tb, tb_ov):

        ob = bpy.data.objects[tb_ov.name]

#             row = box.row()
#             row.prop(tb_ov, "colour")

        box = layout.box()
        row = box.row()
        row.label(text="Convenience access to border properties:")
        row = box.row()
        mat = bpy.data.materials[tb_ov.name]
        colour = mat.node_tree.nodes["Diffuse BSDF"].inputs[0]
        row.prop(colour, "default_value", text="Colour")
        trans = mat.node_tree.nodes["Mix Shader.001"].inputs[0]
        row.prop(trans, "default_value", text="Transparency")
        row = box.row()
        row.label(text="Smoothing:")
        row.prop(ob.modifiers["smooth"], "factor")
        row.prop(ob.modifiers["smooth"], "iterations")
        row = box.row()
        row.label(text="Bevel:")
        row.prop(ob.data, "bevel_depth")
        row.prop(ob.data, "bevel_resolution")

    def drawunit_new_material(self, layout, tb_ob):

        row = layout.row()
        col1 = row.column()
        row1 = col1.row()
        row1.prop(tb_ob, "transparency")
        row1 = col1.row()
        row1.prop(tb_ob, "colourpicker")
        col2 = row.column()
        col2.prop(tb_ob, "colourtype", expand=True)

    def drawunit_material(self, layout, nt, tb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        row.prop(nt.nodes["Diffuse BSDF"].inputs[1], "default_value", text="diffuse")
        row.prop(nt.nodes["Glossy BSDF"].inputs[1], "default_value", text="glossy")
        row.prop(nt.nodes["Mix Shader"].inputs[0], "default_value", text="mix")
        ramp = nt.nodes["ColorRamp"]
        self.drawunit_colourramp(layout, ramp, tb_coll)

    def drawunit_texture(self, layout, tex, tb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        row.prop(tex, "intensity")
        row.prop(tex, "contrast")
        row.prop(tex, "saturation")

        if tex.use_color_ramp:
            self.drawunit_colourramp(layout, tex, tb_coll)

    def drawunit_colourramp(self, layout, ramp, tb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        layout.template_color_ramp(ramp, "color_ramp", expand=True)

        if tb_coll is not None:
            row = layout.row()
            row.label(text="non-normalized colour stop positions:")
            self.calc_nn_elpos(tb_coll, ramp)
            row = layout.row()
            row.enabled = False
            row.template_list("ObjectListCR", "",
                              tb_coll, "nn_elements",
                              tb_coll, "index_nn_elements",
                              rows=3)

    def calc_nn_elpos(self, tb_ov, ramp):
        # TODO: solve with drivers
        els = ramp.color_ramp.elements
        nnels = tb_ov.nn_elements
        n_els = len(els)
        n_nnels = len(nnels)
        if n_els > n_nnels:
            for _ in range(n_els-n_nnels):
                nnels.add()
        elif n_els < n_nnels:
            for _ in range(n_nnels-n_els):
                nnels.remove(0)
        dmin = tb_ov.range[0]
        dmax = tb_ov.range[1]
        drange = dmax-dmin
        for i, el in enumerate(nnels):
            el.name = "colour stop " + str(i)
            el.nn_position = els[i].position * drange + dmin


class SwitchToMainScene(Operator):
    bl_idname = "tb.switch_to_main"
    bl_label = "Switch to main"
    bl_description = "Switch to main TractBlender scene to import"
    bl_options = {"REGISTER"}

    def execute(self, context):

        context.window.screen.scene = bpy.data.scenes["Scene"]

        return {"FINISHED"}


class ObjectListL1(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.isvalid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)
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

        if item.isvalid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)
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

        if item.isvalid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)
            col = layout.column()
            col.alignment = "RIGHT"
            col.active = item.is_rendered
            col.prop(item, "is_rendered", text="", emboss=False,
                     translate=False, icon='SCENE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListCR(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        item_icon = "ARROW_LEFTRIGHT"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)
            col = layout.column()
            col.prop(item, "nn_position", text="")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListOperations(Operator):
    bl_idname = "tb.oblist_ops"
    bl_label = "Objectlist operations"

    action = bpy.props.EnumProperty(
        items=(('UP_L1', "UpL1", ""),
               ('DOWN_L1', "DownL1", ""),
               ('REMOVE_L1', "RemoveL1", ""),
               ('UP_L2', "UpL2", ""),
               ('DOWN_L2', "DownL2", ""),
               ('REMOVE_L2', "RemoveL2", ""),
               ('UP_L3', "UpL3", ""),
               ('DOWN_L3', "DownL3", ""),
               ('REMOVE_L3', "RemoveL3", "")))

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        tb_ob, ob_idx = tb_utils.active_tb_object()

        collection = eval("%s.%s" % ("tb", tb.objecttype))
        validate_tb_objects([collection])

        if self.action.endswith('_L1'):
            data = "tb"
            type = tb.objecttype
        elif self.action.endswith('_L2'):
            data = "tb_ob"
            type = tb.overlaytype
        elif self.action.endswith('_L3'):
            tb_ov, ov_idx = tb_utils.active_tb_overlay()
            data = "tb_ov"
            type = tb.overlaytype.replace("groups", "s")

        collection = eval("%s.%s" % (data, type))
        idx = eval("%s.index_%s" % (data, type))

        try:
            item = collection[idx]
        except IndexError:
            pass
        else:
            if self.action.startswith('DOWN') and idx < len(collection) - 1:
                collection.move(idx, idx+1)
                exec("%s.index_%s += 1" % (data, type))
            elif self.action.startswith('UP') and idx >= 1:
                collection.move(idx, idx-1)
                exec("%s.index_%s -= 1" % (data, type))
            elif self.action.startswith('REMOVE'):
                info = 'removed %s' % (collection[idx].name)
                self.remove_items(tb, data, type, collection, idx)
                self.report({'INFO'}, info)

        scn.update()  # FIXME: update the viewports

        return {"FINISHED"}

    def remove_items(self, tb, data, type, collection, idx):
        """Remove items from TractBlender."""

        name = collection[idx].name
        tb_ob, ob_idx = tb_utils.active_tb_object()
        ob = bpy.data.objects[tb_ob.name]

        if self.action.endswith('_L1'):
            # remove all children
            exec("self.remove_%s_overlays(tb_ob, ob)" % type)
            # remove the object itself
            if type == 'voxelvolumes':
                self.remove_material(ob, name)
#             for ms in ob.material_slots:
#                 self.remove_material(ob, ms.name)  # FIXME: causes crash
            bpy.data.objects.remove(ob, do_unlink=True)

        else:
            if tb_ob.isvalid:
                tb_ov, ov_idx = tb_utils.active_tb_overlay()
                ob = bpy.data.objects[tb_ob.name]
                exec("self.remove_%s_%s(collection[idx], ob)" 
                     % (tb.objecttype, type))

        collection.remove(idx)
        exec("%s.index_%s -= 1" % (data, type))

    def remove_tracts_overlays(self, tb_ob, ob):
        """Remove tract scalars and labels."""

        for scalar in tb_ob.scalars:
            self.remove_tracts_scalars(scalar, ob)
        for label in tb_ob.labels:
            pass  # TODO

    def remove_surfaces_overlays(self, tb_ob, ob):
        """Remove surface scalars, labels and borders."""

        for scalar in tb_ob.scalars:
            self.remove_surfaces_scalars(scalar, ob)
        for label in tb_ob.labels:
            self.remove_surfaces_labels(label, ob)
        for bordergroup in tb_ob.bordergroups:
            self.remove_surfaces_bordergroups(bordergroup, ob)

    def remove_voxelvolumes_overlays(self, tb_ob, ob):
        """Remove voxelvolume scalars and labels."""

        for scalar in tb_ob.scalars:
            self.remove_voxelvolumes_scalars(scalar, ob)
        for label in tb_ob.labels:
            self.remove_voxelvolumes_labels(label, ob)

    def remove_tracts_scalars(self, scalar, ob):
        """Remove scalar overlay from tract."""

        for i, spline in enumerate(ob.data.splines):
            splname = scalar.name + '_spl' + str(i).zfill(8)
            self.remove_material(ob, splname)
            self.remove_image(ob, splname)

    def remove_tracts_labels(self, label, ob):
        """Remove scalar overlay from tract."""

        pass  # TODO

    def remove_surfaces_scalars(self, tb_ov, ob):
        """Remove scalar overlay from a surface."""

        # TODO: remove colourbars
        self.remove_vertexcoll(ob.vertex_groups, tb_ov.name)
        self.remove_vertexcoll(ob.data.vertex_colors, tb_ov.name)
        self.remove_material(ob, tb_ov.name)

    def remove_surfaces_labelgroups(self, tb_ov, ob):
        """Remove label group."""

        for label in tb_ov.labels:
            self.remove_surfaces_labels(label, ob)

    def remove_surfaces_labels(self, tb_ov, ob):
        """Remove label overlay from a surface."""

        self.remove_vertexcoll(ob.vertex_groups, tb_ov.name)
        self.remove_material(ob, tb_ov.name)

    def remove_surfaces_bordergroups(self, tb_ov, ob):
        """Remove border group."""

        for border in tb_ov.borders:
            self.remove_surfaces_borders(border, ob)
        bordergroup_ob = bpy.data.objects.get(tb_ov.name)
        bpy.data.objects.remove(bordergroup_ob, do_unlink=True)

    def remove_surfaces_borders(self, tb_ov, ob):
        """Remove border overlay from a surface."""

        border_ob = bpy.data.objects[tb_ov.name]
        bpy.data.objects.remove(border_ob, do_unlink=True)
        self.remove_material(ob, tb_ov.name)

    def remove_voxelvolumes_scalars(self, tb_ov, ob):
        """Remove scalar overlay from a voxelvolume."""

        self.remove_material(ob, tb_ov.name)
        ob = bpy.data.objects[tb_ov.name]
        bpy.data.objects.remove(ob, do_unlink=True)

    def remove_voxelvolumes_labels(self, tb_ov, ob):
        """Remove label overlay from a voxelvolume."""

        self.remove_material(ob, tb_ov.name)
        ob = bpy.data.objects[tb_ov.name]
        bpy.data.objects.remove(ob, do_unlink=True)

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

        item = coll.get(name)
        if item is not None:
            coll.remove(item)


class ImportTracts(Operator, ImportHelper):
    bl_idname = "tb.import_tracts"
    bl_label = "Import tracts"
    bl_description = "Import tracts as curves"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.vtk;*.bfloat;*.Bfloat;*.bdouble;*.Bdouble;" +
                "*.tck;*.trk;*.npy;*.npz;*.dpy")

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    interpolate_streamlines = FloatProperty(
        name="Interpolate streamlines",
        description="Interpolate the individual streamlines",
        default=1.,
        min=0.,
        max=1.)
    weed_tract = FloatProperty(
        name="Tract weeding",
        description="Retain a random selection of streamlines",
        default=1.,
        min=0.,
        max=1.)

    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial bevel on streamlines",
        default=True)
    colourtype = EnumProperty(
        name="",
        description="Apply this tract colour method",
        default="primary6",
        items=[("none", "none", "none", 1),
               ("golden_angle", "golden_angle", "golden_angle", 2),
               ("primary6", "primary6", "primary6", 3),
               ("random", "random", "random", 4),
               ("directional", "directional", "directional", 5),
               ("pick", "pick", "pick", 6)])
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour for the tract(s)",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.)

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        info = {}
        info['interpolate_streamlines'] = self.interpolate_streamlines
        info['weed_tract'] = self.weed_tract

        filenames = [file.name for file in self.files]
        tb_imp.import_objects(self.directory,
                              filenames,
                              tb_imp.import_tract,
                              "tracts",
                              self.name,
                              self.colourtype,
                              self.colourpicker,
                              self.transparency,
                              self.beautify,
                              info)

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout

        row = self.layout.row()
        row.prop(self, "name")
        row = self.layout.row()
        row.prop(self, "interpolate_streamlines")
        row = self.layout.row()
        row.prop(self, "weed_tract")

        row = self.layout.row()
        row.separator()
        row = self.layout.row()
        row.prop(self, "beautify")
        row = self.layout.row()
        row.label(text="Colour: ")
        row = self.layout.row()
        row.prop(self, "colourtype")
        row = self.layout.row()
        if self.colourtype == "pick":
            row.prop(self, "colourpicker")
        row = self.layout.row()
        row.prop(self, "transparency")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportSurfaces(Operator, ImportHelper):
    bl_idname = "tb.import_surfaces"
    bl_label = "Import surfaces"
    bl_description = "Import surfaces as mesh data"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.gii;*.obj;*.stl;*.white;*.pial;*.inflated")

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial smoothing on surfaces",
        default=True)
    colourtype = EnumProperty(
        name="",
        description="Apply this surface colour method",
        default="primary6",
        items=[("none", "none", "none", 1),
               ("golden_angle", "golden_angle", "golden_angle", 2),
               ("primary6", "primary6", "primary6", 3),
               ("random", "random", "random", 4),
               ("directional", "directional", "directional", 5),
               ("pick", "pick", "pick", 6)])
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour for the tract(s)",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.)

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        filenames = [file.name for file in self.files]
        tb_imp.import_objects(self.directory,
                              filenames,
                              tb_imp.import_surface,
                              "surfaces",
                              self.name,
                              self.colourtype,
                              self.colourpicker,
                              self.transparency,
                              self.beautify)

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout

        row = self.layout.row()
        row.prop(self, "name")

        row = self.layout.row()
        row.prop(self, "beautify")

        row = self.layout.row()
        row.label(text="Colour: ")
        row = self.layout.row()
        row.prop(self, "colourtype")
        row = self.layout.row()
        if self.colourtype == "pick":
            row.prop(self, "colourpicker")
        row = self.layout.row()
        row.prop(self, "transparency")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportVoxelvolumes(Operator, ImportHelper):
    bl_idname = "tb.import_voxelvolumes"
    bl_label = "Import voxelvolumes"
    bl_description = "Import voxelvolumes to textures"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial ... on voxelvolumes",
        default=True)

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        filenames = [file.name for file in self.files]
        tb_imp.import_voxelvolume(self.directory, filenames, self.name)

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout

        row = self.layout.row()
        row.prop(self, "name")

        row = self.layout.row()
        row.prop(self, "beautify")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportScalars(Operator, ImportHelper):
    bl_idname = "tb.import_scalars"
    bl_label = "Import scalar overlay"
    bl_description = "Import scalar overlay to vertexweights/colours"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_scalars(self.directory, filenames, self.name)

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportLabelGroups(Operator, ImportHelper):
    bl_idname = "tb.import_labelgroups"
    bl_label = "Import label overlay"
    bl_description = "Import label overlay to vertexgroups/colours"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_labels(self.directory, filenames, self.name)

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportBorderGroups(Operator, ImportHelper):
    bl_idname = "tb.import_bordergroups"
    bl_label = "Import bordergroup overlay"
    bl_description = "Import bordergroup overlay to curves"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_borders(self.directory, filenames, self.name)

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class MassIsRenderedObjects(Menu):
    bl_idname = "tb.mass_is_rendered_objects"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_ob'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_ob'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_ob'


class MassIsRenderedOverlays(Menu):
    bl_idname = "tb.mass_is_rendered_overlays"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_ov'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_ov'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_ov'


class MassSelect(Operator):
    bl_idname = "tb.mass_select"
    bl_label = "Mass select"
    bl_description = "Select/Deselect/Invert rendered objects/overlays"
    bl_options = {"REGISTER"}

    action = bpy.props.EnumProperty(
        items=(('SELECT_ob', "Select_ob", ""),
               ('DESELECT_ob', "Deselect_ob", ""),
               ('INVERT_ob', "Invert_ob", ""),
               ('SELECT_ov', "Select_ov", ""),
               ('DESELECT_ov', "Deselect_ov", ""),
               ('INVERT_ov', "Invert_ov", "")))

    def execute(self, context):

        scn = bpy.context.scene
        tb = scn.tb

        if self.action.endswith("_ob"):
            items = eval("tb.%s" % tb.objecttype)
        elif self.action.endswith("_ov"):
            tb_ob = tb_utils.active_tb_object()[0]
            items = eval("tb_ob.%s" % tb.overlaytype)

        for item in items:
            if self.action.startswith('SELECT'):
                item.is_rendered = True
            elif self.action.startswith('DESELECT'):
                item.is_rendered = False
            elif self.action.startswith('INVERT'):
                item.is_rendered = not item.is_rendered

        return {"FINISHED"}


class RevertLabel(Operator):
    bl_idname = "tb.revert_label"
    bl_label = "Revert label"
    bl_description = "Revert changes to imported label colour/transparency"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        tb = scn.tb

        tb_ov = tb_utils.active_tb_overlay()[0]
        type = tb.overlaytype.replace("groups", "s")
        idx = eval("tb_ov.index_%s" % type)
        item = eval("tb_ov.%s[%d]" % (type, idx))

        mat = bpy.data.materials[item.name]
        diff = mat.node_tree.nodes["Diffuse BSDF"]
        diff.inputs[0].default_value = item.colour
        mix2 = mat.node_tree.nodes["Mix Shader.001"]
        mix2.inputs[0].default_value = item.colour[3]

        return {"FINISHED"}


class TractBlenderScenePanel(Panel):
    """Host the TractBlender scene setup functionality"""
    bl_idname = "OBJECT_PT_tb_scene"
    bl_label = "TractBlender - Scene setup"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):

        scn = context.scene
        tb = scn.tb

        if tb.is_enabled:
            self.draw_tb_scene(self.layout, tb)
        else:
            switch_to_main_scene(self.layout, tb)

    def draw_tb_scene(self, layout, tb):

        obs = [ob for ob in bpy.data.objects
               if ob.type not in ["CAMERA", "LAMP", "EMPTY"]]
        sobs = bpy.context.selected_objects

        if obs:
            row = self.layout.row()
            col = row.column()
            col.prop(tb, "cam_view_enum")
            col = row.column()
            col.enabled = not tb.cam_view_enum == "Numeric"
            col.prop(tb, "cam_distance")
            row = self.layout.row()
            row.prop(tb, "cam_view")
            row.enabled = tb.cam_view_enum == "Numeric"
            row = self.layout.row()
            row.separator()
            row = self.layout.row()
            row.operator("tb.scene_preset",
                         text="Load scene preset",
                         icon="WORLD")
        else:
            row = self.layout.row()
            row.label(text="No geometry loaded ...")


class ScenePreset(Operator):
    bl_idname = "tb.scene_preset"
    bl_label = "Load scene preset"
    bl_description = "Setup up camera and lighting for this brain"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        tb_rp.scene_preset()

        return {"FINISHED"}


class VertexColourFromVertexGroups(Operator):
    bl_idname = "tb.vertexcolour_from_vertexgroups"
    bl_label = "Make vertex colour"
    bl_description = "Turn a set of vertex groups into a vertex paint map"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        tb_mat.vgs2vc()

        return {"FINISHED"}


class TractBlenderSettingsPanel(Panel):
    """Host the TractBlender settings"""
    bl_idname = "OBJECT_PT_tb_settings"
    bl_label = "TractBlender - Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):

        scn = context.scene
        tb = scn.tb

        if tb.is_enabled:
            self.draw_tb_settings(self.layout, tb)
        else:
            switch_to_main_scene(self.layout, tb)

    def draw_tb_settings(self, layout, tb):

        self.draw_nibabel(layout, tb)
        # TODO: etc

    def draw_nibabel(self, layout, tb):

        box = layout.box()
        row = box.row()
        row.prop(tb, "nibabel_use")
        if tb.nibabel_use:
            row.prop(tb, "nibabel_path")
            row = box.row()
            col = row.column()
            col.prop(tb, "nibabel_valid")
            col.enabled = False
            col = row.column()
            col.operator("tb.make_nibabel_persistent",
                         text="Make persistent",
                         icon="LOCKED")
            col.enabled = tb.nibabel_valid


class MakeNibabelPersistent(Operator):
    bl_idname = "tb.make_nibabel_persistent"
    bl_label = "Make nibabel persistent"
    bl_description = "Add script to /scripts/startup/ that loads shadow-python"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        addon_dir = dirname(__file__)
        tb_dir = dirname(addon_dir)
        scripts_dir = dirname(dirname(dirname(bpy.__file__)))
        startup_dir = join(scripts_dir, 'startup')
        basename = 'external_sitepackages'
        with open(join(startup_dir, basename + '.txt'), 'w') as f:
            f.write(scn.tb.nibabel_path)
        copy(join(addon_dir, basename + '.py'), startup_dir)

        return {"FINISHED"}


def switch_to_main_scene(layout, tb):

    row = layout.row()
    row.label(text="Please use the main scene for TractBlender.")
    row = layout.row()
    row.operator("tb.switch_to_main",
                 text="Switch to main",
                 icon="FORWARD")

def vgs2vc_enum_callback(self, context):
    """Populate the enum with vertex groups."""
    # FIXME: TypeError: EnumProperty(...):
    # maximum 32 members for a ENUM_FLAG type property

    items = []
    ob = context.selected_objects[0]
    for i, vg in enumerate(ob.vertex_groups):
        items.append((vg.name, vg.name, vg.name, i))

    return items


def validate_tb_objects(collections):
    """Validate that TractBlender objects can be found in Blender."""

    itemtype = "object"
    for collection in collections:
        for item in collection:
            try:
                ob = bpy.data.objects[item.name]
            except KeyError:
                print("The " + itemtype + " '" + item.name +
                      "' seems to have been removed or renamed " +
                      "outside of TractBlender")
                item.isvalid = False
            else:
                item.isvalid = True
                # descend into the object's vertexgroups
                validate_tb_overlays(ob, [item.scalars] + 
                                     [lg.labels for lg in item.labelgroups])


def validate_tb_overlays(ob, collections):
    """Validate that a TractBlender vertexgroup can be found in Blender."""

    itemtype = "vertexgroup"
    for collection in collections:
        for item in collection:
            try:
                vg = ob.vertex_groups[item.name]
            except KeyError:
                print("The " + itemtype + " '" + item.name +
                      "' seems to have been removed or renamed " +
                      "outside of TractBlender")
                item.isvalid = False
            else:
                item.isvalid = True


def nibabel_path_update(self, context):
    """Check whether nibabel can be imported."""

    tb_utils.validate_nibabel("")


def sformfile_update(self, context):
    """Set the sform transformation matrix for the object."""

    tb_ob = tb_utils.active_tb_object()[0]
    ob = bpy.data.objects[tb_ob.name]

    affine = tb_imp.read_affine_matrix(tb_ob.sformfile)
    ob.matrix_world = affine


def material_enum_callback(self, context):
    """Populate the enum based on available options."""
    # TODO: set the enum value on the basis of currect material?
    # TODO: handle multiple objects at once?

    tb_ob = tb_utils.active_tb_object()[0]
    ob = bpy.data.objects[tb_ob.name]

    items = []
    items.append(("none", "none",
                  "Add an empty material", 1))
    items.append(("pick", "pick",
                  "Add a material with the chosen colour", 2))
    items.append(("golden_angle", "golden angle",
                  "Add a material with golden angle colour increment", 3))
    items.append(("primary6", "primary6",
                  "Add a material of the primary6 set", 4))
    items.append(("random", "random",
                  "Add a material with a randomly picked colour", 5))
    if ob.type == "MESH":
        attrib = ob.data.vertex_colors
    elif ob.type == "CURVE":
        attrib = ob.data.materials
    if attrib.get("directional" + ob.type) is None:
        items.append(("directional", "directional",
                      "Add a material with directional colour-coding", 6))

    return items


def overlay_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    items = []
    items.append(("scalars", "scalars",
                  "List the scalar overlays", 1))
    items.append(("labelgroups", "labelgroups",
                  "List the label overlays", 2))
    if tb.objecttype == 'surfaces':
        items.append(("bordergroups", "bordergroups",
                      "List the bordergroups", 3))

    return items


def material_enum_update(self, context):
    """Assign a new preset material to the object."""

    tb_ob = tb_utils.active_tb_object()[0]
    ob = bpy.data.objects[tb_ob.name]

    tb_mat.materialise(ob, tb_ob.colourtype, tb_ob.colourpicker,
                       tb_ob.transparency)


def material_enum_set(self, value):
    """Set the value of the enum."""

    pass


def cam_view_enum_update(self, context):
    """Set the camview property from enum options."""

    if self.cam_view_enum == "Numeric":
        return

    scn = context.scene
    tb = scn.tb

    quadrants = {'Right': (1, 0, 0),
                 'Left': (-1, 0, 0),
                 'Ant': (0, 1, 0),
                 'Post': (0, -1, 0),
                 'Sup': (0, 0, 1),
                 'Inf': (0, 0, -1),
                 'RightAntSup': (1, 1, 1),
                 'RightAntInf': (1, 1, -1),
                 'RightPostSup': (1, -1, 1),
                 'RightPostInf': (1, -1, -1),
                 'LeftAntSup': (-1, 1, 1),
                 'LeftAntInf': (-1, 1, -1),
                 'LeftPostSup': (-1, -1, 1),
                 'LeftPostInf':  (-1, -1, -1)}
    cv_unit = mathutils.Vector(quadrants[self.cam_view_enum]).normalized()
    tb.cam_view = list(cv_unit * tb.cam_distance)


class ColorRampProperties(PropertyGroup):
    """Custom properties of color ramps."""

    name = StringProperty(
        name="Name",
        description="The name of the color stop.")
    nn_position = FloatProperty(
        name="nn_position",
        description="The non-normalized position of the color stop",
        default=0,
        precision=4)


class ScalarProperties(PropertyGroup):
    """Properties of scalar overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the scalar overlay")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the scalar overlay")
    icon = StringProperty(
        name="Icon",
        description="Icon for scalar overlays",
        default="FORCE_CHARGE")
    isvalid = BoolProperty(
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
    showcolourbar = BoolProperty(
        name="Render colourbar",
        description="Show/hide colourbar in rendered image",
        default=True)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)


class LabelProperties(PropertyGroup):
    """Properties of label overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay")
    icon = StringProperty(
        name="Icon",
        description="Icon for label overlays",
        default="BRUSH_VERTEXDRAW")
    isvalid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the label is rendered",
        default=True)
    value = IntProperty(
        name="Label value",
        description="The value of the label in vertexgroup 'scalarname'",
        default=0)
    colour = FloatVectorProperty(
        name="Label color",
        description="The color of the label in vertexgroup 'scalarname'",
        subtype="COLOR",
        size=4,
        min=0,
        max=1)


class BorderProperties(PropertyGroup):
    """Properties of border overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay")
    icon = StringProperty(
        name="Icon",
        description="Icon for border overlays",
        default="CURVE_BEZCIRCLE")
    isvalid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the border is rendered",
        default=True)
    group = StringProperty(
        name="Group",
        description="The group the border overlay belongs to")
    colour = FloatVectorProperty(
        name="Border color",
        description="The color of the border",
        subtype="COLOR",
        size=4,
        min=0,
        max=1)


class LabelGroupProperties(PropertyGroup):
    """Properties of label groups."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the label overlay")
    icon = StringProperty(
        name="Icon",
        description="Icon for label overlays",
        default="BRUSH_VERTEXDRAW")
    isvalid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the label is rendered",
        default=True)
    labels = CollectionProperty(
        type=LabelProperties,
        name="labels",
        description="The collection of loaded labels")
    index_labels = IntProperty(
        name="label index",
        description="index of the labels collection",
        default=0,
        min=0)


class BorderGroupProperties(PropertyGroup):
    """Properties of border groups."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the border overlay")
    icon = StringProperty(
        name="Icon",
        description="Icon for border overlays",
        default="CURVE_BEZCIRCLE")
    isvalid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the border is rendered",
        default=True)
    borders = CollectionProperty(
        type=BorderProperties,
        name="borders",
        description="The collection of loaded borders")
    index_borders = IntProperty(
        name="border index",
        description="index of the borders collection",
        default=0,
        min=0)


class TractProperties(PropertyGroup):
    """Properties of tracts."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the tract (default: filename)",
        default="")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the tract")
    icon = StringProperty(
        name="Icon",
        description="Icon for tract objects",
        default="CURVE_BEZCURVE")
    isvalid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    beautified = BoolProperty(
        name="Beautify",
        description="Apply initial bevel on streamlines",
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
    srow_x = FloatVectorProperty(
        name="srow_x",
        description="",
        default=[1.0, 0.0, 0.0, 0.0],
        size=4)
    srow_y = FloatVectorProperty(
        name="srow_y",
        description="",
        default=[0.0, 1.0, 0.0, 0.0],
        size=4)
    srow_z = FloatVectorProperty(
        name="srow_z",
        description="",
        default=[0.0, 0.0, 1.0, 0.0],
        size=4)

    scalars = CollectionProperty(
        type=ScalarProperties,
        name="scalars",
        description="The collection of loaded scalars")
    index_scalars = IntProperty(
        name="scalar index",
        description="index of the scalars collection",
        default=0,
        min=0)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=material_enum_callback,
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.)

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


class SurfaceProperties(PropertyGroup):
    """Properties of surfaces."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the surface (default: filename)",
        default="")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the surface")
    icon = StringProperty(
        name="Icon",
        description="Icon for surface objects",
        default="MESH_MONKEY")
    isvalid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    beautified = BoolProperty(
        name="Beautify",
        description="Apply initial smoothing on surface",
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
    srow_x = FloatVectorProperty(
        name="srow_x",
        description="",
        default=[1.0, 0.0, 0.0, 0.0],
        size=4)
    srow_y = FloatVectorProperty(
        name="srow_y",
        description="",
        default=[0.0, 1.0, 0.0, 0.0],
        size=4)
    srow_z = FloatVectorProperty(
        name="srow_z",
        description="",
        default=[0.0, 0.0, 1.0, 0.0],
        size=4)

    scalars = CollectionProperty(
        type=ScalarProperties,
        name="scalars",
        description="The collection of loaded scalars")
    index_scalars = IntProperty(
        name="scalar index",
        description="index of the scalars collection",
        default=0,
        min=0)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0)
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
        items=material_enum_callback,
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.0)


class VoxelvolumeProperties(PropertyGroup):
    """Properties of voxelvolumes."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the voxelvolume (default: filename)",
        default="")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the voxelvolume")
    icon = StringProperty(
        name="Icon",
        description="Icon for surface objects",
        default="MESH_GRID")
    isvalid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    beautified = BoolProperty(
        name="Beautify",
        description="",
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
    srow_x = FloatVectorProperty(
        name="srow_x",
        description="",
        default=[1.0, 0.0, 0.0, 0.0],
        size=4)
    srow_y = FloatVectorProperty(
        name="srow_y",
        description="",
        default=[0.0, 1.0, 0.0, 0.0],
        size=4)
    srow_z = FloatVectorProperty(
        name="srow_z",
        description="",
        default=[0.0, 0.0, 1.0, 0.0],
        size=4)

    scalars = CollectionProperty(
        type=ScalarProperties,
        name="scalars",
        description="The collection of loaded scalars")
    index_scalars = IntProperty(
        name="scalar index",
        description="index of the scalars collection",
        default=0,
        min=0)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=material_enum_callback,
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max in the data",
        default=(0, 0),
        size=2,
        precision=4)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)


class TractBlenderProperties(PropertyGroup):
    """Properties for the TractBlender panel."""

    try:
        import nibabel as nib
        nib_valid = True
        nib_path = os.path.dirname(os.path.dirname(nib.__file__))
    except:
        nib_valid = False
        nib_path = ""

    is_enabled = BoolProperty(
        name="Show/hide Tractblender",
        description="Show/hide the tractblender panel contents",
        default=True)

    nibabel_use = BoolProperty(
        name="use nibabel",
        description="Use nibabel to import nifti and gifti",
        default=True)
    nibabel_valid = BoolProperty(
        name="nibabel valid",
        description="Indicates whether nibabel has been detected",
        default=nib_valid)
    nibabel_path = StringProperty(
        name="nibabel path",
        description=""""
            The path to the site-packages directory
            of an equivalent python version with nibabel installed
            e.g. using:
            >>> conda create --name blender2.77 python=3.5.1
            >>> source activate blender2.77
            >>> pip install git+git://github.com/nipy/nibabel.git@master
            on Mac this would be the directory:
            <conda root dir>/envs/blender2.77/lib/python3.5/site-packages
            """,
        default=nib_path,
        subtype="DIR_PATH",
        update=nibabel_path_update)

    show_transform = BoolProperty(
        name="Transform",
        default=False,
        description="Show/hide the object's transform options")
    show_info = BoolProperty(
        name="Info",
        default=False,
        description="Show/hide the object's info")
    show_overlays = BoolProperty(
        name="Overlays",
        default=False,
        description="Show/hide the object's overlay options")
    show_appearance = BoolProperty(
        name="Base material",
        default=False,
        description="Show/hide the object's preset materials options")
    show_additional = BoolProperty(
        name="Additional options",
        default=False,
        description="Show/hide the object's additional options")
    show_items = BoolProperty(
        name="Items",
        default=False,
        description="Show/hide the group overlay's items")
    show_itemprops = BoolProperty(
        name="Item properties",
        default=False,
        description="Show/hide the properties of the item")

    objecttype = EnumProperty(
        name="object type",
        description="switch between object types",
        items=[("tracts", "tracts", "List the tracts", 1),
               ("surfaces", "surfaces", "List the surfaces", 2),
               ("voxelvolumes", "voxelvolumes", "List the voxelvolumes", 3)],
        default="tracts")

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

    overlaytype = EnumProperty(
        name="overlay type",
        description="switch between overlay types",
        items=overlay_enum_callback)

#     colourtype = EnumProperty(
#         name="material_presets",
#         description="Choose a material preset",
#         items=material_enum_callback,
#         update=material_enum_update)  # FIXME: set=material_enum_set
#     colourpicker = FloatVectorProperty(
#         name="",
#         description="Pick a colour for the brain structure",
#         default=[1.0, 1.0, 1.0],
#         subtype="COLOR")

#     vgs2vc = EnumProperty(
#         name="vgs2vc",
#         description="Select vertexgroups to turn into a vertexcolour",
#         options={"ENUM_FLAG"},
#         items=vgs2vc_enum_callback)
#     vginfo = CollectionProperty(
#         type=TractBlenderVertexGroupInfo,
#         name="VertexgroupInfo",
#         description="Keep track of info about vertexgroups")

    cam_view = FloatVectorProperty(
        name="Numeric input",
        description="Setting of the LR-AP-IS viewpoint of the camera",
        default=[2.31, 2.31, 2.31],
        size=3)

    cam_view_enum = EnumProperty(
        name="Camera viewpoint",
        description="Choose a view for the camera",
        default="RightAntSup",
        items=[("LeftPostInf", "Left-Post-Inf",
                "Left-Posterior-Inferior"),
               ("LeftPostSup", "Left-Post-Sup",
                "Left-Posterior-Superior"),
               ("LeftAntInf", "Left-Ant-Inf",
                "Left-Anterior-Inferior"),
               ("LeftAntSup", "Left-Ant-Sup",
                "Left-Anterior-Superior"),
               ("RightPostInf", "Right-Post-Inf",
                "Right-Posterior-Inferior"),
               ("RightPostSup", "Right-Post-Sup",
                "Right-Posterior-Superior"),
               ("RightAntInf", "Right-Ant-Inf",
                "Right-Anterior-Inferior"),
               ("RightAntSup", "Right-Ant-Sup",
                "Right-Anterior-Superior"),
               ("Inf", "Inf", "Inferior"),
               ("Sup", "Sup", "Superior"),
               ("Post", "Post", "Posterior"),
               ("Ant", "Ant", "Anterior"),
               ("Left", "Left", "Left"),
               ("Right", "Right", "Right"),
               ("Numeric", "Numeric", "Numeric")],
        update=cam_view_enum_update)

    cam_distance = FloatProperty(
        name="Camera distance",
        description="Relative distance of the camera (to bounding box)",
        default=4,
        min=1,
        update=cam_view_enum_update)


# =========================================================================== #


def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.tb = PointerProperty(type=TractBlenderProperties)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.Scene.tb

if __name__ == "__main__":
    register()
