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

            self.draw_tb_ob(self.layout, tb)

        else:
            row = self.layout.row()
            row.label(text="Please use the main scene for TractBlender.")
            row = self.layout.row()
            row.operator("tb.switch_to_main",
                         text="Switch to main",
                         icon="FORWARD")

    def draw_tb_ob(self, layout, tb):

        obtype = tb.objecttype

        row = layout.row()
        row.separator()
        row = layout.row()
        row.prop(tb, "objecttype", expand=True)
        row = layout.row()
        row.template_list("ObjectListOb", "",
                          tb, obtype,
                          tb, "index_" + obtype,
                          rows=2)
        col = row.column(align=True)
        col.operator("tb.import_" + obtype,
                     icon='ZOOMIN',
                     text="")
        col.operator("tb.oblist_ops",
                     icon='ZOOMOUT',
                     text="").action = 'REMOVE_ob'
        col.menu("tb.mass_is_rendered_objects",
                 icon='DOWNARROW_HLT',
                 text="")
        col.separator()
        col.operator("tb.oblist_ops",
                     icon='TRIA_UP',
                     text="").action = 'UP_ob'
        col.operator("tb.oblist_ops",
                     icon='TRIA_DOWN',
                     text="").action = 'DOWN_ob'

        obtype = tb.objecttype
        try:
            idx = eval("tb.index_%s" % obtype)
            tb_ob = eval("tb.%s[%d]" % (obtype, idx))
        except IndexError:
            pass
        else:
            row = layout.row()
            if tb.show_transform_options:
                row.prop(tb, "show_transform_options",
                         icon='TRIA_DOWN',
                         emboss=False)
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
            else:
                row.prop(tb, "show_transform_options",
                         icon='TRIA_RIGHT',
                         emboss=False)


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

            obtype = tb.objecttype
            try:
                idx = eval("tb.index_%s" % obtype)
                tb_ob = eval("tb.%s[%d]" % (obtype, idx))
            except IndexError:
                row = self.layout.row()
                row.label(text="No geometry loaded ...")
            else:
                row = self.layout.row()
                row.label(text="Properties of %s:" % tb_ob.name,
                          icon=tb_ob.icon)
                self.draw_appearance(self.layout, tb, tb_ob)
                self.draw_tb_ov(self.layout, tb, tb_ob)
#                 self.draw_additional(self.layout, tb, tb_ob)

        else:
            row = self.layout.row()
            row.label(text="Please use the main scene for TractBlender.")
            row = self.layout.row()
            row.operator("tb.switch_to_main",
                         text="Switch to main",
                         icon="FORWARD")

    def draw_appearance(self, layout, tb, tb_ob):

        row = layout.row()
        if tb.show_appearance_options:
            row.prop(tb, "show_appearance_options",
                     icon='TRIA_DOWN',
                     emboss=False)
            if tb.objecttype != "voxelvolumes":

                row = layout.row()
                col1 = row.column()
                row1 = col1.row()
                row1.prop(tb_ob, "transparency")
                row1 = col1.row()
                row1.prop(tb_ob, "colourpicker")
                col2 = row.column()
                col2.prop(tb_ob, "colourtype", expand=True)
        else:
            row.prop(tb, "show_appearance_options",
                     icon='TRIA_RIGHT',
                     emboss=False)

    def draw_tb_ov(self, layout, tb, tb_ob):

        ovtype = tb.overlaytype

        row = layout.row()
        if tb.show_overlay_options:
            row.prop(tb, "show_overlay_options",
                     icon='TRIA_DOWN',
                     emboss=False)
            row = layout.row()
            row.prop(tb, "overlaytype", expand=True)
            row = layout.row()
            row.template_list("ObjectListOv", "",
                              tb_ob, ovtype,
                              tb_ob, "index_" + ovtype,
                              rows=2)
            col = row.column(align=True)
            col.operator("tb.import_" + ovtype,
                         icon='ZOOMIN',
                         text="")
            col.operator("tb.oblist_ops",
                         icon='ZOOMOUT',
                         text="").action = 'REMOVE_ov'
            col.menu("tb.mass_is_rendered_overlays",
                     icon='DOWNARROW_HLT',
                     text="")
            col.separator()
            col.operator("tb.oblist_ops",
                         icon='TRIA_UP',
                         text="").action = 'UP_ov'
            col.operator("tb.oblist_ops",
                         icon='TRIA_DOWN',
                         text="").action = 'DOWN_ov'
            try:
                ov_idx = eval("tb_ob.index_%s" % ovtype)
                tb_ov = eval("tb_ob.%s[%d]" % (ovtype, ov_idx))
            except IndexError:
                pass
            else:
                if ovtype == "scalars":
                    row = layout.row()
                    row.enabled = False
                    row.prop(tb_ov, "range")
                    row = layout.row()
                    row.prop(tb_ov, "showcolourbar")

                    box = layout.box()
                    row = box.row()
                    row.label(text="Convenience access to colorramp:")
                    row = box.row()
                    if tb.objecttype == "tracts":
                        ng = bpy.data.node_groups.get("TractOvGroup")
                        ramp = ng.nodes["ColorRamp"]
                    else:
                        mat = bpy.data.materials[tb_ov.name]
                        ramp = mat.node_tree.nodes["ColorRamp"]
                        # FIXME: this fails on voxelvolumes
                    box.template_color_ramp(ramp, "color_ramp", expand=True)
                    row = box.row()
                    row.label(text="non-normalized colour stop positions:")
                    self.calc_nn_elpos(tb_ov, ramp)
                    row = box.row()
                    row.enabled = False
                    row.template_list("ObjectListCR", "",
                                      tb_ov, "nn_elements",
                                      tb_ov, "index_nn_elements",
                                      rows=3)

                elif ovtype == "labels":
                    row = layout.row()
                    row.enabled = False
                    row.prop(tb_ov, "value")
                    row = layout.row()
                    col = row.column()
                    col.enabled = False
                    col.label(text="original: ")
                    col = row.column()
                    col.enabled = False
                    col.prop(tb_ov, "colour", text="")
                    col = row.column()
                    col.operator("tb.revert_" + "label",
                                 icon='BACK', text="")

                    box = layout.box()
                    row = box.row()
                    row.label(text="Convenience access to material:")
                    row = box.row()
                    mat = bpy.data.materials[tb_ov.name]
                    colour = mat.node_tree.nodes["Diffuse BSDF"].inputs[0]
                    row.prop(colour, "default_value", text="Colour")
                    trans = mat.node_tree.nodes["Mix Shader.001"].inputs[0]
                    row.prop(trans, "default_value", text="Transparency")
                    # TODO: copy transparency from colourpicker
                elif ovtype == "borders":
                    row = layout.row()
                    row.enabled = False
                    row.prop(tb_ov, "colour")
        else:
            row.prop(tb, "show_overlay_options",
                     icon='TRIA_RIGHT',
                     emboss=False)

    def draw_additional(self, layout, tb, tb_ob):

        row = layout.row()
        if tb.show_additional_options:
            row.prop(tb, "show_additional_options",
                     icon='TRIA_DOWN',
                     emboss=False)
            row = layout.row()
            row.enabled = False
            row.prop(tb_ob, "beautified")
            if tb.objecttype == 'tracts':
                row.prop(tb_ob, "nstreamlines")
                row.prop(tb_ob, "streamlines_interpolated")
                row.prop(tb_ob, "tract_weeded")
            elif tb.objecttype == 'surfaces':
                pass
            elif tb.objecttype == 'voxelvolumes':
                pass
        else:
            row.prop(tb, "show_additional_options",
                     icon='TRIA_RIGHT',
                     emboss=False)

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


class ObjectListOb(UIList):

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


class ObjectListOv(UIList):

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
        items=(('UP_ob', "UpOb", ""),
               ('DOWN_ob', "DownOb", ""),
               ('REMOVE_ob', "RemoveOb", ""),
               ('UP_ov', "UpOv", ""),
               ('DOWN_ov', "DownOv", ""),
               ('REMOVE_ov', "RemoveOv", "")))

    def invoke(self, context, event):

        scn = context.scene
        tb = scn.tb

        tb_ob, ob_idx = tb_utils.active_tb_object()

        collection = eval("%s.%s" % ("tb", tb.objecttype))
        validate_tb_objects([collection])

        if self.action.endswith('_ob'):
            data = "tb"
            type = tb.objecttype
        elif self.action.endswith('_ov'):
            data = "tb_ob"
            type = tb.overlaytype

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
                name = collection[idx].name
                info = 'removed %s' % (name)

                if self.action.endswith('_ob'):
                    for ob in bpy.data.objects:
                        ob.select = ob.name == name
                    scn.objects.active = ob
                    bpy.ops.object.mode_set(mode='OBJECT')
                    bpy.ops.object.delete()
                    for border in tb_ob.borders:
                        for ob in bpy.data.objects:
                            ob.select = ob.name == border.name
                        scn.objects.active = bpy.data.objects[border.name]
                        bpy.ops.object.delete()
                        # TODO: remove the empty that groups the curves
                elif self.action.endswith('_ov'):
                    if tb_ob.isvalid:
                        if type == 'borders':
                            name = collection[idx].name
                            for ob in bpy.data.objects:
                                ob.select = ob.name == name
                            scn.objects.active = bpy.data.objects[name]
                            bpy.ops.object.delete()
                            # TODO: remove the empty
                            # that groups the curves if border is last
                        else:
                            ob = bpy.data.objects[tb_ob.name]
                            vg = ob.vertex_groups.get(name)
                            if vg is not None:
                                ob.vertex_groups.remove(vg)

                            vc = ob.data.vertex_colors.get(name)
                            # FIXME: does not work for tract-scalars
                            if vc is not None:
                                ob.data.vertex_colors.remove(vc)

                            ob_mats = ob.data.materials
                            mat_idx = ob_mats.find(name)
                            if mat_idx != -1:
                                ob_mats.pop(mat_idx, update_data=True)
                            mats = bpy.data.materials
                            mat = mats.get(name)
                            if (mat is not None) and (mat.users < 2):
                                mat.user_clear()
                                bpy.data.materials.remove(mat)

                collection.remove(idx)
                self.report({'INFO'}, info)
                exec("%s.index_%s -= 1" % (data, type))

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


class ImportLabels(Operator, ImportHelper):
    bl_idname = "tb.import_labels"
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


class ImportBorders(Operator, ImportHelper):
    bl_idname = "tb.import_borders"
    bl_label = "Import border overlay"
    bl_description = "Import border overlay to curves"
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

        tb_ov = tb_utils.active_tb_overlay()[0]

        mat = bpy.data.materials[tb_ov.name]
        diff = mat.node_tree.nodes["_Diffuse BSDF"]
        diff.inputs[0].default_value = tb_ov.colour
        mix2 = mat.node_tree.nodes["_Mix Shader.001"]
        mix2.inputs[0].default_value = tb_ov.colour[3]

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

            obs = [ob for ob in bpy.data.objects
                   if ob.type not in ["CAMERA", "LAMP", "EMPTY"]]
            sobs = context.selected_objects

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

#             if len(sobs) == 1:
#                 row = self.layout.row()
#                 row.separator()
#                 row = self.layout.row()
#                 row.label(text="Add preset material: ")
#                 row.prop(tb, "colourpicker")
#                 col = self.layout.column()
#                 col.prop(tb, "colourtype", expand=True)
#             if (len(sobs) == 1) and sobs[0].vertex_groups:
#                 row = self.layout.row()
#                 row.separator()
#                 row = self.layout.row()
#                 row.label(text="Combine overlays/labels: ")
#                 row = self.layout.row()
#                 row.prop(tb, "vgs2vc")
#                 row = self.layout.row()
#                 row.operator("tb.vertexcolour_from_vertexgroups",
#                              text="Blend to vertexcolours",
#                              icon="COLOR")

        else:
            row = self.layout.row()
            row.label(text="Please use the main scene for TractBlender.")
            row = self.layout.row()
            row.operator("tb.switch_to_main",
                         text="Switch to main",
                         icon="FORWARD")


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

            self.draw_nibabel(self.layout, tb)

        else:
            row = self.layout.row()
            row.label(text="Please use the main scene for TractBlender.")
            row = self.layout.row()
            row.operator("tb.switch_to_main",
                         text="Switch to main",
                         icon="FORWARD")

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
                validate_tb_overlays(ob, [item.scalars, item.labels])


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
    items.append(("labels", "labels",
                  "List the label overlays", 2))
    if tb.objecttype == 'surfaces':
        items.append(("borders", "borders",
                      "List the border overlays", 3))

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
    colour = FloatVectorProperty(
        name="Border color",
        description="The color of the border",
        subtype="COLOR",
        size=4,
        min=0,
        max=1)
    iterations = IntProperty(
        name="iterations",
        description="smoothing iterations",
        default=10,
        min=0)
    factor = FloatProperty(
        name="factor",
        description="smoothing factor",
        default=0.5,
        min=0)
    bevel_depth = FloatProperty(
        name="bevel_depth",
        description="bevel depth",
        default=0.5,
        min=0)
    bevel_resolution = IntProperty(
        name="bevel_resolution",
        description="bevel resolution",
        default=10,
        min=0)


# TODO: remember and display filepaths
class TractProperties(PropertyGroup):
    """Properties of tracts."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the tract (default: filename)",
        default="")
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
    labels = CollectionProperty(
        type=LabelProperties,
        name="labels",
        description="The collection of loaded labels")
    index_labels = IntProperty(
        name="label index",
        description="index of the labels collection",
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
    labels = CollectionProperty(
        type=LabelProperties,
        name="labels",
        description="The collection of loaded labels")
    index_labels = IntProperty(
        name="label index",
        description="index of the labels collection",
        default=0,
        min=0)
    borders = CollectionProperty(
        type=BorderProperties,
        name="borders",
        description="The collection of loaded borders")
    index_borders = IntProperty(
        name="border index",
        description="index of the borders collection",
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
    labels = CollectionProperty(
        type=LabelProperties,
        name="labels",
        description="The collection of loaded labels")
    index_labels = IntProperty(
        name="label index",
        description="index of the labels collection",
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

    show_transform_options = BoolProperty(
        name="Transform",
        default=False,
        description="Show/hide the object's transform options")
    show_overlay_options = BoolProperty(
        name="Overlays",
        default=False,
        description="Show/hide the object's overlay options")
    show_appearance_options = BoolProperty(
        name="Preset materials",
        default=False,
        description="Show/hide the object's preset materials options")
    show_additional_options = BoolProperty(
        name="Additional options",
        default=False,
        description="Show/hide the object's additional options")

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
