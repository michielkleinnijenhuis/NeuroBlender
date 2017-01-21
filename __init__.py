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
                       IntVectorProperty,
                       PointerProperty)

from os import listdir
from os.path import dirname, join
from shutil import copy
import numpy as np
import mathutils

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
    "blender": (2, 78, 0),
    "location": "Properties -> Scene -> NeuroBlender",
    "description": """"
        This add-on focusses on visualising MRI data.
        """,
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}


# =========================================================================== #


class Reload(Operator):
    bl_idname = "tb.reload"
    bl_label = "Reload"
    bl_description = "Reload"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        # FIXME: Blender crashes on reload
        tb_path = "/Users/michielk/workspace/TractBlender/TractBlender.zip"
        bpy.ops.wm.addon_install(filepath=tb_path)
        bpy.ops.wm.addon_enable(module="TractBlender")

        return {"FINISHED"}


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
            else:
                pass
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
            col.operator("tb.import_" + type,
                         icon='ZOOMIN',
                         text="")
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
            tex = bpy.data.textures[tb_ob.name]
            self.drawunit_texture(layout, tex, tb_ob)
        else:
            self.drawunit_material(layout, tb_ob)

    def drawunit_tri_slices(self, layout, tb, tb_ob):

        self.drawunit_slices(layout, tb_ob)

    def drawunit_tri_info(self, layout, tb, tb_ob):

        row = layout.row()
        row.enabled = False
        row.prop(tb_ob, "filepath",
                 text="Path", emboss=False)

        if tb.objecttype == "tracts":
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
            pass

        elif tb.objecttype == 'voxelvolumes':
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "range",
                     text="Datarange", emboss=False)

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
        lgp = bpy.types.LabelProperties
        bgp = bpy.types.BorderProperties
        if isinstance(tb_ob, (lgp, bgp)):
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
        row.prop(tex, "intensity")
        row.prop(tex, "contrast")
        row.prop(tex, "saturation")

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

    def drawunit_slices(self, layout, tb_ob):
#         row = layout.row()
#         ob = bpy.data.objects[tb_ob.name+"SliceBox"]
#         row.prop(ob, "scale", expand=True)
#         row = layout.row()
#         row.prop(ob, "location", expand=True)
        row = layout.row()
        col = row.column()
        col.prop(tb_ob, "slicethickness", expand=True, text="Thickness")
        col = row.column()
        col.prop(tb_ob, "sliceposition", expand=True, text="Position")
        col = row.column()
        col.prop(tb_ob, "sliceangle", expand=True, text="Angle")


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
                if ovtype == "scalars":
                    self.drawunit_tri(layout, "overlay_material", tb, tb_ov)

                elif ovtype == "scalargroups":
                    row = layout.row()

                    col = row.column()
                    col.operator("tb.wp_preview", text="", icon="GROUP_VERTEX")
                    col.enabled = bpy.context.mode != 'PAINT_WEIGHT'

                    col = row.column()
                    col.operator("tb.vp_preview", text="", icon="GROUP_VCOL")
                    ob = bpy.data.objects[tb_ob.name]
                    tpname = tb_ov.scalars[tb_ov.index_scalars].name
                    col.enabled = ob.data.vertex_colors.find(tpname) == -1

                    col = row.column()
                    col.template_list("ObjectListTS", "",
                                      tb_ov, "scalars",
                                      tb_ov, "index_scalars",
                                      rows=2, type="COMPACT")

                    self.drawunit_tri(layout, "overlay_material", tb, tb_ov)

                else:
                    self.drawunit_tri(layout, "items", tb, tb_ov)

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
            tex = bpy.data.textures[tb_ov.name]
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

    def drawunit_tri_overlay_info(self, layout, tb, tb_ov):

        row = layout.row()
        row.enabled = False
        row.prop(tb_ov, "filepath")

        if tb.overlaytype == "scalars":
            row = layout.row()
            row.enabled = False
            row.prop(tb_ov, "range")


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
               ('UP_AN', "UpAN", ""),
               ('DOWN_AN', "DownAN", ""),
               ('REMOVE_AN', "RemoveAN", "")))

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        tb_ob, ob_idx = tb_utils.active_tb_object()

        collection = eval("%s.%s" % ("tb", tb.objecttype))
        tb_utils.validate_tb_objects([collection])

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
        elif self.action.endswith('_PL'):
            data = "tb.presets[%d]" % tb.index_presets
            type = "lights"
        elif self.action.endswith('_AN'):
            data = "tb.presets[%d]" % tb.index_presets
            type = "animations"

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

        if type == "voxelvolumes":
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
                slicebox = bpy.data.objects[name+"SliceBox"]
                bpy.data.objects.remove(slicebox, do_unlink=True)
#             for ms in ob.material_slots:
#                 self.remove_material(ob, ms.name)  # FIXME: causes crash
            bpy.data.objects.remove(ob, do_unlink=True)
        elif self.action.endswith('_PL'):
            print("remove PL")  # FIXME: TODO
        elif self.action.endswith('_AN'):
            print("remove AN")  # FIXME: TODO
            # for CamPath anim:
            # remove follow path constraint on camera
            # remove keyframes on TrackTo constraint influence
        else:
            if tb_ob.is_valid:
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
        for labelgroup in tb_ob.labelgroups:
            pass  # TODO

    def remove_surfaces_overlays(self, tb_ob, ob):
        """Remove surface scalars, labels and borders."""

        for scalar in tb_ob.scalars:
            self.remove_surfaces_scalars(scalar, ob)
        for labelgroup in tb_ob.labelgroups:
            self.remove_surfaces_labelgroups(labelgroup, ob)
        for bordergroup in tb_ob.bordergroups:
            self.remove_surfaces_bordergroups(bordergroup, ob)

    def remove_voxelvolumes_overlays(self, tb_ob, ob):
        """Remove voxelvolume scalars and labels."""

        for scalar in tb_ob.scalars:
            self.remove_voxelvolumes_scalars(scalar, ob)
        for labelgroup in tb_ob.labelgroups:
            self.remove_voxelvolumes_labelgroups(labelgroup, ob)

    def remove_tracts_scalars(self, scalar, ob):
        """Remove scalar overlay from tract."""

        for i, spline in enumerate(ob.data.splines):
            splname = scalar.name + '_spl' + str(i).zfill(8)
            self.remove_material(ob, splname)
            self.remove_image(ob, splname)

    def remove_tracts_labelgroups(self, label, ob):
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
        """Remove label from a labelgroup."""

        self.remove_vertexcoll(ob.vertex_groups, tb_ov.name)
        self.remove_material(ob, tb_ov.name)

    def remove_surfaces_bordergroups(self, tb_ov, ob):
        """Remove a bordergroup overlay from a surface."""

        for border in tb_ov.borders:
            self.remove_surfaces_borders(border, ob)
        bordergroup_ob = bpy.data.objects.get(tb_ov.name)
        bpy.data.objects.remove(bordergroup_ob, do_unlink=True)

    def remove_surfaces_borders(self, tb_ov, ob):
        """Remove border from a bordergroup."""

        border_ob = bpy.data.objects[tb_ov.name]
        bpy.data.objects.remove(border_ob, do_unlink=True)
        self.remove_material(ob, tb_ov.name)

    def remove_voxelvolumes_scalars(self, tb_ov, ob):
        """Remove scalar overlay from a voxelvolume."""

        self.remove_material(ob, tb_ov.name)
        ob = bpy.data.objects[tb_ov.name]
        bpy.data.objects.remove(ob, do_unlink=True)

    def remove_voxelvolumes_labelgroups(self, tb_ov, ob):
        """Remove labelgroup overlay from a voxelvolume."""

        self.remove_material(ob, tb_ov.name)
        ob = bpy.data.objects[tb_ov.name]
        bpy.data.objects.remove(ob, do_unlink=True)

    def remove_voxelvolumes_labels(self, tb_ov, ob):
        """Remove label from a labelgroup."""

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
            filenames = listdir(self.directory)

        for f in filenames:
            fpath = join(self.directory, f)

            ca = [bpy.data.objects,
                  bpy.data.materials]
            name = tb_utils.check_name(self.name, fpath, ca)

            ob, info_imp, info_geom = importfun(fpath, name, "", impdict)
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

    parent = StringProperty(
        name="Parent",
        description="The parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parent, "scalars")

        return {"FINISHED"}

    def invoke(self, context, event):
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

    parent = StringProperty(
        name="Parent",
        description="The parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parent, "scalargroups")

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

    parent = StringProperty(
        name="Parent",
        description="The parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parent, "labelgroups")

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

    parent = StringProperty(
        name="Parent",
        description="The parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        tb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parent, "bordergroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class AddPreset(Operator):
    bl_idname = "tb.add_preset"
    bl_label = "New preset"
    bl_description = "Create a new preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="Preset")

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        ca = [tb.presets]
        name = tb_utils.check_name(self.name, "", ca)
        tb_rp.scene_preset_init(name)
        tb.presets_enum = name

        return {"FINISHED"}


class DelPreset(Operator):
    bl_idname = "tb.del_preset"
    bl_label = "Delete preset"
    bl_description = "Delete a preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        tb.presets.remove(tb.index_presets)
        tb.index_presets -= 1

        try:
            name = tb.presets[tb.index_presets].name
        except IndexError:
            pass
        else:
            tb.presets_enum = name

        return {"FINISHED"}


class AddLight(Operator):
    bl_idname = "tb.import_lights"
    bl_label = "New light"
    bl_description = "Create a new light"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the light",
        default="Light")

    def execute(self, context):

        scn = bpy.context.scene
        tb = scn.tb
        tb_preset = tb.presets[tb.index_presets]
        preset = bpy.data.objects[tb_preset.name]
        centre = bpy.data.objects[tb_preset.centre]
        box = bpy.data.objects[tb_preset.box]
        lights = bpy.data.objects[tb_preset.lightsempty]

        tb_light = tb_imp.add_light_to_collection(self.name)
        tb_rp.create_light(tb_light, preset, centre, box, lights)

        return {"FINISHED"}


class AddAnimation(Operator):
    bl_idname = "tb.import_animations"
    bl_label = "New animation"
    bl_description = "Create a new animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="Anim")

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        ca = [preset.animations for preset in tb.presets]
        name = tb_utils.check_name(self.name, "", ca, forcefill=True)
        tb_imp.add_animation_to_collection(name)

        return {"FINISHED"}


class AddCamPath(Operator):
    bl_idname = "tb.add_campath"
    bl_label = "New camera path"
    bl_description = "Create a new path for the camera"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        preset = tb.presets[tb.index_presets]
        anim = preset.animations[preset.index_animations]
        cam = bpy.data.objects[preset.cameras[0].name]
        centre = bpy.data.objects[preset.centre]
        box = bpy.data.objects[preset.name + "Box"]

        ca = [tb.campaths]
        if anim.pathtype == "Circular":
            name = "CP_%s" % (anim.axis)
            name = tb_utils.check_name(name, "", ca)
            campath = tb_rp.create_camera_path_rotation(name, preset, cam, centre, box, anim.axis)
        elif anim.pathtype == "Streamline":
            name = "CP_%s_%05d" % (anim.anim_tract, anim.spline_index)
            name = tb_utils.check_name(name, "", ca)
            campath = tb_rp.create_camera_path_streamline(name, preset,
                                                          anim.anim_tract,
                                                          anim.spline_index)
        # TODO: choose between hiding objects' streamline tube from render
        # or use camera clipping
        elif anim.pathtype == "Select":
            name = "CP_%s" % (anim.anim_curve)
            name = tb_utils.check_name(name, "", ca)
            cu = bpy.data.objects[anim.anim_curve].data.copy()
            campath = bpy.data.objects.new(name, cu)
            scn.objects.link(campath)
            scn.update()

        campath.hide_render = True
        campath.parent = bpy.data.objects[preset.name]

        tb_imp.add_campath_to_collection(name)

        anim.campaths_enum = campath.name

        return {"FINISHED"}


class DelCamPath(Operator):
    bl_idname = "tb.del_campath"
    bl_label = "Delete camera path"
    bl_description = "Delete a camera path"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = context.scene
        tb = scn.tb

        preset = tb.presets[tb.index_presets]
        anim = preset.animations[preset.index_animations]
        campath = bpy.data.objects[anim.campaths_enum]
        scn.objects.unlink(campath)
        # NOTE: this doesn't remove it from the list of objects

        tb.campaths.remove(tb.campaths.find(anim.campaths_enum))
#         tb.index_campaths -= 1

        return {"FINISHED"}


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


class WeightPaintMode(Operator):
    bl_idname = "tb.wp_preview"
    bl_label = "wp_mode button"
    bl_description = "Go to weight paint mode for preview"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")

        return {"FINISHED"}


class VertexPaintMode(Operator):
    bl_idname = "tb.vp_preview"
    bl_label = "vp_mode button"
    bl_description = "Bake timepoint and go to vertex paint mode for preview"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        tb_ob = tb_utils.active_tb_object()[0]
        scalargroup = tb_utils.active_tb_overlay()[0]
        ob = bpy.data.objects[tb_ob.name]
        scalar = scalargroup.scalars[scalargroup.index_scalars]
        vg = ob.vertex_groups[scalar.name]

        vcs = ob.data.vertex_colors
        vc = vcs.new(name=scalar.name)
        ob.data.vertex_colors.active = vc
        ob = tb_mat.assign_vc(ob, vc, [vg])

        bpy.ops.object.mode_set(mode="VERTEX_PAINT")

        return {"FINISHED"}


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
               ('SELECT_AN', "Select_AN", ""),
               ('DESELECT_AN', "Deselect_AN", ""),
               ('INVERT_AN', "Invert_AN", "")))

    def execute(self, context):

        scn = bpy.context.scene
        tb = scn.tb

        if self.action.endswith("_L1"):
            items = eval("tb.%s" % tb.objecttype)
        elif self.action.endswith("_L2"):
            tb_ob = tb_utils.active_tb_object()[0]
            items = eval("tb_ob.%s" % tb.overlaytype)
        elif self.action.endswith("_L3"):
            tb_ov = tb_utils.active_tb_overlay()[0]
            type = tb.overlaytype.replace("groups", "s")
            items = eval("tb_ov.%s" % type)
        elif self.action.endswith("_PL"):
            preset = tb.presets[tb.index_presets]
            items = eval("preset.lights")
        elif self.action.endswith("_AN"):
            preset = tb.presets[tb.index_presets]
            items = eval("preset.animations")

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

        name = tb.presets[tb.index_presets].centre
        centre = bpy.data.objects[name]
        centre.location = centre_location

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

        name = tb.presets[tb.index_presets].centre
        centre = bpy.data.objects[name]
        centre.scale = 0.5 * mathutils.Vector(dims)

        tb.presets[tb.index_presets].dims = dims

        return {"FINISHED"}


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
            self.drawunit_tri(layout, "animations", tb, preset)

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

        lights = bpy.data.objects[preset.name+"Lights"]
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

    def drawunit_tri_animations(self, layout, tb, preset):

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

                col = row.column()
                col.split(percentage=0.7, align=False)
                row1 = col.row()
                row1.label("Camera path:")

                row1 = col.row()
                col1 = row1.column()
                col1.prop(anim, "reverse", toggle=True, icon="ARROW_LEFTRIGHT", icon_only=True)
                col1 = row1.column()
                col1.prop(anim, "campaths_enum", expand=False, text="")
                col1 = row1.column()
                col1.operator("tb.del_campath", icon='ZOOMOUT', text="")
                col1.enabled = True
                row1 = col.row()
                box = row1.box()
                self.drawunit_tri(box, "newpath", tb, anim)

                col = row.column()
                col.separator()

                col = row.column()
                row1 = col.row()
                row1.label("Camera tracking:")
                row1 = col.row()
                col1 = row1.column()
                col1.prop(anim, "tracktype", expand=True)
                if anim.tracktype == "TrackPath":
                    tb_cam = preset.cameras[0]
                    cam = bpy.data.objects[tb_cam.name]
                    row1 = col.row()
                    row1.prop(cam, "rotation_euler", index=2, text="tumble")

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
                pass

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

        row = layout.row()
        row.separator()

        row = layout.row()
        row.operator("tb.add_campath", text="Add trajectory")


class ScenePreset(Operator):
    bl_idname = "tb.scene_preset"
    bl_label = "Load scene preset"
    bl_description = "Setup up camera and lighting for this brain"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        tb_rp.scene_preset()

        return {"FINISHED"}


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

        addon_dir = dirname(__file__)
        tb_dir = dirname(addon_dir)
        scripts_dir = dirname(dirname(dirname(bpy.__file__)))
        startup_dir = join(scripts_dir, 'startup')
        basename = 'external_sitepackages'
        with open(join(startup_dir, basename + '.txt'), 'w') as f:
            f.write(scn.tb.nibabel_path)
        copy(join(addon_dir, basename + '.py'), startup_dir)

        return {"FINISHED"}


class SwitchToMainScene(Operator):
    bl_idname = "tb.switch_to_main"
    bl_label = "Switch to main"
    bl_description = "Switch to main TractBlender scene to import"
    bl_options = {"REGISTER"}

    def execute(self, context):

        context.window.screen.scene = bpy.data.scenes["Scene"]

        return {"FINISHED"}


def nibabel_path_update(self, context):
    """Check whether nibabel can be imported."""

    tb_utils.validate_nibabel("")


def sformfile_update(self, context):
    """Set the sform transformation matrix for the object."""

    ob = bpy.data.objects[self.name]
    affine = tb_imp.read_affine_matrix(self.sformfile)
    ob.matrix_world = affine


def slices_update(self, context):
    """Set slicethicknesses and positions for the object."""

    ob = bpy.data.objects[self.name+"SliceBox"]
    ob.scale = self.slicethickness


def mode_enum_update(self, context):
    """Perform actions for updating mode."""

    tb_preset = tb.presets[self.index_presets]
    tb_cam = tb_preset.cameras[0]

    for mat in bpy.data.materials:
        tb_mat.switch_mode_mat(mat, self.mode)

    lights = [tb_preset.name + "LightsBack",
              tb_preset.name + "LightsFill",
              tb_preset.name + "LightsKey"]
    tables = [tb.presetname + "Table"]
    light_obs = [bpy.data.objects.get(light) for light in lights]
    light_obs = [light for light in light_obs if light is not None]
    table_obs = [bpy.data.objects.get(table) for table in tables]
    table_obs = [table for table in table_obs if table is not None]
    tb_rp.switch_mode_preset(light_obs, table_obs, tb.mode, tb_cam.cam_view)

    # TODO: switch colourbars


def overlay_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = []
    items.append(("scalars", "scalars",
                  "List the scalar overlays", 1))
    if self.objecttype == 'surfaces':
        items.append(("scalargroups", "time series",
                      "List the time series", 2))
    if self.objecttype != 'tracts':
        items.append(("labelgroups", "labelgroups",
                      "List the label overlays", 3))
    if self.objecttype == 'surfaces':
        items.append(("bordergroups", "bordergroups",
                      "List the bordergroups", 4))

    return items


def index_scalars_update(self, context):
    """Assign a new preset material to the object."""

    tb_object = tb_utils.active_tb_object()[0]
    ob = bpy.data.objects[tb_object.name]

    tpname = self.scalars[self.index_scalars].name
    vg_idx = ob.vertex_groups.find(tpname)
    ob.vertex_groups.active_index = vg_idx

    mat = bpy.data.materials[self.name]
    attr = mat.node_tree.nodes["Attribute"]
    attr.attribute_name = tpname

    for scalar in self.scalars:
        scalar_index = self.scalars.find(scalar.name)
        scalar.is_rendered = scalar_index == self.index_scalars


def material_enum_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    tb_mat.link_innode(mat, self.colourtype)


def colourmap_enum_update(self, context):
    """Assign a new colourmap to the object."""

    tb_ob = tb_utils.active_tb_object()[0]

    if isinstance(self, bpy.types.VoxelvolumeProperties):
        cr = bpy.data.textures[self.name].color_ramp
    elif isinstance(self, (bpy.types.ScalarProperties,
                           bpy.types.ScalarGroupProperties)):
        if isinstance(tb_ob, bpy.types.TractProperties):
            ng = bpy.data.node_groups.get("TractOvGroup")
            cr = ng.nodes["ColorRamp"].color_ramp
        elif isinstance(tb_ob, bpy.types.SurfaceProperties):
            nt = bpy.data.materials[self.name].node_tree
            cr = nt.nodes["ColorRamp"].color_ramp

    colourmap = self.colourmap_enum
    tb_mat.switch_colourmap(cr, colourmap)


def cam_view_enum_update(self, context):
    """Set the camview property from enum options."""

    scn = context.scene
    tb = scn.tb
    tb_preset = tb.presets[tb.index_presets]

    if self.cam_view_enum == "Numeric":
        return

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
    self.cam_view = list(cv_unit * self.cam_distance)

    cam = bpy.data.objects[self.name]
    centre = bpy.data.objects[tb_preset.name+"Centre"]

#     tb_rp.cam_view_update(cam, centre, self.cam_view, tb_preset.dims)
    cam.location = self.cam_view

    scn.frame_set(0)


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
    centre = bpy.data.objects[tb_preset.name+"Centre"]

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

    self.index_presets = self.presets.find(self.presets_enum)


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
             for i, tract in enumerate(tb.surfaces)]

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


class ScalarGroupProperties(PropertyGroup):
    """Properties of time series overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the time series overlay")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the time series overlay")
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

    ntimepoints = IntProperty(
        name="Ntimepoints",
        description="Number of timepoints in the timeseries",
        min=1)


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
        description="The filepath to the surface")
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
    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded timeseries")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
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
        default=[0.0, 0.0, 0.0],
        size=3,
        subtype="TRANSLATION")

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
               ("Right", "Right", "Right")],
        # ("Numeric", "Numeric", "Numeric")
        update=cam_view_enum_update)

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

    # TODO: size, material, shape, ...

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
                "Curvilinear trajectory from curve", 2)],
        default="Circular")

    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
#                ("-X", "-X", "-X", 3),
#                ("-Y", "-Y", "-Y", 4),
#                ("-Z", "-Z", "-Z", 5),
        default="Z")
    reverse = BoolProperty(
        name="Reverse",
        description="Toggle direction of trajectory traversal",
        default=False,
        update=direction_toggle_update)

    anim_tract = EnumProperty(
        name="Animation streamline",
        description="Select tract to animate",
        items=tracts_enum_callback)
    spline_index = IntProperty(
        name="streamline index",
        description="index of the streamline to animate",
        min=0,
        default=0)

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

    anim_curve = EnumProperty(
        name="Animation curves",
        description="Select curve to animate",
        items=curves_enum_callback)

    # TODO: TimeSeries props


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


# =========================================================================== #


def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.tb = PointerProperty(type=TractBlenderProperties)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.Scene.tb

if __name__ == "__main__":
    register()
