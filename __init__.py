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

import os
from shutil import copy
import numpy as np
import mathutils
import re

from . import tractblender_import as tb_imp
from . import tractblender_materials as tb_mat
from . import tractblender_renderpresets as tb_rp
from . import tractblender_beautify as tb_beau
from . import tractblender_utils as tb_utils
from . import external_sitepackages as ext_sp


# =========================================================================== #


bl_info = {
    "name": "NeuroBlender",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 6),
    "blender": (2, 78, 4),
    "location": "Properties -> Scene -> NeuroBlender",
    "description": """"
        This add-on focusses on visualising MRI data.
        """,
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}


# =========================================================================== #


class TractBlenderBasePanel(Panel):
    """Host the TractBlender base geometry"""
    bl_idname = "OBJECT_PT_tb_geometry"
    bl_label = "NeuroBlender - Base"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):

        scn = context.scene
        tb = scn.tb

        if tb.is_enabled:
            self.draw_tb_panel(self.layout, tb)
        else:
            self.drawunit_switch_to_main(self.layout, tb)

    def draw_tb_panel(self, layout, tb):

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
            self.drawunit_tri(layout, "material", tb, tb_ob)
            if tb.objecttype == "voxelvolumes":
                self.drawunit_tri(layout, "slices", tb, tb_ob)
            self.drawunit_tri(layout, "info", tb, tb_ob)

    def drawunit_switch_to_main(self, layout, tb):

        row = layout.row()
        row.label(text="Please use the main scene for TractBlender.")
        row = layout.row()
        row.operator("tb.switch_to_main",
                     text="Switch to main",
                     icon="FORWARD")

    def drawunit_UIList(self, layout, uilistlevel, data, type, addopt=True):

        row = layout.row()
        row.template_list("ObjectList" + uilistlevel, "",
                          data, type,
                          data, "index_" + type,
                          rows=2)
        col = row.column(align=True)
        if addopt:
            if ((uilistlevel == "L2") and 
                data.path_from_id().startswith("tb.voxelvolumes")):
                type = "voxelvolumes"
            col.operator("tb.import_" + type,
                         icon='ZOOMIN',
                         text="").parentpath = data.path_from_id()
        col.operator("tb.oblist_ops",
                     icon='ZOOMOUT',
                     text="").action = 'REMOVE_' + uilistlevel
        col.menu("tb.mass_is_rendered_" + uilistlevel,
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
            icon = 'TRIA_DOWN'
        else:
            icon = 'TRIA_RIGHT'
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

    def drawunit_tri_material(self, layout, tb, tb_ob):

        if tb.objecttype == "voxelvolumes":
            row = layout.row()
            row.prop(tb_ob, "rendertype", expand=True)
            tex = bpy.data.textures[tb_ob.name]
            self.drawunit_texture(layout, tex, tb_ob)
        elif tb.objecttype == "surfaces":
            self.drawunit_material(layout, tb_ob)
            row = layout.row()
            row.separator()
            row = layout.row()
            row.prop(tb_ob, "sphere")
            row.operator("tb.unwrap_surface", text="Unwrap")
        else:
            self.drawunit_material(layout, tb_ob)

    def drawunit_tri_slices(self, layout, tb, tb_ob):

        self.drawunit_slices(layout, tb_ob)

    def drawunit_tri_info(self, layout, tb, tb_ob):

        row = layout.row()
        row.prop(tb_ob, "filepath")
        row.enabled = False

        if tb.objecttype == "tracts":

            row = layout.row()
            row.prop(tb_ob, "nstreamlines",
                     text="Number of streamlines", emboss=False)
            row.enabled = False

            row = layout.row()
            row.prop(tb_ob, "streamlines_interpolated",
                     text="Interpolation factor", emboss=False)
            row.enabled = False

            row = layout.row()
            row.prop(tb_ob, "tract_weeded",
                     text="Tract weeding factor", emboss=False)
            row.enabled = False

        elif tb.objecttype == 'surfaces':
            pass

        elif tb.objecttype == 'voxelvolumes':

            row = layout.row()
            row.prop(tb_ob, "texdir")

            row = layout.row()
            row.prop(tb_ob, "range",
                     text="Datarange", emboss=False)
            row.enabled = False

    def drawunit_material(self, layout, tb_ob):

        row = layout.row()
        row.prop(tb_ob, "colourtype", expand=True)
        self.drawunit_basic_cycles(layout, tb_ob)

    def drawunit_basic_cycles(self, layout, tb_ob):

        mat = bpy.data.materials[tb_ob.name]
        colour = mat.node_tree.nodes["RGB"].outputs[0]
        trans = mat.node_tree.nodes["Transparency"].outputs[0]
        row = layout.row()
        row.prop(colour, "default_value", text="Colour")
        row.prop(trans, "default_value", text="Transparency")
        # TODO: copy transparency from colourpicker (via driver?)
    #             nt.nodes["Diffuse BSDF"].inputs[0].default_value[3]
        if hasattr(tb_ob, "colour"):
            row.operator("tb.revert_label", icon='BACK', text="")

        nt = mat.node_tree
        row = layout.row()
        row.prop(nt.nodes["Diffuse BSDF"].inputs[1],
                 "default_value", text="diffuse")
        row.prop(nt.nodes["Glossy BSDF"].inputs[1],
                 "default_value", text="glossy")
        row.prop(nt.nodes["MixDiffGlos"].inputs[0],
                 "default_value", text="mix")

    def drawunit_texture(self, layout, tex, tb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(tex, "intensity")
        row.prop(tex, "contrast")
        row.prop(tex, "saturation")

        row = layout.row()
        row.separator()

        if tex.use_color_ramp:
            box = layout.box()
            self.drawunit_colourramp(box, tex, tb_coll)

    def drawunit_colourramp(self, layout, ramp, tb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        row.prop(tb_coll, "colourmap_enum", expand=False)

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
                              rows=2)

            row = layout.row()
            row.separator()
            row = layout.row()
            row.prop(tb_coll, "showcolourbar")
            if tb_coll.showcolourbar:
                row = layout.row()
                row.prop(tb_coll, "colourbar_size", text="size")
                row.prop(tb_coll, "colourbar_position", text="position")
                row = layout.row()
#                 nt = bpy.data.materials[tb_coll.name + "cbartext"].node_tree
#                 emit_in = nt.nodes["Emission"].inputs[0]
#                 row.prop(emit_in, "default_value", text="Textlabels")
                row.prop(tb_coll, "textlabel_colour", text="Textlabels")
                row.prop(tb_coll, "textlabel_placement", text="")
                row.prop(tb_coll, "textlabel_size", text="size")

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

    def drawunit_slices(self, layout, tb_ob, is_yoked=False):

        row = layout.row()
        col = row.column()
        col.prop(tb_ob, "slicethickness", expand=True, text="Thickness")
        col.enabled = not is_yoked
        col = row.column()
        col.prop(tb_ob, "sliceposition", expand=True, text="Position")
        col.enabled = not is_yoked
        col = row.column()
        col.prop(tb_ob, "sliceangle", expand=True, text="Angle")
        col.enabled = not is_yoked


class TractBlenderOverlayPanel(Panel):
    """Host the TractBlender overlay functions"""
    bl_idname = "OBJECT_PT_tb_overlays"
    bl_label = "NeuroBlender - Overlays"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    # delegate some methods
    draw = TractBlenderBasePanel.draw
    drawunit_switch_to_main = TractBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = TractBlenderBasePanel.drawunit_UIList
    drawunit_tri = TractBlenderBasePanel.drawunit_tri
    drawunit_basic_cycles = TractBlenderBasePanel.drawunit_basic_cycles
    drawunit_texture = TractBlenderBasePanel.drawunit_texture
    drawunit_colourramp = TractBlenderBasePanel.drawunit_colourramp
    calc_nn_elpos = TractBlenderBasePanel.calc_nn_elpos
    drawunit_slices = TractBlenderBasePanel.drawunit_slices

    def draw_tb_panel(self, layout, tb):

        obtype = tb.objecttype

        try:
            idx = eval("tb.index_%s" % obtype)
            tb_ob = eval("tb.%s[%d]" % (obtype, idx))
        except IndexError:
            row = self.layout.row()
            row.label(text="No " + obtype + " loaded ...")
        else:

            row = layout.row()
            row.prop(tb, "overlaytype", expand=True)

            self.drawunit_UIList(layout, "L2", tb_ob, tb.overlaytype)

            ovtype = tb.overlaytype
            try:
                ov_idx = eval("tb_ob.index_%s" % ovtype)
                tb_ov = eval("tb_ob.%s[%d]" % (ovtype, ov_idx))
            except IndexError:
                pass
            else:

                if ((ovtype == "scalargroups") and (len(tb_ov.scalars) > 1)):
                    row = layout.row()
                    row.template_list("ObjectListTS", "",
                                      tb_ov, "scalars",
                                      tb_ov, "index_scalars",
                                      rows=2, type="COMPACT")

                if obtype == 'surfaces':
                    row = layout.row()
                    col = row.column()
                    col.operator("tb.wp_preview", text="", icon="GROUP_VERTEX")
                    col = row.column()
                    col.operator("tb.vw2vc", text="", icon="GROUP_VCOL")
                    col = row.column()
                    col.operator("tb.vw2uv", text="", icon="GROUP_UVS")
                    col = row.column()
                    col.prop(tb, "uv_bakeall", toggle=True)

                elif obtype == "voxelvolumes":
                    row = layout.row()
                    row.prop(tb_ov, "rendertype", expand=True)

                if ovtype == "scalargroups":
                    self.drawunit_tri(layout, "overlay_material", tb, tb_ov)
                else:
                    self.drawunit_tri(layout, "items", tb, tb_ov)

                if obtype == "voxelvolumes":
                    self.drawunit_tri(layout, "overlay_slices", tb, tb_ov)

                self.drawunit_tri(layout, "overlay_info", tb, tb_ov)

    def drawunit_tri_overlay_material(self, layout, tb, tb_ov):

        # TODO: implement colourbar for all and move into UIList
        # row = layout.row()
        # row.prop(tb_ov, "showcolourbar")

        if tb.objecttype == "tracts":
            ng = bpy.data.node_groups.get("TractOvGroup")
            ramp = ng.nodes["ColorRamp"]
            box = layout.box()
            self.drawunit_colourramp(box, ramp, tb_ov)

        elif tb.objecttype == "surfaces":
            nt = bpy.data.materials[tb_ov.name].node_tree
            self.drawunit_material(layout, nt, tb_ov)

        elif tb.objecttype == "voxelvolumes":
            scalar = tb_ov.scalars[tb_ov.index_scalars]
            mat = bpy.data.materials[scalar.matname]
            tex = mat.texture_slots[scalar.tex_idx].texture
            self.drawunit_texture(layout, tex, tb_ov)

    def drawunit_tri_items(self, layout, tb, tb_ov):

        itemtype = tb.overlaytype.replace("groups", "s")
        self.drawunit_UIList(layout, "L3", tb_ov, itemtype, addopt=False)
        self.drawunit_tri(layout, "itemprops", tb, tb_ov)

    def drawunit_tri_itemprops(self, layout, tb, tb_ov):

        type = tb.overlaytype.replace("groups", "s")

        try:
            idx = eval("tb_ov.index_%s" % type)
            data = eval("tb_ov.%s[%d]" % (type, idx))
        except IndexError:
            pass
        else:
            exec("self.drawunit_%s(layout, tb, data)" % type)

    def drawunit_labels(self, layout, tb, tb_ov):

        if tb.objecttype == "voxelvolumes":
            tb_overlay = tb_utils.active_tb_overlay()[0]

            row = layout.row()
            row.label(text="Convenience access to label properties:")

            tex = bpy.data.textures[tb_overlay.name]
            el = tex.color_ramp.elements[tb_overlay.index_labels + 1]
            row = layout.row()
            row.prop(el, "color")

            mat = bpy.data.materials[tb_overlay.name]
            row = layout.row()
            row.prop(mat.texture_slots[0], "emission_factor")
            row.prop(mat.texture_slots[0], "emission_color_factor")

        else:
            self.drawunit_basic_cycles(layout, tb_ov)

    def drawunit_borders(self, layout, tb, tb_ov):

        self.drawunit_basic_cycles(layout, tb_ov)

        row = layout.row()
        row.separator()

        ob = bpy.data.objects[tb_ov.name]

        row = layout.row()
        row.label(text="Smoothing:")
        row.prop(ob.modifiers["smooth"], "factor")
        row.prop(ob.modifiers["smooth"], "iterations")

        row = layout.row()
        row.label(text="Bevel:")
        row.prop(ob.data, "bevel_depth")
        row.prop(ob.data, "bevel_resolution")

    def drawunit_material(self, layout, nt, tb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        row.prop(nt.nodes["Diffuse BSDF"].inputs[1],
                 "default_value", text="diffuse")
        row.prop(nt.nodes["Glossy BSDF"].inputs[1],
                 "default_value", text="glossy")
        row.prop(nt.nodes["MixDiffGlos"].inputs[0],
                 "default_value", text="mix")

        ramp = nt.nodes["ColorRamp"]
        box = layout.box()
        self.drawunit_colourramp(box, ramp, tb_coll)

    def drawunit_tri_overlay_slices(self, layout, tb, tb_ov):

        self.drawunit_slices(layout, tb_ov, tb_ov.is_yoked)
        row = layout.row()
        row.prop(tb_ov, "is_yoked", text="Follow parent")

    def drawunit_tri_overlay_info(self, layout, tb, tb_ov):

        row = layout.row()
        row.prop(tb_ov, "filepath")
        row.enabled = False

        if tb.overlaytype == "scalargroups":

            row = layout.row()
            row.prop(tb_ov, "texdir")

            row = layout.row()
            row.prop(tb_ov, "range")
#             row.enabled = False


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

            # TODO: display Ntracts for tracts
            # TODO: display range for voxelvolumes

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

            # TODO: display range for scalars
            # TODO: display Nitems for groups

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


class ObjectListCR(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        item_icon = "FULLSCREEN_ENTER"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)
            col = layout.column()
            col.prop(item, "nn_position", text="")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


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

            col = layout.column()
            col.alignment = "RIGHT"
            col.active = item.is_rendered
            col.prop(item, "is_rendered", text="", emboss=False,
                     translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


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

            col = layout.column()
            col.prop(item, "co", text="co", emboss=True,
                     translate=False, icon=item_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListTS(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text="Time index:")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListOperations(Operator):
    bl_idname = "tb.oblist_ops"
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
        tb = scn.tb

        collection, data = self.get_collection(context)

        try:
            item = collection[self.index]
        except IndexError:
            pass
        else:
            if (self.action.startswith('DOWN') and
                self.index < len(collection) - 1):
                collection.move(self.index, self.index + 1)
                exec("%s.index_%s += 1" % (data, self.type))
            elif self.action.startswith('UP') and self.index >= 1:
                collection.move(self.index, self.index - 1)
                exec("%s.index_%s -= 1" % (data, self.type))
            elif self.action.startswith('REMOVE'):
                info = ['removed %s' % (collection[self.index].name)]
                info += self.remove_items(tb, data, collection)
                self.report({'INFO'}, '; '.join(info))

        if self.type == "voxelvolumes":
            # TODO: update the index to tb.voxelvolumes in all drivers
            for i, vvol in enumerate(tb.voxelvolumes):
                slicebox = bpy.data.objects[vvol.name+"SliceBox"]
                for dr in slicebox.animation_data.drivers:
                    for var in dr.driver.variables:
                        for tar in var.targets:
                            dp = tar.data_path
                            idx = 16
                            if dp.index("tb.voxelvolumes[") == 0:
                                newpath = dp[:idx] + "%d" % i + dp[idx + 1:]
                                tar.data_path = dp[:idx] + "%d" % i + dp[idx + 1:]

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        tb_ob = tb_utils.active_tb_object()[0]

        if self.action.endswith('_L1'):
            self.type = tb.objecttype
            self.name = tb_ob.name
            self.index = eval("tb.%s.find(self.name)" % self.type)
            self.data_path = tb_ob.path_from_id()
        elif self.action.endswith('_L2'):
            tb_ov = tb_utils.active_tb_overlay()[0]
            self.type = tb.overlaytype
            self.name = tb_ov.name
            self.index = eval("tb_ob.%s.find(self.name)" % self.type)
            self.data_path = tb_ov.path_from_id()
        elif self.action.endswith('_L3'):
            tb_ov = tb_utils.active_tb_overlay()[0]
            tb_it = tb_utils.active_tb_overlayitem()[0]
            self.type = tb.overlaytype.replace("groups", "s")
            self.name = tb_it.name
            self.index = eval("tb_ov.%s.find(self.name)" % self.type)
            self.data_path = tb_it.path_from_id()
        elif self.action.endswith('_PL'):
            preset = eval("tb.presets[%d]" % tb.index_presets)
            light = preset.lights[preset.index_lights]
            self.type = "lights"
            self.name = light.name
            self.index = preset.index_lights
            self.data_path = light.path_from_id()
        elif self.action.endswith('_AN'):
            preset = eval("tb.presets[%d]" % tb.index_presets)
            animation = preset.animations[preset.index_animations]
            self.type = "animations"
            self.name = animation.name
            self.index = preset.index_animations
            self.data_path = animation.path_from_id()

        return self.execute(context)

    def get_collection(self, context):

        scn = context.scene
        tb = scn.tb

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

        return collection, data

    def remove_items(self, tb, data, collection):
        """Remove items from NeuroBlender."""

        info = []

        name = collection[self.index].name
        tb_ob, ob_idx = tb_utils.active_tb_object()

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
                fun(tb_ob, ob)
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
            print("remove AN")  # FIXME: TODO
            # for CamPath anim:
            # remove follow path constraint on camera
            # remove keyframes on TrackTo constraint influence
        else:
            tb_ov, ov_idx = tb_utils.active_tb_overlay()
            ob = bpy.data.objects[tb_ob.name]
            fun = eval("self.remove_%s_%s" % (tb.objecttype, self.type))
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

    def remove_voxelvolumes_overlays(self, tb_ob, ob):
        """Remove voxelvolume scalars and labels."""

        for sg in tb_ob.scalargroups:
            self.remove_voxelvolumes_scalargroups(sg, ob)
        for lg in tb_ob.labelgroups:
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

    def remove_voxelvolumes_labelgroups(self, labelgroup, ob):
        """Remove labelgroup overlay from a voxelvolume."""

        self.remove_material(ob, labelgroup.name)
        lg_ob = bpy.data.objects[labelgroup.name]
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

        item = coll.get(name)
        if item is not None:
            coll.remove(item)


class MassIsRenderedL1(Menu):
    bl_idname = "tb.mass_is_rendered_L1"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L1'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L1'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L1'


class MassIsRenderedL2(Menu):
    bl_idname = "tb.mass_is_rendered_L2"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L2'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L2'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L2'


class MassIsRenderedL3(Menu):
    bl_idname = "tb.mass_is_rendered_L3"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L3'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L3'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L3'


class MassIsRenderedPL(Menu):
    bl_idname = "tb.mass_is_rendered_PL"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_PL'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_PL'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_PL'


class MassIsRenderedAN(Menu):
    bl_idname = "tb.mass_is_rendered_AN"
    bl_label = "Animation Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_AN'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_AN'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_AN'


class MassIsRenderedCP(Menu):
    bl_idname = "tb.mass_is_rendered_CP"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_CP'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_CP'
        layout.operator("tb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_CP'


class MassSelect(Operator):
    bl_idname = "tb.mass_select"
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
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="tb")
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

        importtype = "tracts"
        impdict = {"weed_tract": self.weed_tract,
                   "interpolate_streamlines": self.interpolate_streamlines}
        beaudict = {"mode": "FULL",
                    "depth": 0.5,
                    "res": 10}

        self.import_objects(importtype, impdict, beaudict)

        return {"FINISHED"}

    def import_objects(self, importtype, impdict, beaudict):

        scn = bpy.context.scene
        tb = scn.tb

        importfun = eval("tb_imp.import_%s" % importtype[:-1])

        filenames = [file.name for file in self.files]
        if not filenames:
            filenames = os.listdir(self.directory)

        for f in filenames:
            fpath = os.path.join(self.directory, f)

            ca = [bpy.data.objects,
                  bpy.data.materials]
            name = tb_utils.check_name(self.name, fpath, ca)

            obs, info_imp, info_geom = importfun(fpath, name, "", impdict)

            for ob in obs:
                info_mat = tb_mat.materialise(ob,
                                              self.colourtype,
                                              self.colourpicker,
                                              self.transparency)
                info_beau = tb_beau.beautify_brain(ob,
                                                   importtype,
                                                   self.beautify,
                                                   beaudict)

            info = info_imp
            if tb.verbose:
                info = info + "\nname: '%s'\npath: '%s'\n" % (name, fpath)
                info = info + "%s\n%s\n%s" % (info_geom, info_mat, info_beau)

            self.report({'INFO'}, info)

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
        default="*.obj;*.stl;*.gii;*.white;*.pial;*.inflated;*.sphere;*.orig;*.blend")

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="tb")
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

    import_objects = ImportTracts.import_objects

    def execute(self, context):

        importtype = "surfaces"
        impdict = {}
        beaudict = {"iterations": 10,
                    "factor": 0.5,
                    "use_x": True,
                    "use_y": True,
                    "use_z": True}

        self.import_objects(importtype, impdict, beaudict)

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


def file_update(self, context):
    ca = [bpy.data.meshes, bpy.data.materials, bpy.data.textures]
    self.name = tb_utils.check_name(self.files[0].name, "", ca)


def name_update(self, context):
    self.texdir = "//voltex_%s" % self.name


def texdir_update(self, context):
    self.has_valid_texdir = tb_imp.check_texdir(self.texdir,
                                                self.texformat,
                                                overwrite=False)


def is_overlay_update(self, context):

    if self.is_overlay:
        try:
            tb_ob = tb_utils.active_tb_object()[0]
        except IndexError:
            pass  # no tb_obs found
        else:
            self.parentpath = tb_ob.path_from_id()
    else:
        self.parentpath = context.scene.tb.path_from_id()


# class ImportFilesCollection(PropertyGroup):
#     name = StringProperty(
#             name="File Path",
#             description="Filepath used for importing the file",
#             maxlen=1024,
#             subtype='FILE_PATH',
#             update=file_update)
# bpy.utils.register_class(ImportFilesCollection)


def h5_dataset_callback(self, context):
    """Populate the enum based on available options."""

    names = []

    def h5_dataset_add(name, obj):
        if isinstance(obj.id, h5py.h5d.DatasetID):
            names.append(name)

    try:
        import h5py
    except:
        pass
    else:
        f = h5py.File(os.path.join(self.directory, self.files[0].name), 'r')
        f.visititems(h5_dataset_add)
        f.close()
        items = [(name, name, "List the datatree", i)
                 for i, name in enumerate(names)]

        return items


class ImportVoxelvolumes(Operator, ImportHelper):
    bl_idname = "tb.import_voxelvolumes"
    bl_label = "Import voxelvolumes"
    bl_description = "Import voxelvolumes to textures"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath", type=OperatorFileListElement)
#     files = CollectionProperty(type=ImportFilesCollection)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.nii;*.nii.gz;*.img;*.hdr;*.h5;*.png;*.jpg;*.tif;*.tiff;")

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="voxelvolume",
        update=name_update)
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="tb")
    name_mode = EnumProperty(
        name="nm",
        description="...",
        default="filename",
        items=[("filename", "filename", "filename", 0),
               ("custom", "custom", "custom", 1)])
    is_overlay = BoolProperty(
        name="Is overlay",
        description="...",
        default=False,
        update=is_overlay_update)
    is_label = BoolProperty(
        name="Is label",
        description="...",
        default=False)
    sformfile = StringProperty(
        name="sformfile",
        description="",
        default="",
        subtype="FILE_PATH")
    has_valid_texdir = BoolProperty(
        name="has_valid_texdir",
        description="...",
        default=False)
    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        default="//",
        update=texdir_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)],
        update=texdir_update)
    overwrite = BoolProperty(
        name="overwrite",
        description="Overwrite existing texture directory",
        default=False)
    dataset = EnumProperty(
        name="Dataset",
        description="The the name of the hdf5 dataset",
        items=h5_dataset_callback)
    vol_idx = IntProperty(
        name="Volume index",
        description="The index of the volume to import (-1 for all)",
        default=-1)

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        filenames = [file.name for file in self.files]

        ca = [bpy.data.meshes, bpy.data.materials, bpy.data.textures]
        self.name = tb_utils.check_name(self.name, "", ca)

        item = tb_imp.import_voxelvolume(self.directory, filenames, self.name,
                                         self.is_overlay, self.is_label,
                                         self.parentpath, self.sformfile,
                                         self.texdir, self.texformat,
                                         self.overwrite, self.dataset,
                                         self.vol_idx)[1]
    #     force updates
        tb.index_voxelvolumes = tb.index_voxelvolumes
        item.rendertype = item.rendertype

        return {"FINISHED"}

    def draw(self, context):

        scn = context.scene
        tb = scn.tb

        layout = self.layout

        # FIXME: solve with update function
        if self.name_mode == "filename":
            voltexdir = [s for s in self.directory.split('/')
                         if "voltex_" in s]  # FIXME: generalize to other namings
            if voltexdir:
                self.name = voltexdir[0][7:]
            else:
                try:
                    self.name = self.files[0].name
                except IndexError:
                    pass

        row = layout.row()
        row.prop(self, "name_mode", expand=True)

        row = layout.row()
        row.prop(self, "name")

        try:
            name = self.files[0].name
        except:
            pass
        else:
            if name.endswith('.h5'):
                row = layout.row()
                row.prop(self, "dataset", expand=False)

        row = layout.row()
        row.prop(self, "vol_idx")

        row = layout.row()
        row.prop(self, "sformfile")

        row = layout.row()
        col = row.column()
        col.prop(self, "is_overlay")
        col = row.column()
        col.prop(self, "is_label")
        col.enabled = self.is_overlay
        row = layout.row()
        row.prop(self, "parentpath")
        row.enabled = self.is_overlay

        row = layout.row()
        row.prop(self, "texdir")
        row = layout.row()
        row.prop(self, "texformat")
        row = layout.row()
        row.prop(self, "has_valid_texdir")
        row.enabled = False
        row = layout.row()
        row.prop(self, "overwrite")
        row.enabled = self.has_valid_texdir

    def invoke(self, context, event):

        if self.parentpath.startswith("tb.voxelvolumes"):
            self.is_overlay = True

        if context.scene.tb.overlaytype == "labelgroups":
            self.is_label = True

        self.name = self.name
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportScalarGroups(Operator, ImportHelper):
    bl_idname = "tb.import_scalargroups"
    bl_label = "Import time series overlay"
    bl_description = "Import time series overlay to vertexweights/colours"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="")
    texdir = StringProperty(
        name="Texture directory",
        description="Directory with textures for this scalargroup",
        default="",
        subtype="DIR_PATH")  # TODO

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parentpath, "scalargroups")

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
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parentpath, "labelgroups")

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
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parentpath, "bordergroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class RevertLabel(Operator):
    bl_idname = "tb.revert_label"
    bl_label = "Revert label"
    bl_description = "Revert changes to imported label colour/transparency"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    def execute(self, context):

        scn = bpy.context.scene
        tb = scn.tb

        item = eval(self.data_path)

        mat = bpy.data.materials[item.name]
        rgb = mat.node_tree.nodes["RGB"]
        rgb.outputs[0].default_value = item.colour
        trans = mat.node_tree.nodes["Transparency"]
        trans.outputs[0].default_value = item.colour[3]

        return {"FINISHED"}

    def invoke(self, context, event):

        tb_it = tb_utils.active_tb_overlayitem()[0]
        self.data_path = tb_it.path_from_id()

        return self.execute(context)


class WeightPaintMode(Operator):
    bl_idname = "tb.wp_preview"
    bl_label = "wp_mode button"
    bl_description = "Go to weight paint mode for preview"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = bpy.context.scene

        tb_ob = tb_utils.active_tb_object()[0]
        scn.objects.active = bpy.data.objects[tb_ob.name]

        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")

        index_scalars_update_func()

        return {"FINISHED"}


class VertexWeight2VertexColors(Operator):
    bl_idname = "tb.vw2vc"
    bl_label = "VW to VC"
    bl_description = "Bake vertex group weights to vertex colours"
    bl_options = {"REGISTER"}

    itemname = StringProperty(
        name="Name",
        description="Specify the vertex group to bake",
        default="")
    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    index = IntProperty(
        name="index",
        description="index",
        default=-1)
    matname = StringProperty(
        name="Name",
        description="Specify the material to bake to",
        default="")

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        tb_ob = eval('.'.join(self.data_path.split('.')[:2]))
        group = eval('.'.join(self.data_path.split('.')[:3]))
        ob = bpy.data.objects[tb_ob.name]

        vcs = ob.data.vertex_colors
        vc = vcs.new(name=self.itemname)
        ob.data.vertex_colors.active = vc

        if hasattr(group, 'scalars'):
            scalar = eval(self.data_path)
            vgs = [ob.vertex_groups[scalar.name]]
            ob = tb_mat.assign_vc(ob, vc, vgs)
            mat = ob.data.materials[self.matname]
            nodes = mat.node_tree.nodes
            nodes["Attribute"].attribute_name = self.itemname

        elif hasattr(group, 'labels'):
            vgs = [ob.vertex_groups[label.name] for label in group.labels]
            ob = tb_mat.assign_vc(ob, vc, vgs, group, colour=[0.5, 0.5, 0.5])

        bpy.ops.object.mode_set(mode="VERTEX_PAINT")

        return {"FINISHED"}

    def invoke(self, context, event):

        tb_ob = tb_utils.active_tb_object()[0]
        tb_ov = tb_utils.active_tb_overlay()[0]
        tb_it = tb_utils.active_tb_overlayitem()[0]

        if hasattr(tb_ov, 'scalars'):
            self.index = tb_ov.index_scalars
        elif hasattr(tb_ov, 'labels'):
            self.index = tb_ov.index_labels

        self.data_path = tb_it.path_from_id()

        self.itemname = tb_it.name
        self.matname = tb_ov.name

        return self.execute(context)


class VertexWeight2UV(Operator, ExportHelper):
    bl_idname = "tb.vw2uv"
    bl_label = "Bake vertex weights"
    bl_description = "Bake vertex weights to texture (via vcol)"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    itemname = StringProperty(
        name="Name",
        description="Specify the vertex group to bake",
        default="")
    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    index = IntProperty(
        name="index",
        description="index",
        default=-1)
    matname = StringProperty(
        name="Name",
        description="Specify the material name for the group",
        default="")

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        tb_ob = eval('.'.join(self.data_path.split('.')[:2]))
        group = eval('.'.join(self.data_path.split('.')[:3]))

        # prep directory
        if not bpy.data.is_saved:
            bpy.ops.wm.save_as_mainfile()
        if not group.texdir:
            group.texdir = "//uvtex_%s" % group.name
        tb_utils.mkdir_p(bpy.path.abspath(group.texdir))

        # set the surface as active object
        surf = bpy.data.objects[tb_ob.name]
        for ob in bpy.data.objects:
            ob.select = False
        surf.select = True
        context.scene.objects.active = surf

        # save old and set new render settings for baking 
        samples = scn.cycles.samples
        preview_samples = scn.cycles.preview_samples
        scn.cycles.samples = 5
        scn.cycles.preview_samples = 5
        scn.cycles.bake_type = 'EMIT'

        # save old and set new materials for baking 
        ami = surf.active_material_index
        matnames = [ms.name for ms in surf.material_slots]
        surf.data.materials.clear()
        img = self.create_baking_material(surf, tb.uv_resolution, "bake_vcol")

        # select the item(s) to bake
        dp_split = re.findall(r"[\w']+", self.data_path)
        items = eval("group.%s" % dp_split[-2])
        if not tb.uv_bakeall:
            items = [items[self.index]]

        # bake
        vcs = surf.data.vertex_colors
        for i, item in enumerate(items):
            dp = item.path_from_id()
            bpy.ops.tb.vw2vc(itemname=item.name, data_path=dp,
                             index=i, matname="bake_vcol")
            img.source = 'GENERATED'
            bpy.ops.object.bake()
            img.filepath_raw = os.path.join(group.texdir, item.name[-5:] + ".png")
            img.save()
            vc = vcs[vcs.active_index]
            vcs.remove(vc)

        # reinstate materials and render properties
        surf.data.materials.pop(0)
        for matname in matnames:
            surf.data.materials.append(bpy.data.materials[matname])
        surf.active_material_index = ami
        scn.cycles.samples = samples
        scn.cycles.preview_samples = preview_samples

        return {"FINISHED"}

    def invoke(self, context, event):

        tb_ob = tb_utils.active_tb_object()[0]
        tb_ov = tb_utils.active_tb_overlay()[0]
        tb_it = tb_utils.active_tb_overlayitem()[0]

        if hasattr(tb_ov, 'scalars'):
            self.index = tb_ov.index_scalars
        elif hasattr(tb_ov, 'labels'):
            self.index = tb_ov.index_labels
        self.data_path = tb_it.path_from_id()
        self.itemname = tb_it.name
        self.matname = tb_ov.name

        if bpy.data.is_saved:
            return self.execute(context)
        else:
            bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT')
            return {"RUNNING_MODAL"}

    def create_baking_material(self, surf, uvres, name):
        """Create a material to bake vertex colours to."""

        mat = tb_mat.make_material_bake_cycles(name)
        surf.data.materials.append(mat)

        nodes = mat.node_tree.nodes
        itex = nodes['Image Texture']
        attr = nodes['Attribute']
        out = nodes['Material Output']

        img = bpy.data.images.new(name, width=uvres, height=uvres)
        img.file_format = 'PNG'
        img.source = 'GENERATED'
        itex.image = img
        attr.attribute_name = name

        for node in nodes:
            node.select = False
        out.select = True
        nodes.active = out

        return img

class UnwrapSurface(Operator):
    bl_idname = "tb.unwrap_surface"
    bl_label = "Unwrap surface"
    bl_description = "Unwrap a surface with sphere projection"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name_surface = StringProperty(
        name="Surface name",
        description="Specify the name for the surface to unwrap",
        default="")
    name_sphere = StringProperty(
        name="Sphere name",
        description="Specify the name for the sphere object to unwrap from",
        default="")

    def execute(self, context):

        scn = context.scene

        surf = bpy.data.objects[self.name_surface]
        sphere = bpy.data.objects[self.name_sphere]

        # select sphere and project
        for ob in bpy.data.objects:
            ob.select = False
        sphere.select = True
        scn.objects.active = sphere
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.sphere_project()
        bpy.ops.object.mode_set(mode='OBJECT')
        # TODO: perhaps do scaling here to keep all vertices within range

        # copy the UV map: select surf then sphere
        surf.select = True
        scn.objects.active = sphere
        bpy.ops.object.join_uvs()

        return {"FINISHED"}

    def invoke(self, context, event):

        tb_ob = tb_utils.active_tb_object()[0]
        self.name_surface = tb_ob.name
        self.name_sphere = tb_ob.sphere

        return self.execute(context)


class TractBlenderScenePanel(Panel):
    """Host the TractBlender scene setup functionality"""
    bl_idname = "OBJECT_PT_tb_scene"
    bl_label = "NeuroBlender - Scene setup"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = TractBlenderBasePanel.draw
    drawunit_switch_to_main = TractBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = TractBlenderBasePanel.drawunit_UIList
    drawunit_tri = TractBlenderBasePanel.drawunit_tri
    drawunit_basic_cycles = TractBlenderBasePanel.drawunit_basic_cycles

    def draw_tb_panel(self, layout, tb):

        self.drawunit_presets(layout, tb)

        try:
            idx = tb.index_presets
            preset = tb.presets[idx]
        except IndexError:
            pass
        else:
            row = layout.row()
            row.prop(preset, "name")

            row = layout.row()
            row.separator()

            self.drawunit_tri(layout, "bounds", tb, preset)
            self.drawunit_tri(layout, "cameras", tb, preset)
            self.drawunit_tri(layout, "lights", tb, preset)
            self.drawunit_tri(layout, "tables", tb, preset)
#             self.drawunit_tri(layout, "animations", tb, preset)

        row = layout.row()
        row.separator()
        obs = [ob for ob in bpy.data.objects
               if ob.type not in ["CAMERA", "LAMP", "EMPTY"]]
        sobs = bpy.context.selected_objects
        if obs:
            row = layout.row()
            row.operator("tb.scene_preset",
                         text="Load scene preset",
                         icon="WORLD")
            row.enabled = len(tb.presets) > 0
        else:
            row = layout.row()
            row.label(text="No geometry loaded ...")

    def drawunit_presets(self, layout, tb):

        row = layout.row()
        row.operator("tb.add_preset", icon='ZOOMIN', text="")
        row.prop(tb, "presets_enum", expand=False, text="")
        row.operator("tb.del_preset", icon='ZOOMOUT', text="")

    def drawunit_tri_bounds(self, layout, tb, preset):

        preset_ob = bpy.data.objects[preset.centre]
        row = layout.row()
        col = row.column()
        col.prop(preset_ob, "location")
        col = row.column()
        col.operator("tb.reset_presetcentre", icon='BACK', text="")

        col = row.column()
        col.prop(preset_ob, "scale")
#         col.prop(preset, "dims")
#         col.enabled = False
        col = row.column()
        col.operator("tb.reset_presetdims", icon='BACK', text="")

    def drawunit_tri_cameras(self, layout, tb, preset):

        try:
            cam = preset.cameras[0]
        except IndexError:
            cam = preset.cameras.add()
            preset.index_cameras = (len(preset.cameras)-1)
        else:
            cam_ob = bpy.data.objects[cam.name]

            row = layout.row()

            col = row.column()
            col.label("Quick camera view:")
            row1 = col.row()
            row1.prop(cam, "cam_view_enum_LR", expand=True)
            row1 = col.row()
            row1.prop(cam, "cam_view_enum_AP", expand=True)
            row1 = col.row()
            row1.prop(cam, "cam_view_enum_IS", expand=True)

            col.prop(cam, "cam_distance", text="distance")

            col = row.column()
            col.label("")
            row1 = col.row()
            row1.prop(cam_ob, "location", index=0, text="X")
            row1 = col.row()
            row1.prop(cam_ob, "location", index=1, text="Y")
            row1 = col.row()
            row1.prop(cam_ob, "location", index=2, text="Z")

            # consider more choices of camera properties (lens, clip, trackto)

    def drawunit_tri_lights(self, layout, tb, preset):

        lights = bpy.data.objects[preset.lightsempty]
        row = layout.row()
        col = row.column()
        col.prop(lights, "rotation_euler", index=2, text="Rotate rig (Z)")
        col = row.column()
        col.prop(lights, "scale", index=2, text="Scale rig (XYZ)")

        row = layout.row()
        row.separator()

        self.drawunit_UIList(layout, "PL", preset, "lights", addopt=True)
        self.drawunit_lightprops(layout, preset.lights[preset.index_lights])

    def drawunit_lightprops(self, layout, light):

        light_ob = bpy.data.objects[light.name]

        row = layout.row()
        col = row.column()
        col.label("Quick lighting rig access:")
        col.prop(light, "name")
        col.prop(light, "type", text="")
        col.prop(light, "strength")

        col = row.column()
        col.prop(light_ob, "location")

        row = layout.row()
        if light.type == "PLANE":
            row = layout.row()
            row.prop(light, "size")

    def drawunit_tri_tables(self, layout, tb, preset):

        try:
            tab = preset.tables[0]
        except IndexError:
            # tab = tb_rp.create_table(preset.name+"DissectionTable")
            tab = preset.tables.add()
            preset.index_tables = (len(preset.tables)-1)
        else:
            row = layout.row()
            row.prop(tab, "is_rendered", toggle=True)
            row = layout.row()
            self.drawunit_basic_cycles(layout, tab)


class ResetPresetCentre(Operator):
    bl_idname = "tb.reset_presetcentre"
    bl_label = "Reset preset centre"
    bl_description = "Revert changes preset to preset centre"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        tb = scn.tb

        obs = tb_rp.get_render_objects(tb)
        centre_location = tb_rp.get_brainbounds(obs)[0]

        tb_preset = tb.presets[tb.index_presets]
        name = tb_preset.centre
        centre = bpy.data.objects[name]
        centre.location = centre_location

        infostring = 'reset location of preset "%s"'
        info = [infostring % tb_preset.name]
        infostring = 'location is now "%s"'
        info += [infostring % ' '.join('%.2f' % l for l in centre_location)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class ResetPresetDims(Operator):
    bl_idname = "tb.reset_presetdims"
    bl_label = "Recalculate scene dimensions"
    bl_description = "Recalculate scene dimension"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        tb = scn.tb

        obs = tb_rp.get_render_objects(tb)
        dims = tb_rp.get_brainbounds(obs)[1]

        tb_preset = tb.presets[tb.index_presets]
        name = tb_preset.centre
        centre = bpy.data.objects[name]
        centre.scale = 0.5 * mathutils.Vector(dims)

        tb.presets[tb.index_presets].dims = dims

        infostring = 'reset dimensions of preset "%s"'
        info = [infostring % tb_preset.name]
        infostring = 'dimensions are now "%s"'
        info += [infostring % ' '.join('%.2f' % d for d in dims)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class AddPreset(Operator):
    bl_idname = "tb.add_preset"
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
        default="tb")

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        ca = [tb.presets]
        name = tb_utils.check_name(self.name, "", ca, firstfill=1)

        tb_rp.scene_preset_init(name)
        tb.presets_enum = name

        infostring = 'added preset "%s"'
        info = [infostring % name]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class DelPreset(Operator):
    bl_idname = "tb.del_preset"
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
        tb = scn.tb

        info = []

        if self.name:  # got here through cli
            try:
                tb.presets[self.name]
            except KeyError:
                infostring = 'no preset with name "%s"'
                info = [infostring % self.name]
                self.report({'INFO'}, info[0])
                return {"CANCELLED"}
            else:
                self.index = tb.presets.find(self.name)
        else:  # got here through invoke
            self.name = tb.presets[self.index].name

        info = self.delete_preset(tb.presets[self.index], info)
        tb.presets.remove(self.index)
        tb.index_presets -= 1
        infostring = 'removed preset "%s"'
        info = [infostring % self.name] + info

        try:
            name = tb.presets[0].name
        except IndexError:
            infostring = 'all presets have been removed'
            info += [infostring]
        else:
            tb.presets_enum = name
            infostring = 'preset is now "%s"'
            info += [infostring % name]

        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        self.index = tb.index_presets
        self.name = ""

        return self.execute(context)

    def delete_preset(self, tb_preset, info=[]):
        """Delete a preset."""

        # unlink all objects from the rendering scenes
        for s in ['_cycles', '_internal']:
            sname = tb_preset.name + s
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
        ps_obnames = [tb_ob.name
                      for tb_coll in [tb_preset.cameras,
                                      tb_preset.lights,
                                      tb_preset.tables]
                      for tb_ob in tb_coll]
        ps_obnames += [tb_preset.lightsempty,
                       tb_preset.box,
                       tb_preset.centre,
                       tb_preset.name]
        for ps_obname in ps_obnames:
            try:
                ob = bpy.data.objects[ps_obname]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % ps_obname]
            else:
                bpy.data.objects.remove(ob)

        for ps_cam in tb_preset.cameras:
            try:
                cam = bpy.data.cameras[ps_cam.name]
            except KeyError:
                infostring = 'camera "%s" not found'
                info += [infostring % ps_cam.name]
            else:
                bpy.data.cameras.remove(cam)

        for ps_lamp in tb_preset.lights:
            try:
                lamp = bpy.data.lamps[ps_lamp.name]
            except KeyError:
                infostring = 'lamp "%s" not found'
                info += [infostring % ps_lamp.name]
            else:
                bpy.data.lamps.remove(lamp)

        for ps_mesh in tb_preset.tables:
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
    bl_idname = "tb.import_lights"
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
        default="tb")
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
        tb = scn.tb

        tb_preset = tb.presets[self.index]
        preset = bpy.data.objects[tb_preset.name]
        centre = bpy.data.objects[tb_preset.centre]
        box = bpy.data.objects[tb_preset.box]
        lights = bpy.data.objects[tb_preset.lightsempty]

        ca = [tb_preset.lights]
        name = tb_utils.check_name(self.name, "", ca)

        lp = {'name': name,
              'type': self.type,
              'size': self.size,
              'colour': self.colour,
              'strength': self.strength,
              'location': self.location}
        tb_light = tb_utils.add_item(tb_preset, "lights", lp)
        tb_rp.create_light(preset, centre, box, lights, lp)

        infostring = 'added light "%s" in preset "%s"'
        info = [infostring % (name, tb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        self.index = tb.index_presets

        return self.execute(context)

class ScenePreset(Operator):
    bl_idname = "tb.scene_preset"
    bl_label = "Load scene preset"
    bl_description = "Setup up camera and lighting for this brain"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        tb_rp.scene_preset()

        return {"FINISHED"}


class SetAnimations(Operator):
    bl_idname = "tb.set_animations"
    bl_label = "Set animations"
    bl_description = "(Re)set all animation in the preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        tb_rp.set_animations()

        return {"FINISHED"}


class TractBlenderAnimationPanel(Panel):
    """Host the TractBlender animation functionality"""
    bl_idname = "OBJECT_PT_tb_animation"
    bl_label = "NeuroBlender - Animations"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = TractBlenderBasePanel.draw
    drawunit_switch_to_main = TractBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = TractBlenderBasePanel.drawunit_UIList
    drawunit_tri = TractBlenderBasePanel.drawunit_tri

    def draw_tb_panel(self, layout, tb):

        try:
            idx = tb.index_presets
            preset = tb.presets[idx]
        except IndexError:
            row = layout.row()
            row.label(text="No presets loaded ...")
        else:
            self.drawunit_animations(layout, tb, preset)

        row = layout.row()
        row.separator()
        obs = [ob for ob in bpy.data.objects
               if ob.type not in ["CAMERA", "LAMP", "EMPTY"]]
        sobs = bpy.context.selected_objects
        row = layout.row()
        row.operator("tb.set_animations",
                     text="Set animations",
                     icon="RENDER_ANIMATION")

    def drawunit_animations(self, layout, tb, preset):

        row = layout.row()
        # consider preset.frame_start and frame_end (min frame_start=1)
        row.prop(bpy.context.scene, "frame_start")
        row.prop(bpy.context.scene, "frame_end")

        row = layout.row()
        self.drawunit_UIList(layout, "AN", preset, "animations")

        if len(preset.animations) > 0:

            row = layout.row()
            row.separator()

            anim = preset.animations[preset.index_animations]

            row = layout.row()
            row.prop(anim, "name")

            row = layout.row()
            row.separator()

            row = layout.row()
            row.prop(anim, "animationtype", expand=True)

            row = layout.row()
            row.separator()

            row = layout.row()
            row.prop(anim, "frame_start")
            row.prop(anim, "frame_end")
            row = layout.row()
            row.prop(anim, "repetitions")
            row.prop(anim, "offset")

            row = layout.row()
            row.separator()

            if anim.animationtype == "CameraPath":

                row = layout.row()

                row.label("Camera path:")

                row = layout.row()
                col = row.column()
                col.prop(anim, "reverse", toggle=True, icon="ARROW_LEFTRIGHT", icon_only=True)
                col = row.column()
                col.prop(anim, "campaths_enum", expand=False, text="")
                col = row.column()
                col.operator("tb.del_campath", icon='ZOOMOUT', text="")
                col.enabled = True

                self.drawunit_tri(layout, "points", tb, anim)

                self.drawunit_tri(layout, "newpath", tb, anim)

                row = layout.row()
                row.separator()

                row = layout.row()
                row.label("Camera tracking:")
                row = layout.row()
                row.prop(anim, "tracktype", expand=True)
                tb_cam = preset.cameras[0]
                cam_ob = bpy.data.objects[tb_cam.name]
                row = layout.row()
                row.prop(cam_ob, "rotation_euler", index=2, text="tumble")
                cam = bpy.data.cameras[tb_cam.name]
                row.prop(cam, "clip_start")
                row.prop(cam, "clip_end")

            elif anim.animationtype == "Slices":

                row = layout.row()
                col = row.column()
                col.prop(anim, "anim_voxelvolume", expand=False, text="Voxelvolume")
                col = row.column()
                col.operator("tb.del_campath", icon='ZOOMOUT', text="")
                col.enabled = False

                row = layout.row()
                row.separator()

                row = layout.row()
                row.prop(anim, "sliceproperty", expand=True)

                row = layout.row()
                row.separator()

                row = layout.row()
                row.prop(anim, "reverse", toggle=True)

                row = layout.row()
                row.separator()

                row = layout.row()
                row.prop(anim, "axis", expand=True)


            elif anim.animationtype == "TimeSeries":

                row = layout.row()
                col = row.column()
                col.prop(anim, "timeseries_object", expand=False, text="Object")
                row = layout.row()
                col = row.column()
                col.prop(anim, "anim_timeseries", expand=False, text="Time series")

                sgs = tb_rp.find_ts_scalargroups(anim)
                sg = sgs[anim.anim_timeseries]

                npoints = len(sg.scalars)
                row = layout.row()
                row.label("%d points in time series" % npoints)

    def drawunit_tri_points(self, layout, tb, anim):

        row = layout.row()
        row.operator("tb.add_campoint",
                     text="Add point at camera position")

        try:
            cu = bpy.data.objects[anim.campaths_enum].data
            data = cu.splines[0]
        except:
            pass
        else:
            if len(data.bezier_points):
                ps = "bezier_points"
            else:
                ps = "points"

            row = layout.row()
            row.template_list("ObjectListCP", "",
                              data, ps,
                              data, "material_index", rows=2,
                              maxrows=4, type="DEFAULT")

    def drawunit_tri_newpath(self, layout, tb, anim):

        row = layout.row()
        row.prop(anim, "pathtype", expand=True)

        row = layout.row()
        if anim.pathtype == 'Circular':
            row = layout.row()
            row.prop(anim, "axis", expand=True)
        elif anim.pathtype == 'Streamline':
            row = layout.row()
            row.prop(anim, "anim_tract", text="")
            row.prop(anim, "spline_index")
        elif anim.pathtype == 'Select':
            row = layout.row()
            row.prop(anim, "anim_curve", text="")
        elif anim.pathtype == 'Create':
            pass  # name, for every options?

        row = layout.row()
        row.separator()

        row = layout.row()
        row.operator("tb.add_campath", text="Add trajectory")


class AddAnimation(Operator):
    bl_idname = "tb.import_animations"
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
        default="tb")

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        ca = [preset.animations for preset in tb.presets]
        name = tb_utils.check_name(self.name, "", ca, forcefill=True)
        tb_imp.add_animation_to_collection(name)

        tb_preset = tb.presets[tb.index_presets]  # FIXME: self
        infostring = 'added animation "%s" in preset "%s"'
        info = [infostring % (name, tb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        self.index_presets = tb.index_presets

        return self.execute(context)


class AddCamPoint(Operator):
    bl_idname = "tb.add_campoint"
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
        tb = scn.tb

        preset = tb.presets[self.index_presets]
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
        tb = scn.tb

        self.index_presets = tb.index_presets
        preset = tb.presets[self.index_presets]

        self.index_animations = preset.index_animations

        cam = bpy.data.objects[preset.cameras[0].name]
        centre = bpy.data.objects[preset.centre]

        self.co[0] = cam.location[0] * preset.dims[0] / 2 + centre.location[0]
        self.co[1] = cam.location[1] * preset.dims[1] / 2 + centre.location[1]
        self.co[2] = cam.location[2] * preset.dims[2] / 2 + centre.location[2]

        return self.execute(context)


class AddCamPath(Operator):
    bl_idname = "tb.add_campath"
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
        tb = scn.tb

        preset = tb.presets[self.index_presets]
        anim = preset.animations[self.index_animations]

        if self.pathtype == "Circular":
            name = "CP_%s" % (self.axis)
        elif self.pathtype == "Streamline":
            name = "CP_%s_%05d" % (self.anim_tract, self.spline_index)
        elif self.pathtype == "Select":
            name = "CP_%s" % (anim.anim_curve)
        elif self.pathtype == "Create":
            name = "CP_%s" % ("fromCam")

        ca = [tb.campaths]
        name = self.name or name
        name = tb_utils.check_name(name, "", ca)
        fun = eval("self.campath_%s" % self.pathtype.lower())
        campath, info = fun(name)

        if campath is not None:
            campath.hide_render = True
            campath.parent = bpy.data.objects[preset.name]
            tb_imp.add_campath_to_collection(name)
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
        tb = scn.tb

        self.index_presets = tb.index_presets
        preset = tb.presets[self.index_presets]
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
        tb = scn.tb

        preset = tb.presets[self.index_presets]
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
            tb_ob = bpy.data.objects[self.anim_tract]
            spline = tb_ob.data.splines[self.spline_index]
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
            tb_imp.make_polyline_ob(curve, streamline)
            ob.matrix_world = tb_ob.matrix_world

            infostring = 'copied path from tract "%s:spline[%s]"'

        info = [infostring % (self.anim_tract, self.spline_index)]

        return ob, info

    def campath_select(self, name):
        """Generate a campath by copying it from a curve object."""

        scn = bpy.context.scene

        try:
            cu = bpy.data.objects[self.anim_curve].data.copy()
        except KeyError:
            ob = None
            infostring = 'curve "%s" not found'
        else:
            ob = bpy.data.objects.new(name, cu)
            scn.objects.link(ob)
            scn.update()
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
    bl_idname = "tb.del_campath"
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
        tb = scn.tb

        try:
            campath = bpy.data.objects[self.name]
            cu = bpy.data.curves[self.name]
        except KeyError:
            infostring = 'camera path curve "%s" not found'
        else:
            bpy.data.curves.remove(cu)
            bpy.data.objects.remove(campath)
            tb.campaths.remove(tb.campaths.find(self.name))
            tb.index_campaths = 0
            # TODO: find and reset all animations that use campath
            infostring = 'removed camera path curve "%s"'

        info = [infostring % self.name]

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        self.index_presets = tb.index_presets
        preset = tb.presets[self.index_presets]
        self.index_animations = preset.index_animations
        anim = preset.animations[self.index_animations]
        self.name = anim.campaths_enum

        return self.execute(context)


class TractBlenderSettingsPanel(Panel):
    """Host the TractBlender settings"""
    bl_idname = "OBJECT_PT_tb_settings"
    bl_label = "NeuroBlender - Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = TractBlenderBasePanel.draw
    drawunit_switch_to_main = TractBlenderBasePanel.drawunit_switch_to_main

    def draw_tb_panel(self, layout, tb):

        row = layout.row()
        row.prop(tb, "mode")
        self.draw_nibabel(layout, tb)
        row = layout.row()
        row.prop(tb, "verbose")
        row = layout.row()
        row.prop(tb, "uv_resolution")
        row = layout.row()
        row.prop(tb, "texformat")

        row = layout.row()
        row.prop(tb, "projectdir")

        row = layout.row()
        row.prop(tb, "texmethod")

        row = layout.row()
        row.operator("tb.reload",
                     text="Reload NeuroBlender",
                     icon="RECOVER_LAST")
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

        addon_dir = os.path.dirname(__file__)
        tb_dir = os.path.dirname(addon_dir)
        scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname(bpy.__file__)))
        startup_dir = os.path.join(scripts_dir, 'startup')
        basename = 'external_sitepackages'
        nibdir_txt = os.path.join(startup_dir, basename + '.txt')
        with open(nibdir_txt, 'w') as f:
            f.write(scn.tb.nibabel_path)
        es_fpath = os.path.join(addon_dir, basename + '.py')
        copy(es_fpath, startup_dir)

        infostring = 'added nibabel path "%s" to startup "%s"'
        info = [infostring % (scn.tb.nibabel_path, startup_dir)]

        return {"FINISHED"}


class SwitchToMainScene(Operator):
    bl_idname = "tb.switch_to_main"
    bl_label = "Switch to main"
    bl_description = "Switch to main TractBlender scene to import"
    bl_options = {"REGISTER"}

    def execute(self, context):

        context.window.screen.scene = bpy.data.scenes["Scene"]

        return {"FINISHED"}


class SaveBlend(Operator, ExportHelper):
    bl_idname = "tb.save_blend"
    bl_label = "Save blend file"
    bl_description = "Prompt to save a blend file"
    bl_options = {"REGISTER"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath", type=OperatorFileListElement)
    filename_ext = StringProperty(subtype="NONE")

    def execute(self, context):

        bpy.ops.wm.save_as_mainfile(filepath=self.properties.filepath)

        return {"FINISHED"}

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

class Reload(Operator):
    bl_idname = "tb.reload"
    bl_label = "Reload"
    bl_description = "Reload"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="name",
        description="The name of the addon",
        default="TractBlender")
    path = StringProperty(
        name="path",
        description="The path to the NeuroBlender zip file",
        default="/Users/michielk/workspace/TractBlender/TractBlender.zip")

    def execute(self, context):

        bpy.ops.wm.addon_install(filepath=self.path)
        bpy.ops.wm.addon_enable(module=self.name)

        return {"FINISHED"}


def nibabel_path_update(self, context):
    """Check whether nibabel can be imported."""

    tb_utils.validate_nibabel("")


def sformfile_update(self, context):
    """Set the sform transformation matrix for the object."""

    try:
        ob = bpy.data.objects[self.name]
    except:
        pass
    else:
        sformfile = bpy.path.abspath(self.sformfile)
        affine = tb_imp.read_affine_matrix(sformfile)
        ob.matrix_world = affine


def slices_update(self, context):
    """Set slicethicknesses and positions for the object."""

    ob = bpy.data.objects[self.name+"SliceBox"]
    ob.scale = self.slicethickness

    try:
        scalar = self.scalars[self.index_scalars]  # FIXME: should this be scalargroups?
    except:
        matname = self.name
        mat = bpy.data.materials[matname]
        mat.type = mat.type
        mat.texture_slots[0].scale[0] = mat.texture_slots[0].scale[0]
    else:
        for scalar in self.scalars:
            mat = bpy.data.materials[scalar.matname]
            tss = [ts for ts in mat.texture_slots if ts is not None]
            for ts in tss:
                ts.scale[0] = ts.scale[0]


def rendertype_enum_update(self, context):
    """Set surface or volume rendering for the voxelvolume."""

    try:
        matnames = [scalar.matname for scalar in self.scalars]
    except:
        matnames = [self.name]
    else:
        matnames = set(matnames)
 
    # FIXME: vvol.rendertype ideally needs to switch if mat.type does
    for matname in matnames:
        mat = bpy.data.materials[matname]
        mat.type = self.rendertype
        tss = [ts for ts in mat.texture_slots if ts is not None]
        for ts in tss:
            if mat.type == 'VOLUME':
                    for idx in range(0, 3):
                        ts.driver_remove("scale", idx)
                        ts.driver_remove("offset", idx)
                    ts.scale = [1, 1, 1]
                    ts.offset = [0, 0, 0]
            elif mat.type == 'SURFACE':
                for idx in range(0, 3):
                    tb_imp.voxelvolume_slice_drivers_surface(self, ts, idx, "scale")
                    tb_imp.voxelvolume_slice_drivers_surface(self, ts, idx, "offset")


def is_yoked_bool_update(self, context):
    """Add or remove drivers linking voxelvolume and overlay."""

    tb_ob = tb_utils.active_tb_object()[0]
    for prop in ['slicethickness', 'sliceposition', 'sliceangle']:
        for idx in range(0, 3):
            if self.is_yoked:
                tb_imp.voxelvolume_slice_drivers_yoke(tb_ob, self, prop, idx)
            else:
                self.driver_remove(prop, idx)


def mat_is_yoked_bool_update(self, context):
    """Add or remove drivers linking overlay's materials."""

    pass
#     tb_ob = tb_utils.active_tb_object()[0]
#     for prop in ['slicethickness', 'sliceposition', 'sliceangle']:
#         for idx in range(0, 3):
#             if self.is_yoked:
#                 tb_imp.voxelvolume_slice_drivers_yoke(tb_ob, self, prop, idx)
#             else:
#                 self.driver_remove(prop, idx)


def mode_enum_update(self, context):
    """Perform actions for updating mode."""

    scn = context.scene
    tb = scn.tb

    tb_preset = tb.presets[self.index_presets]
    tb_cam = tb_preset.cameras[0]

    for mat in bpy.data.materials:
        tb_mat.switch_mode_mat(mat, self.mode)

    light_obs = [bpy.data.objects.get(light.name)
                 for light in tb_preset.lights]
    table_obs = [bpy.data.objects.get(table.name)
                 for table in tb_preset.tables]

    tb_rp.switch_mode_preset(light_obs, table_obs, tb.mode, tb_cam.cam_view)

    # TODO: switch colourbars


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


def index_scalars_update(self, context):
    """Switch views on updating scalar index."""

    if hasattr(self, 'scalargroups'):  # TODO: isinstance
        try:
            sg = self.scalargroups[self.index_scalargroups]
        except IndexError:
            pass
        else:
            index_scalars_update_func(sg)
    else:
        sg = self
        index_scalars_update_func(sg)


@persistent
def index_scalars_handler_func(dummy):
    """"""

    scn = bpy.context.scene
    tb = scn.tb

    preset = tb.presets[tb.index_presets]
    for anim in preset.animations:
        if anim.animationtype == "TimeSeries":

            sgs = tb_rp.find_ts_scalargroups(anim)
            sg = sgs[anim.anim_timeseries]

            scalar = sg.scalars[sg.index_scalars]
            index_scalars_update_vvolscalar_func(sg, scalar, tb.texmethod)


bpy.app.handlers.frame_change_pre.append(index_scalars_handler_func)


def index_scalars_update_func(group=None):
    """Switch views on updating overlay index."""

    scn = bpy.context.scene
    tb = scn.tb

    tb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    tb_ob = eval(tb_ob_path)
    ob = bpy.data.objects[tb_ob.name]

    if group is None:
        group = tb_utils.active_tb_overlay()[0]

    try:
        scalar = group.scalars[group.index_scalars]
    except IndexError:
        pass
    else:
        name = scalar.name

        if group.path_from_id().startswith("tb.surfaces"):

            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx

            if hasattr(group, 'scalars'):
                vc_idx = ob.data.vertex_colors.find(name)
                ob.data.vertex_colors.active_index = vc_idx

                mat = bpy.data.materials[group.name]
                attr = mat.node_tree.nodes["Attribute"]
                attr.attribute_name = name  # FIXME

                for scalar in group.scalars:
                    scalar_index = group.scalars.find(scalar.name)
                    scalar.is_rendered = scalar_index == group.index_scalars

                # reorder materials: place active group on top
                mats = [mat for mat in ob.data.materials]
                mat_idx = ob.data.materials.find(group.name)
                mat = mats.pop(mat_idx)
                mats.insert(0, mat)
                ob.data.materials.clear()
                for mat in mats:
                    ob.data.materials.append(mat)

        if group.path_from_id().startswith("tb.tracts"):
            if hasattr(group, 'scalars'):
                for i, spline in enumerate(ob.data.splines):
                    splname = name + '_spl' + str(i).zfill(8)
                    spline.material_index = ob.material_slots.find(splname)

        if group.path_from_id().startswith("tb.voxelvolumes"):  # FIXME: used texture slots
            if hasattr(group, 'scalars'):

                index_scalars_update_vvolscalar_func(group, scalar, tb.texmethod)


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
        print(mat, ts, scalar.tex_idx)
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
            v = 1
            for prop in props:
                exec('ts.%s = v' % prop)

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

    if hasattr(self, 'labelgroups'):  # TODO: isinstance
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
    tb = scn.tb

    tb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    tb_ob = eval(tb_ob_path)
    ob = bpy.data.objects[tb_ob.name]

    if group is None:
        group = tb_utils.active_tb_overlay()[0]

    try:
        label = group.labels[group.index_labels]
    except IndexError:
        pass
    else:
        name = label.name

        if "surfaces" in group.path_from_id():
            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx


def material_enum_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    tb_mat.link_innode(mat, self.colourtype)


def colourmap_enum_update(self, context):
    """Assign a new colourmap to the object."""

    tb_ob = tb_utils.active_tb_object()[0]
    if hasattr(tb_ob, 'slicebox'):
        cr = bpy.data.textures[self.name].color_ramp
    else:
        if hasattr(tb_ob, "nstreamlines"):
            ng = bpy.data.node_groups.get("TractOvGroup")
            cr = ng.nodes["ColorRamp"].color_ramp
        elif hasattr(tb_ob, "sphere"):
            nt = bpy.data.materials[self.name].node_tree
            cr = nt.nodes["ColorRamp"].color_ramp

    colourmap = self.colourmap_enum
    tb_mat.switch_colourmap(cr, colourmap)


def cam_view_enum_XX_update(self, context):
    """Set the camview property from enum options."""

    scn = context.scene
    tb = scn.tb
    tb_preset = tb.presets[tb.index_presets]

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
    centre = bpy.data.objects[tb_preset.centre]

#     tb_rp.cam_view_update(cam, centre, self.cam_view, tb_preset.dims)
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
    tb = scn.tb

    self.index_presets = self.presets.find(self.presets_enum)
    preset = self.presets[self.index_presets]
    scn.camera = bpy.data.objects[preset.cameras[0].name]
    # TODO:
    # switch cam view etc


def campaths_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    items = [(cp.name, cp.name, "List the camera paths", i)
             for i, cp in enumerate(tb.campaths)]

    return items


def campaths_enum_update(self, context):
    """Update the camera path."""

    scn = context.scene
    tb = scn.tb
    tb_preset = tb.presets[tb.index_presets]
    cam = bpy.data.objects[tb_preset.cameras[0].name]
    anim = tb_preset.animations[tb_preset.index_animations]

    if anim.animationtype == 'Trajectory':
        # overkill?
        cam_anims = [anim for anim in tb_preset.animations
                     if ((anim.animationtype == "CameraPath") &
                         (anim.is_rendered))]
        tb_rp.clear_camera_path_animations(cam, cam_anims)
        tb_rp.create_camera_path_animations(cam, cam_anims)

    # This adds Follow Path on the bottom of the constraint stack
#     tb_rp.campath_animation(anim, cam)

    scn.frame_set(anim.frame_start)


def tracktype_enum_update(self, context):
    """Update the camera path constraints."""

    scn = context.scene
    tb = scn.tb
    tb_preset = tb.presets[tb.index_presets]
    cam = bpy.data.objects[tb_preset.cameras[0].name]
    centre = bpy.data.objects[tb_preset.centre]
    anim = tb_preset.animations[tb_preset.index_animations]

    cam_anims = [anim for anim in tb_preset.animations
                 if ((anim.animationtype == "CameraPath") &
                     (anim.is_rendered))]

    anim_blocks = [[anim.anim_block[0], anim.anim_block[1]]
                   for anim in cam_anims]

    timeline = tb_rp.generate_timeline(scn, cam_anims, anim_blocks)
    cnsTT = cam.constraints["TrackToCentre"]
    tb_rp.restrict_incluence_timeline(scn, cnsTT, timeline, group="TrackTo")

    cns = cam.constraints["FollowPath" + anim.campaths_enum]  # TODO: if not yet executed/exists
    cns.use_curve_follow = anim.tracktype == "TrackPath"
    if anim.tracktype == 'TrackPath':
        cns.forward_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
    else:
        cns.forward_axis = 'TRACK_NEGATIVE_Y'
        cns.up_axis = 'UP_Z'

    scn.frame_set(anim.frame_start)


def direction_toggle_update(self, context):
    """Update the direction of animation on a curve."""

    scn = context.scene
    tb = scn.tb
    tb_preset = tb.presets[tb.index_presets]
    anim = tb_preset.animations[tb_preset.index_animations]

    try:
        campath = bpy.data.objects[anim.campaths_enum]
    except:
        pass
    else:
        animdata = campath.data.animation_data
        fcu = animdata.action.fcurves.find("eval_time")
        mod = fcu.modifiers[0]  # TODO: sloppy
        intercept, slope, _ = tb_rp.calculate_coefficients(campath, anim)
        mod.coefficients = (intercept, slope)


def tracts_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    items = [(tract.name, tract.name, "List the tracts", i)
             for i, tract in enumerate(tb.tracts)]

    return items


def surfaces_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    items = [(surface.name, surface.name, "List the surfaces", i)
             for i, surface in enumerate(tb.surfaces)]

    return items


def timeseries_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    # FIXME: crash when commenting/uncommenting this
    aliases = {'T': 'tracts', 'S': 'surfaces', 'V': 'voxelvolumes'}
    coll = eval('tb.%s' % aliases[self.timeseries_object[0]])
    sgs = coll[self.timeseries_object[3:]].scalargroups
#     sgs = tb_rp.find_ts_scalargroups(self)

    items = [(scalargroup.name, scalargroup.name, "List the timeseries", i)
             for i, scalargroup in enumerate(sgs)]

    return items


def voxelvolumes_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    items = [(vvol.name, vvol.name, "List the voxelvolumes", i)
             for i, vvol in enumerate(tb.voxelvolumes)]

    return items


def curves_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    campaths = [cp.name for cp in tb.campaths]
    tracts = [tract.name for tract in tb.tracts]
    items = [(cu.name, cu.name, "List the curves", i)
             for i, cu in enumerate(bpy.data.curves)
             if ((cu.name not in campaths) and
                 (cu.name not in tracts))]

    return items


def timeseries_object_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    tb = scn.tb

    tb_obs = ["%s: %s" % (l, ob.name)
              for l, coll in zip(['T', 'S', 'V'], [tb.tracts, tb.surfaces, tb.voxelvolumes])
              for ob in coll if len(ob.scalargroups)]
    items = [(obname, obname, "List the objects", i)
             for i, obname in enumerate(tb_obs)]

    return items


def texture_directory_update(self, context):
    """Update the texture."""

    if "surfaces" in self.path_from_id():
        tb_mat.load_surface_textures(self.name, self.texdir, len(self.scalars))
    elif "voxelvolumes" in self.path_from_id():
        pass  # TODO


def update_viewport():
    """Trigger viewport updates"""

    for area in bpy.context.screen.areas:
        if area.type in ['IMAGE_EDITOR', 'VIEW_3D', 'PROPERTIES']:
            area.tag_redraw()


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
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")
    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=[("greyscale", "greyscale", "greyscale", 1),
               ("jet", "jet", "jet", 2),
               ("hsv", "hsv", "hsv", 3),
               ("hot", "hot", "hot", 4),
               ("cool", "cool", "cool", 5),
               ("spring", "spring", "spring", 6),
               ("summer", "summer", "summer", 7),
               ("autumn", "autumn", "autumn", 8),
               ("winter", "winter", "winter", 9),
               ("parula", "parula", "parula", 10)],
        default="jet",
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


class LabelProperties(PropertyGroup):
    """Properties of label overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay")
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
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")
    group = StringProperty(
        name="Group",
        description="The group the border overlay belongs to")
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
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the border is rendered",
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")
    group = StringProperty(
        name="Group",
        description="The group the border overlay belongs to")
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
        max=1)


class ScalarGroupProperties(PropertyGroup):
    """Properties of time series overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the time series overlay")
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
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")

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
        items=[("greyscale", "greyscale", "greyscale", 1),
               ("jet", "jet", "jet", 2),
               ("hsv", "hsv", "hsv", 3),
               ("hot", "hot", "hot", 4),
               ("cool", "cool", "cool", 5),
               ("spring", "spring", "spring", 6),
               ("summer", "summer", "summer", 7),
               ("autumn", "autumn", "autumn", 8),
               ("winter", "winter", "winter", 9),
               ("parula", "parula", "parula", 10)],
        default="jet",
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

    rendertype = EnumProperty(
        name="rendertype",
        description="Surface or volume rendering of texture",
        items=[("SURFACE", "Surface",
                "Switch to surface rendering", 0),
               ("VOLUME", "Volume",
                "Switch to volume rendering", 2)],
        update=rendertype_enum_update,
        default="VOLUME")

    slicebox = StringProperty(
        name="Slicebox",
        description="Name of slicebox",
        default="box")
    slicethickness = FloatVectorProperty(
        name="Slice thickness",
        description="The thickness of the slices",
        default=(1.0, 1.0, 1.0),
        size=3,
        precision=2,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=2,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",  
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=2,
        min=-1.57,
        max=1.57,
        subtype="TRANSLATION",
        update=slices_update)
    is_yoked = BoolProperty(
        name="Is Yoked",
        description="Indicates if the overlay is yoked to parent",
        default=False,
        update=is_yoked_bool_update)
    dimensions = FloatVectorProperty(
        name="dimensions",
        description="",
        default=[0.0, 0.0, 0.0, 0.0],
        size=4,
        subtype="TRANSLATION")

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

    mat_is_yoked = BoolProperty(
        name="Material Is Yoked",
        description="Indicates if the overlay time point materials are yoked",
        default=True,
        update=mat_is_yoked_bool_update)


class LabelGroupProperties(PropertyGroup):
    """Properties of label groups."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay")
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
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")

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

    rendertype = EnumProperty(
        name="rendertype",
        description="Surface or volume rendering of texture",
        items=[("SURFACE", "Surface",
                "Switch to surface rendering", 0),
               ("VOLUME", "Volume",
                "Switch to volume rendering", 2)],
        update=rendertype_enum_update,
        default="VOLUME")

    slicebox = StringProperty(
        name="Slicebox",
        description="Name of slicebox",
        default="box")
    slicethickness = FloatVectorProperty(
        name="Slice thickness",
        description="The thickness of the slices",
        default=(1.0, 1.0, 1.0),
        size=3,
        precision=2,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=2,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",  
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=2,
        min=-1.57,
        max=1.57,
        subtype="TRANSLATION",
        update=slices_update)
    is_yoked = BoolProperty(
        name="Is Yoked",
        description="Indicates if the overlay is yoked to parent",
        default=False,
        update=is_yoked_bool_update)
    dimensions = FloatVectorProperty(
        name="dimensions",
        description="",
        default=[0.0, 0.0, 0.0, 0.0],
        size=4,
        subtype="TRANSLATION")

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


class BorderGroupProperties(PropertyGroup):
    """Properties of border groups."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay")
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
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")

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


class TractProperties(PropertyGroup):
    """Properties of tracts."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the tract (default: filename)",
        default="")
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

    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded scalargroups")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
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
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
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
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.0)

    sphere = EnumProperty(
        name="Unwrapping sphere",
        description="Select sphere for unwrapping",
        items=surfaces_enum_callback)


class VoxelvolumeProperties(PropertyGroup):
    """Properties of voxelvolumes."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the voxelvolume (default: filename)",
        default="")
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
    dimensions = FloatVectorProperty(
        name="dimensions",
        description="",
        default=[0.0, 0.0, 0.0, 0.0],
        size=4,
        subtype="TRANSLATION")

    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded scalargroups")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
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
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")

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
        items=[("greyscale", "greyscale", "greyscale", 1),
               ("jet", "jet", "jet", 2),
               ("hsv", "hsv", "hsv", 3),
               ("hot", "hot", "hot", 4),
               ("cool", "cool", "cool", 5),
               ("spring", "spring", "spring", 6),
               ("summer", "summer", "summer", 7),
               ("autumn", "autumn", "autumn", 8),
               ("winter", "winter", "winter", 9),
               ("parula", "parula", "parula", 10)],
        default="greyscale",
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

    slicebox = StringProperty(
        name="Slicebox",
        description="Name of slicebox",
        default="box")
    slicethickness = FloatVectorProperty(
        name="Slice thickness",
        description="The thickness of the slices",
        default=(1.0, 1.0, 1.0),
        size=3,
        precision=2,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=2,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",  
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=2,
        min=-1.57,
        max=1.57,
        subtype="TRANSLATION",
        update=slices_update)

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
        description="The name of the scalar overlay")
    texname = StringProperty(
        name="Texture name",
        description="The name of the scalar overlay")


class CameraProperties(PropertyGroup):
    """Properties of cameras."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera",
        default="")
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


class LightsProperties(PropertyGroup):
    """Properties of light."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the lights",
        default="")
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
        default=True)

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


class TableProperties(PropertyGroup):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the table",
        default="")
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
        default=True)
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
        subtype="COLOR")

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


class AnimationProperties(PropertyGroup):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="")
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
        default="")
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


class PresetProperties(PropertyGroup):
    """Properties of a preset."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="")
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
        type=AnimationProperties,
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
    verbose = BoolProperty(
        name="Verbose",
        description="Verbose reporting",
        default=False)

    mode = EnumProperty(
        name="mode",
        description="switch between tractblender modes",
        items=[("artistic", "artistic", "artistic", 1),
               ("scientific", "scientific", "scientific", 2)],
        default="artistic",
        update=mode_enum_update)

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
        default=False,
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
    show_newpath = BoolProperty(
        name="New trajectory",
        default=False,
        description="Show/hide the camera trajectory generator")
    show_points = BoolProperty(
        name="Points",
        default=False,
        description="Show/hide the camera path points")

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
        min=0)
    presets_enum = EnumProperty(
        name="presets",
        description="switch between presets",
        items=presets_enum_callback,
        update=presets_enum_update)

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

    uv_resolution = IntProperty(
        name="utexture resolution",
        description="the resolution of baked textures",
        default=4096,
        min=1)
    uv_bakeall = BoolProperty(
        name="Bake all",
        description="Bake single or all scalars in a group",
        default=True)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])

    projectdir = StringProperty(
        name="Project directory",
        description="The path to the NeuroBlender project",
        subtype="DIR_PATH",
        default=os.path.expanduser('~'))

    texmethod = IntProperty(
        name="texmethod",
        description="",
        default=1,
        min=1, max=4)


# @persistent
# def projectdir_update(dummy):
#     """"""
# 
#     scn = bpy.context.scene
#     tb = scn.tb
# 
# #     tb.projectdir = os.path.
# 
# bpy.app.handlers.load_post(projectdir_update)

# =========================================================================== #


def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.tb = PointerProperty(type=TractBlenderProperties)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.Scene.tb

if __name__ == "__main__":
    register()
