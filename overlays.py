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


"""The NeuroBlender base geometry module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements the importing geometry into NeuroBlender.
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
# from . import overlays as nb_ol
from . import panels as nb_pa
from . import renderpresets as nb_rp
from . import scenepresets as nb_sp
from . import settings as nb_se
from . import utils as nb_ut

# from .base import (slices_update,
#                    texture_directory_update)
# from .imports import (import_overlays,
#                       voxelvolume_slice_drivers_yoke,
#                       material_update)
# from .materials import (assign_vc,
#                         make_material_bake_cycles,
#                         mat_is_yoked_bool_update)
# from .colourmaps import (ColorRampProperties,
#                          colourmap_enum_callback,
#                          colourmap_enum_update)
# from .renderpresets import find_ts_scalargroups
# from .utils import (active_nb_object,
#                     active_nb_overlay,
#                     active_nb_overlayitem,
#                     force_save,
#                     mkdir_p,
#                     update_name)
# from .settings import rendertype_enum_update

# =========================================================================== #


class ImportScalarGroups(Operator, ImportHelper):
    bl_idname = "nb.import_scalargroups"
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
        nb_im.import_overlays(self.directory, filenames,
                        self.name, self.parentpath, "scalargroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportLabelGroups(Operator, ImportHelper):
    bl_idname = "nb.import_labelgroups"
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
        nb_im.import_overlays(self.directory, filenames,
                        self.name, self.parentpath, "labelgroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportBorderGroups(Operator, ImportHelper):
    bl_idname = "nb.import_bordergroups"
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
        nb_im.import_overlays(self.directory, filenames,
                        self.name, self.parentpath, "bordergroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class RevertLabel(Operator):
    bl_idname = "nb.revert_label"
    bl_label = "Revert label"
    bl_description = "Revert changes to imported label colour/transparency"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        item = eval(self.data_path)

        mat = bpy.data.materials[item.name]
        rgb = mat.node_tree.nodes["RGB"]
        rgb.outputs[0].default_value = item.colour
        trans = mat.node_tree.nodes["Transparency"]
        trans.outputs[0].default_value = item.colour[3]

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_it = nb_ut.active_nb_overlayitem()[0]
        self.data_path = nb_it.path_from_id()

        return self.execute(context)


class WeightPaintMode(Operator):
    bl_idname = "nb.wp_preview"
    bl_label = "wp_mode button"
    bl_description = "Go to weight paint mode for preview"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = bpy.context.scene

        nb_ob = nb_ut.active_nb_object()[0]
        scn.objects.active = bpy.data.objects[nb_ob.name]

        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")

        index_scalars_update_func()

        return {"FINISHED"}


class VertexWeight2VertexColors(Operator):
    bl_idname = "nb.vw2vc"
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
        nb = scn.nb

        nb_ob = eval('.'.join(self.data_path.split('.')[:2]))
        group = eval('.'.join(self.data_path.split('.')[:3]))
        ob = bpy.data.objects[nb_ob.name]

        vcs = ob.data.vertex_colors
        vc = vcs.new(name=self.itemname)
        ob.data.vertex_colors.active = vc

        if hasattr(group, 'scalars'):
            scalar = eval(self.data_path)
            vgs = [ob.vertex_groups[scalar.name]]
            ob = nb_ma.assign_vc(ob, vc, vgs)
            mat = ob.data.materials[self.matname]
            nodes = mat.node_tree.nodes
            nodes["Attribute"].attribute_name = self.itemname

        elif hasattr(group, 'labels'):
            vgs = [ob.vertex_groups[label.name] for label in group.labels]
            ob = nb_ma.assign_vc(ob, vc, vgs, group, colour=[0.5, 0.5, 0.5])

        bpy.ops.object.mode_set(mode="VERTEX_PAINT")

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        nb_ov = nb_ut.active_nb_overlay()[0]
        nb_it = nb_ut.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels

        self.data_path = nb_it.path_from_id()

        self.itemname = nb_it.name
        self.matname = nb_ov.name

        return self.execute(context)


class VertexWeight2UV(Operator, ExportHelper):
    bl_idname = "nb.vw2uv"
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
        nb = scn.nb

        nb_ob = eval('.'.join(self.data_path.split('.')[:2]))
        group = eval('.'.join(self.data_path.split('.')[:3]))

        # TODO: exit on no UVmap

        # prep directory
        if not bpy.data.is_saved:
            nb_ut.force_save(nb.projectdir)
        if not group.texdir:
            group.texdir = "//uvtex_%s" % group.name
        nb_ut.mkdir_p(bpy.path.abspath(group.texdir))

        # set the surface as active object
        surf = bpy.data.objects[nb_ob.name]
        for ob in bpy.data.objects:
            ob.select = False
        surf.select = True
        context.scene.objects.active = surf

        # save old and set new render settings for baking
        engine = scn.render.engine
        scn.render.engine = "CYCLES"
        samples = scn.cycles.samples
        preview_samples = scn.cycles.preview_samples
        scn.cycles.samples = 5
        scn.cycles.preview_samples = 5
        scn.cycles.bake_type = 'EMIT'

        # save old and set new materials for baking
        ami = surf.active_material_index
        matnames = [ms.name for ms in surf.material_slots]
        surf.data.materials.clear()
        img = self.create_baking_material(surf, nb.uv_resolution, "bake_vcol")

        # select the item(s) to bake
        dp_split = re.findall(r"[\w']+", self.data_path)
        items = eval("group.%s" % dp_split[-2])
        if not nb.uv_bakeall:
            items = [items[self.index]]

        # bake
        vcs = surf.data.vertex_colors
        for i, item in enumerate(items):
            dp = item.path_from_id()
            bpy.ops.nb.vw2vc(itemname=item.name, data_path=dp,
                             index=i, matname="bake_vcol")
            img.source = 'GENERATED'
            bpy.ops.object.bake()
            if len(items) > 1:
                itemname = item.name[-5:]
            else:
                itemname = item.name
            img.filepath_raw = os.path.join(group.texdir, itemname + ".png")
            img.save()
            vc = vcs[vcs.active_index]
            vcs.remove(vc)

        # reinstate materials and render settings
        surf.data.materials.pop(0)
        for matname in matnames:
            surf.data.materials.append(bpy.data.materials[matname])
        surf.active_material_index = ami
        scn.render.engine = engine
        scn.cycles.samples = samples
        scn.cycles.preview_samples = preview_samples

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        nb_ov = nb_ut.active_nb_overlay()[0]
        nb_it = nb_ut.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels
        self.data_path = nb_it.path_from_id()
        self.itemname = nb_it.name
        self.matname = nb_ov.name

        return self.execute(context)

    def create_baking_material(self, surf, uvres, name):
        """Create a material to bake vertex colours to."""

        mat = nb_ma.make_material_bake_cycles(name)
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
    bl_idname = "nb.unwrap_surface"
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

        nb_ob = nb_ut.active_nb_object()[0]
        self.name_surface = nb_ob.name
        self.name_sphere = nb_ob.sphere

        return self.execute(context)


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


def slices_update(self, context):
    """Set slicethicknesses and positions for the object."""

    ob = bpy.data.objects[self.name+"SliceBox"]
    ob.scale = self.slicethickness

    try:
        # FIXME: should this be scalargroups?
        scalar = self.scalars[self.index_scalars]
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


def texture_directory_update(self, context):
    """Update the texture."""

    if "surfaces" in self.path_from_id():
        nb_ma.load_surface_textures(self.name, self.texdir, len(self.scalars))
    elif "voxelvolumes" in self.path_from_id():
        pass  # TODO


def material_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    if context.scene.nb.engine.startswith("BLENDER"):
        CR2BR(mat)


def mat_is_yoked_bool_update(self, context):
    """"""

    pass  # FIXME: implement this


def colourmap_enum_callback(self, context):
    """Populate the enum based on available options."""

    def order_cmaps(mapnames, pref_order):
        """Order a list starting with with a prefered ordering."""

        mapnames_ordered = []
        for mapname in pref_order:
            if mapname in mapnames:
                mapnames_ordered.append(mapname)
                mapnames.pop(mapnames.index(mapname))
        if mapnames:
            mapnames_ordered += mapnames

        return mapnames_ordered

    cmap_dir = os.path.join("presets","neuroblender_cmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    files = glob(os.path.join(preset_path, '*.py'))

    mapnames = [os.path.splitext(os.path.basename(f))[0]
                for i, f in enumerate(files)]

    pref_order = ["grey", "jet", "hsv", "hot", "cool",
                  "spring", "summer", "autumn", "winter",
                  "parula"]
    mapnames = order_cmaps(mapnames, pref_order)

    items = []
    for i, mapname in enumerate(mapnames):
        displayname = bpy.path.display_name(mapname)
        items.append((mapname, displayname, "", i))

    return items


def colourmap_enum_update(self, context):
    """Assign a new colourmap to the object."""

    scn = context.scene
    nb = scn.nb

    nb_ob = nb_ut.active_nb_object()[0]
    if hasattr(nb_ob, 'slicebox'):
        cr = bpy.data.textures[self.name].color_ramp
        cr_parentpath = 'bpy.data.textures["{}"]'.format(self.name)
    else:
        if hasattr(nb_ob, "nstreamlines"):
            ng = bpy.data.node_groups.get("TractOvGroup")
            cr = ng.nodes["ColorRamp"].color_ramp
            ng_path = 'bpy.data.node_groups["TractOvGroup"]'
            # FIXME: include self.name
            cr_parentpath = '{}.nodes["ColorRamp"]'.format(ng_path)
        elif hasattr(nb_ob, "sphere"):
            nt = bpy.data.materials[self.name].node_tree
            cr = nt.nodes["ColorRamp"].color_ramp
            nt_path = 'bpy.data.materials["{}"].node_tree'.format(self.name)
            cr_parentpath = '{}.nodes["ColorRamp"]'.format(nt_path)

    colourmap = self.colourmap_enum

    # load preset
    cr_path = '{}.color_ramp'.format(cr_parentpath)
    nb.cr_path = cr_path
    menu_idname = "OBJECT_MT_colourmap_presets"

    cmap_dir = os.path.join("presets","neuroblender_cmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    filepath = os.path.join(preset_path, '{}.py'.format(colourmap))

    bpy.ops.script.execute_preset_cr(filepath=filepath,
                                     menu_idname=menu_idname,
                                     cr_path=cr_path)


def rendertype_enum_update(self, context):
    """"""

    pass  #FIXME: where is this function?





def is_yoked_bool_update(self, context):
    """Add or remove drivers linking voxelvolume and overlay."""

    nb_ob = nb_ut.active_nb_object()[0]
    for prop in ['slicethickness', 'sliceposition', 'sliceangle']:
        for idx in range(0, 3):
            if self.is_yoked:
                nb_im.voxelvolume_slice_drivers_yoke(nb_ob, self, prop, idx)
            else:
                self.driver_remove(prop, idx)


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
    nb = scn.nb

    try:
        preset = nb.presets[nb.index_presets]
    except:
        pass
    else:
        for anim in preset.animations:
            if anim.animationtype == "TimeSeries":

                sgs = nb_rp.find_ts_scalargroups(anim)
                sg = sgs[anim.anim_timeseries]

                scalar = sg.scalars[sg.index_scalars]

                if sg.path_from_id().startswith("nb.surfaces"):
                    # update Image Sequence Texture index
                    mat = bpy.data.materials[sg.name]
                    itex = mat.node_tree.nodes["Image Texture"]
                    itex.image_user.frame_offset = scn.frame_current
                    # FIXME: more flexible indexing

                elif sg.path_from_id().startswith("nb.voxelvolumes"):
                    index_scalars_update_vvolscalar_func(sg, scalar,
                                                         nb.texmethod)


bpy.app.handlers.frame_change_pre.append(index_scalars_handler_func)


def index_scalars_update_func(group=None):
    """Switch views on updating overlay index."""

    scn = bpy.context.scene
    nb = scn.nb

    if group is None:
        group = nb_ut.active_nb_overlay()[0]

    nb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    nb_ob = eval(nb_ob_path)
    ob = bpy.data.objects[nb_ob.name]

    try:
        scalar = group.scalars[group.index_scalars]
    except IndexError:
        pass
    else:
        name = scalar.name

        if group.path_from_id().startswith("nb.surfaces"):

            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx

            if hasattr(group, 'scalars'):

                mat = bpy.data.materials[group.name]

                # update Image Sequence Texture index
                itex = mat.node_tree.nodes["Image Texture"]
                itex.image_user.frame_offset = group.index_scalars

                # update Vertex Color attribute
                attr = mat.node_tree.nodes["Attribute"]
                attr.attribute_name = name  # FIXME

                vc_idx = ob.data.vertex_colors.find(name)
                ob.data.vertex_colors.active_index = vc_idx

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

        if group.path_from_id().startswith("nb.tracts"):
            if hasattr(group, 'scalars'):
                for i, spline in enumerate(ob.data.splines):
                    splname = name + '_spl' + str(i).zfill(8)
                    spline.material_index = ob.material_slots.find(splname)

        # FIXME: used texture slots
        if group.path_from_id().startswith("nb.voxelvolumes"):
            if hasattr(group, 'scalars'):

                index_scalars_update_vvolscalar_func(group, scalar,
                                                     nb.texmethod)


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
    nb = scn.nb

    nb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    nb_ob = eval(nb_ob_path)
    ob = bpy.data.objects[nb_ob.name]

    if group is None:
        group = nb_ut.active_nb_overlay()[0]

    try:
        label = group.labels[group.index_labels]
    except IndexError:
        pass
    else:
        name = label.name

        if "surfaces" in group.path_from_id():
            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx


class ScalarProperties(PropertyGroup):
    """Properties of scalar overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the scalar overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
        items=colourmap_enum_callback,
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=nb_cm.ColorRampProperties,
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
        description="The name of the label overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
        max=1,
        update=material_update)


class BorderProperties(PropertyGroup):
    """Properties of border overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
        max=1,
        update=material_update)


class ScalarGroupProperties(PropertyGroup):
    """Properties of time series overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the time series overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
        items=colourmap_enum_callback,
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=nb_cm.ColorRampProperties,
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
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=4,
        min=-1.5708,
        max=1.5708,
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
        description="The name of the label overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=colourmap_enum_callback,
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=nb_cm.ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)

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
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=4,
        min=-1.5708,
        max=1.5708,
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
        description="The name of the border overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
