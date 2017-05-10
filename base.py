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
# from . import base as nb_ba
from . import beautify as nb_be
from . import colourmaps as nb_cm
from . import imports as nb_im
from . import materials as nb_ma
from . import overlays as nb_ol
from . import panels as nb_pa
from . import renderpresets as nb_rp
from . import scenepresets as nb_sp
from . import settings as nb_se
from . import utils as nb_ut

# from .imports import (check_texdir,
#                       read_affine_matrix,
#                       voxelvolume_slice_drivers_surface)
# from .beautify import beautify_brain
# from .utils import (check_name,
#                     active_nb_object,
#                     update_name)
# from .materials import (material_update,
#                         material_enum_update,
#                         materialise,
#                         load_surface_textures)
# from .animations import surfaces_enum_callback
# from .colourmaps import (ColorRampProperties,
#                          colourmap_enum_callback,
#                          colourmap_enum_update)
# from .overlays import (ScalarGroupProperties,
#                        LabelGroupProperties,
#                        BorderGroupProperties,
#                        index_scalars_update,
#                        index_labels_update)


# =========================================================================== #


class ImportTracts(Operator, ImportHelper):
    bl_idname = "nb.import_tracts"
    bl_label = "Import tracts"
    bl_description = "Import tracts as curves"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.vtk;" +
                "*.bfloat;*.Bfloat;*.bdouble;*.Bdouble;" +
                "*.tck;*.trk;" +
                "*.npy;*.npz;*.dpy")
        # NOTE: multiline comment not working here

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
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
        nb = scn.nb

        importfun = eval("import_%s" % importtype[:-1])

        filenames = [file.name for file in self.files]
        if not filenames:
            filenames = os.listdir(self.directory)

        for f in filenames:
            fpath = os.path.join(self.directory, f)

            ca = [bpy.data.objects, bpy.data.meshes,
                  bpy.data.materials, bpy.data.textures]
            name = nb_ut.check_name(self.name, fpath, ca)

            obs, info_imp, info_geom = importfun(fpath, name, "", impdict)

            for ob in obs:
                try:
                    self.beautify
                except:  # force updates on voxelvolumes
                    nb.index_voxelvolumes = nb.index_voxelvolumes
#                     item.rendertype = item.rendertype  # FIXME
                else:
                    info_mat = nb_ma.materialise(ob,
                                                 self.colourtype,
                                                 self.colourpicker,
                                                 self.transparency)
                    info_beau = nb_be.beautify_brain(ob,
                                                     importtype,
                                                     self.beautify,
                                                     beaudict)

            info = info_imp
            if nb.verbose:
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
    bl_idname = "nb.import_surfaces"
    bl_label = "Import surfaces"
    bl_description = "Import surfaces as mesh data"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.obj;*.stl;" +
                "*.gii;" +
                "*.white;*.pial;*.inflated;*.sphere;*.orig;" +
                "*.blend")
        # NOTE: multiline comment not working here

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
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
    """Set the voxelvolume name according to the selected file."""

    ca = [bpy.data.meshes,
          bpy.data.materials,
          bpy.data.textures]
    self.name = nb_ut.check_name(self.files[0].name, "", ca)


def name_update(self, context):
    """Set the texture directory to the voxelvolume name."""

    self.texdir = "//voltex_%s" % self.name


def texdir_update(self, context):
    """Evaluate if a valid texture directory exists."""

    self.has_valid_texdir = nb_im.check_texdir(self.texdir,
                                               self.texformat,
                                               overwrite=False)


def is_overlay_update(self, context):
    """Switch the parentpath base/overlay."""

    if self.is_overlay:
        try:
            nb_ob = nb_ut.active_nb_object()[0]
        except IndexError:
            pass  # no nb_obs found
        else:
            self.parentpath = nb_ob.path_from_id()
    else:
        self.parentpath = context.scene.nb.path_from_id()


def h5_dataset_callback(self, context):
    """Populate the enum based on available options."""

    names = []

    def h5_dataset_add(name, obj):
        if isinstance(obj.id, h5py.h5d.DatasetID):
            names.append(name)

    try:
        import h5py
        f = h5py.File(os.path.join(self.directory, self.files[0].name), 'r')
    except:
        items = [("no data", "no data", "not a valid h5", 0)]
    else:
        f.visititems(h5_dataset_add)
        f.close()
        items = [(name, name, "List the datatree", i)
                 for i, name in enumerate(names)]

        return items


class ImportVoxelvolumes(Operator, ImportHelper):
    bl_idname = "nb.import_voxelvolumes"
    bl_label = "Import voxelvolumes"
    bl_description = "Import voxelvolumes to textures"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath", type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.nii;*.nii.gz;*.img;*.hdr;" +
                "*.h5;" +
                "*.png;*.jpg;*.tif;*.tiff;")
        # NOTE: multiline comment not working here

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="voxelvolume",
        update=name_update)
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
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

    import_objects = ImportTracts.import_objects

    def execute(self, context):

        importtype = "voxelvolumes"
        impdict = {"is_overlay": self.is_overlay,
                   "is_label": self.is_label,
                   "parentpath": self.parentpath,
                   "texdir": self.texdir,
                   "texformat": self.texformat,
                   "overwrite": self.overwrite,
                   "dataset": self.dataset,
                   "vol_idx": self.vol_idx}
        beaudict = {}

        self.import_objects(importtype, impdict, beaudict)

        return {"FINISHED"}

    def draw(self, context):

        scn = context.scene
        nb = scn.nb

        layout = self.layout

        # FIXME: solve with update function
        if self.name_mode == "filename":
            voltexdir = [s for s in self.directory.split('/')
                         if "voltex_" in s]
              # FIXME: generalize to other namings
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
            file = self.files[0]
        except:
            pass
        else:
            if file.name.endswith('.h5'):
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

        if self.parentpath.startswith("nb.voxelvolumes"):
            self.is_overlay = True

        if context.scene.nb.overlaytype == "labelgroups":
            self.is_label = True

        self.name = self.name
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


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


def surfaces_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(surface.name, surface.name, "List the surfaces", i)
             for i, surface in enumerate(nb.surfaces)]

    return items


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





def sformfile_update(self, context):
    """Set the sform transformation matrix for the object."""

    try:
        ob = bpy.data.objects[self.name]
    except:
        pass
    else:
        sformfile = bpy.path.abspath(self.sformfile)
        affine = nb_im.read_affine_matrix(sformfile)
        ob.matrix_world = affine


# TODO: this should be inherited by voxelvolume overlays
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


@persistent
def slices_handler(dummy):
    """Set surface or volume rendering for the voxelvolume."""

    scn = bpy.context.scene
    nb = scn.nb

    for vvol in nb.voxelvolumes:
        slices_update(vvol, bpy.context)
    for vvol in nb.voxelvolumes:
        for scalargroup in vvol.scalargroups:
            slices_update(scalargroup, bpy.context)
        for labelgroup in vvol.labelgroups:
            slices_update(labelgroup, bpy.context)

bpy.app.handlers.frame_change_pre.append(slices_handler)


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
                    nb_im.voxelvolume_slice_drivers_surface(self, ts, idx, "scale")
                    nb_im.voxelvolume_slice_drivers_surface(self, ts, idx, "offset")


# FIXME: excessive to remove/add these drivers at every frame;
# mostly just need an update of the offset values for texture mapping;
# except when keyframing rendertype!
@persistent
def rendertype_enum_handler(dummy):
    """Set surface or volume rendering for the voxelvolume."""

    scn = bpy.context.scene
    nb = scn.nb

    for vvol in nb.voxelvolumes:
        rendertype_enum_update(vvol, bpy.context)
    for vvol in nb.voxelvolumes:
        for scalargroup in vvol.scalargroups:
            rendertype_enum_update(scalargroup, bpy.context)
        for labelgroup in vvol.labelgroups:
            rendertype_enum_update(labelgroup, bpy.context)

bpy.app.handlers.frame_change_pre.append(rendertype_enum_handler)
# does this need to be post?


def texture_directory_update(self, context):
    """Update the texture."""

    if "surfaces" in self.path_from_id():
        nb_ma.load_surface_textures(self.name, self.texdir, len(self.scalars))
    elif "voxelvolumes" in self.path_from_id():
        pass  # TODO


class TractProperties(PropertyGroup):
    """Properties of tracts."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the tract (default: filename)",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
        type=nb_ol.ScalarGroupProperties,
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
        subtype="COLOR",
        update=material_update)
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.,
        update=material_update)

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
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
        type=nb_ol.ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded timeseries")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0,
        update=index_scalars_update)
    labelgroups = CollectionProperty(
        type=nb_ol.LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0,
        update=index_labels_update)
    bordergroups = CollectionProperty(
        type=nb_ol.BorderGroupProperties,
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
        subtype="COLOR",
        update=material_update)
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.0,
        update=material_update)

    sphere = EnumProperty(
        name="Unwrapping sphere",
        description="Select sphere for unwrapping",
        items=surfaces_enum_callback)


class VoxelvolumeProperties(PropertyGroup):
    """Properties of voxelvolumes."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the voxelvolume (default: filename)",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
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
        type=nb_ol.ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded scalargroups")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0)
    labelgroups = CollectionProperty(
        type=nb_ol.LabelGroupProperties,
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
        subtype="COLOR",
        update=material_update)

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


# =========================================================================== #


# def register():
#     bpy.utils.register_class(NeuroBlenderBasePanel)
#     bpy.utils.register_class(ImportTracts)
#     bpy.utils.register_class(ImportSurfaces)
#     bpy.utils.register_class(ImportVoxelvolumes)
#     bpy.utils.register_class(TractProperties)
#     bpy.utils.register_class(SurfaceProperties)
#     bpy.utils.register_class(VoxelvolumeProperties)
# #     bpy.utils.register_module(__name__)
# 
# 
# def unregister():  # TODO: unregister handlers
#     bpy.utils.register_class(NeuroBlenderBasePanel)
#     bpy.utils.register_class(ImportTracts)
#     bpy.utils.register_class(ImportSurfaces)
#     bpy.utils.register_class(ImportVoxelvolumes)
#     bpy.utils.register_class(TractProperties)
#     bpy.utils.register_class(SurfaceProperties)
#     bpy.utils.register_class(VoxelvolumeProperties)
# #     bpy.utils.unregister_module(__name__)
# 
# if __name__ == "__main__":
#     register()
