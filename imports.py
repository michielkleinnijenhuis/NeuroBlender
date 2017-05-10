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

# ========================================================================== #

import os
from glob import glob
import numpy as np
from mathutils import Vector, Matrix
from random import sample
import xml.etree.ElementTree
import pickle

import bpy
from bpy.types import (Operator,
                       OperatorFileListElement)
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       IntProperty)
from bpy_extras.io_utils import ImportHelper

from . import beautify as nb_be
from . import materials as nb_ma
from . import renderpresets as nb_rp
from . import utils as nb_ut

# from .materials import (get_voxmat,
#                         get_voxtex,
#                         set_materials,
#                         get_golden_angle_colour,
#                         create_vc_overlay_tract,
#                         create_vc_overlay,
#                         create_vg_overlay,
#                         create_vg_annot,
#                         create_border_curves)
# from .renderpresets import create_var
# from .utils import (add_item,
#                     move_to_layer,
#                     force_save,
#                     mkdir_p,
#                     active_nb_object,
#                     validate_nibabel,
#                     validate_dipy)  # get_nb_objectinfo


# ========================================================================== #
# brain data import functions
# ========================================================================== #


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


def vvol_name_update(self, context):
    """Set the texture directory to the voxelvolume name."""

    self.texdir = "//voltex_%s" % self.name


def texdir_update(self, context):
    """Evaluate if a valid texture directory exists."""

    self.has_valid_texdir = check_texdir(self.texdir,
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
        update=vvol_name_update)
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
        import_overlays(self.directory, filenames,
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
        import_overlays(self.directory, filenames,
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
        import_overlays(self.directory, filenames,
                        self.name, self.parentpath, "bordergroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


def import_tract(fpath, name, sformfile="",
                 argdict={"weed_tract": 1.,
                          "interpolate_streamlines": 1.}):
    """Import a tract object.

    This imports the streamlines found in the specified file and
    joins the individual streamlines into one 'Curve' object.
    Valid formats include:
    - .bfloat/.Bfloat/.bdouble/.Bdouble (Camino)
      http://camino.cs.ucl.ac.uk/index.php?n=Main.Fileformats
    - .tck (MRtrix)
      http://jdtournier.github.io/mrtrix-0.2/appendix/mrtrix.html
    - .vtk (vtk polydata (ASCII); from MRtrix's 'tracks2vtk' command)
      http://www.vtk.org/wp-content/uploads/2015/04/file-formats.pdf
    - .trk (TrackVis; via nibabel)
    - .dpy (dipy; via dipy)
    - .npy (2d numpy arrays [Npointsx3]; single streamline per file)
    - .npz (zipped archive of Nstreamlines .npy files)
      http://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.savez.html

    'weed_tract' thins tracts by randomly selecting streamlines.
    'interpolate_streamlines' keeps every nth point of the streamlines
    (int(1/interpolate_streamlines)).
    'sformfile' sets matrix_world to affine transformation.

    """

    scn = bpy.context.scene
    nb = scn.nb

    weed_tract = argdict["weed_tract"]
    interp_sl = argdict["interpolate_streamlines"]

    outcome = "failed"
    ext = os.path.splitext(fpath)[1]

    try:
        funcall = "read_streamlines_{}(fpath)".format(ext[1:])
        streamlines = eval(funcall)

    except NameError:
        reason = "file format '{}' not supported".format(ext)
        info = "import {}: {}".format(outcome, reason)
        return [], info, "no geometry loaded"
    except (IOError, FileNotFoundError):
        reason = "file '{}' not valid".format(fpath)
        info = "import {}: {}".format(outcome, reason)
        return [], info, "no geometry loaded"

    except:
        reason = "unknown import error"
        info = "import {}: {}".format(outcome, reason)
        raise

    curve = bpy.data.curves.new(name=name, type='CURVE')
    curve.dimensions = '3D'
    ob = bpy.data.objects.new(name, curve)
    bpy.context.scene.objects.link(ob)

    nsamples = int(len(streamlines) * weed_tract)
    streamlines_sample = sample(range(len(streamlines)), nsamples)
    # TODO: remember 'sample' for scalars import?
    # TODO: weed tract at reading stage where possible?

    for i, streamline in enumerate(streamlines):
        if i in streamlines_sample:
            if interp_sl < 1.:
                subs_sl = int(1/interp_sl)
                streamline = np.array(streamline)[1::subs_sl, :]
#                 TODO: interpolation
#                 from scipy import interpolate
#                 x = interpolate.splprep(list(np.transpose(streamline)))
            make_polyline_ob(curve, streamline)

    # TODO: handle cases where transform info is included in tractfile
    affine = read_affine_matrix(sformfile)
    ob.matrix_world = affine

    props = {"name": name,
             "filepath": fpath,
             "sformfile": sformfile,
             "nstreamlines": nsamples,
             "tract_weeded": weed_tract,
             "streamines_interpolated": interp_sl}
    nb_ut.add_item(nb, "tracts", props)

    nb_ut.move_to_layer(ob, 0)
    scn.layers[0] = True

    scn.objects.active = ob
    ob.select = True

    outcome = "successful"
    info = "import {}".format(outcome)
    info_tf = "transform: {}\n".format(affine)
    info_dc = """decimate:
                 weeding={}; interpolation={}""".format(weed_tract, interp_sl)

    return [ob], info, info_tf + info_dc


def import_surface(fpath, name, sformfile="", argdict={}):
    """Import a surface object.

    This imports the surfaces found in the specified file.
    Valid formats include:
    - .gii (via nibabel)
    - .white/.pial/.inflated/.sphere/.orig (FreeSurfer)
    - .obj
    - .stl
    - .blend

    'sformfile' sets matrix_world to affine transformation.

    """

    scn = bpy.context.scene
    nb = scn.nb

    outcome = "failed"
    ext = os.path.splitext(fpath)[1]

    try:
        funcall = "read_surfaces_{}(fpath, name, sformfile)".format(ext[1:])
        surfaces = eval(funcall)

    except NameError:
        reason = "file format '{}' not supported".format(ext)
        info = "import {}: {}".format(outcome, reason)
        return [], info, "no geometry loaded"
    except (IOError, FileNotFoundError):
        reason = "file '{}' not valid".format(fpath)
        info = "import {}: {}".format(outcome, reason)
        return [], info, "no geometry loaded"
    except ImportError:
        reason = "nibabel not found"
        info = "import {}: {}".format(outcome, reason)
        return [], info, "no geometry loaded"

    except:
        reason = "unknown import error"
        info = "import {}: {}".format(outcome, reason)
        raise

    for surf in surfaces:

        ob, affine, sformfile = surf

        ob.matrix_world = affine

        props = {"name": name,
                 "filepath": fpath,
                 "sformfile": sformfile}
        nb_ut.add_item(nb, "surfaces", props)

        nb_ut.move_to_layer(ob, 1)
        scn.layers[1] = True

    scn.objects.active = ob
    ob.select = True

    outcome = "successful"
    info = "import {}".format(outcome)
    info_tf = "transform: {}".format(affine)

    return [surf[0] for surf in surfaces] , info, info_tf


def import_voxelvolume(fpath, name, sformfile="", texdict={
        "is_overlay": False, "is_label": False,
        "parentpath": "", "sformfile": "",
        "texdir": "", "texformat": "IMAGE_SEQUENCE",
        "overwrite": False, "dataset": 'stack',
        "vol_idx":-1}):
    """Import a voxelvolume.

    This imports the volumes found in the specified file.
    Valid formats include:
    - .nii(.gz)/.img/.hdr (via nibabel)
    - .h5 (with h5py)
    - Blender/NeuroBlender directory tree (IMAGE_SEQUENCE or 8BIT_RAW .raw)
    -- ...
    -- ...

    'sformfile' sets matrix_world to affine transformation.

    """

    scn = bpy.context.scene
    nb = scn.nb

    texdict["fpath"] = fpath
    texdict["name"] = name
    texdict["sformfile"] = sformfile
    is_overlay = texdict["is_overlay"]
    is_label = texdict["is_label"]
    texdir = texdict["texdir"]
    texformat = texdict["texformat"]

    # prep texture directory
    if not bpy.data.is_saved:
        nb_ut.force_save(nb.projectdir)
    abstexdir = bpy.path.abspath(texdir)
    nb_ut.mkdir_p(abstexdir)

    outcome = "failed"
    ext = os.path.splitext(fpath)[1]

    texdict = load_texdir(texdict)

    item = add_to_collections(texdict)

    mat = nb_ma.get_voxmat(name)
    tex = nb_ma.get_voxtex(mat, texdict, 'vol0000', item)

    if is_label:
        for volnr, label in enumerate(item.labels):
            pass
    elif is_overlay:
        item.rendertype = "SURFACE"
        for scalar in item.scalars:
            volname = scalar.name[-7:]  # FIXME: this is not secure
            pfdict = {"IMAGE_SEQUENCE": os.path.join(volname, '0000.png'),
                      "STRIP": volname + '.png',
                      "8BIT_RAW": volname + '.raw_8bit'}
            scalarpath = os.path.join(texdir, texformat, pfdict[texformat])
            scalar.filepath = scalarpath
            scalar.matname = mat.name
            scalar.texname = tex.name
            if nb.texmethod == 4:
                tex = nb_ma.get_voxtex(mat, texdict, volname, scalar)

    # create the voxelvolume object
#     ob = voxelvolume_object_bool(name, texdict['dims'], texdict['affine'])
    ob, sbox = voxelvolume_object_slicebox(item, texdict)

    # single texture slot for simple switching
    texslot = mat.texture_slots.add()
    texslot.texture = tex
    texslot.use_map_density = True
    texslot.texture_coords = 'ORCO'
    texslot.use_map_emission = True

    voxelvolume_rendertype_driver(mat, item)

    nb_ma.set_materials(ob.data, mat)

    if is_overlay:
        nb_ob = eval(texdict["parentpath"])
        ob.parent = bpy.data.objects[nb_ob.name]
        item.index_scalars = 0  # induce switch
        bpy.ops.object.mode_set(mode='EDIT')  # TODO: more elegant update
        bpy.ops.object.mode_set(mode='OBJECT')

    nb_ut.move_to_layer(ob, 2)
    nb_ut.move_to_layer(sbox, 2)
    scn.layers[2] = True

    scn.render.engine = "BLENDER_RENDER"

    outcome = "successful"
    info = "import {}".format(outcome)
    info_tf = "transform: {}".format(texdict["affine"])
    # more info ...

    return [ob], info, info_tf


def check_texdir(texdir, texformat, overwrite=False, vol_idx=-1):
    """Check whether path is in a valid NeuroBlender volume texture."""

    if overwrite:
        return False

    abstexdir = bpy.path.abspath(texdir)
    if not os.path.isdir(abstexdir):
        return False

    for pf in ('affine', 'dims', 'datarange', 'labels'):
        if not os.path.isfile(os.path.join(abstexdir, "{}.npy".format(pf))):
            return False

    absimdir = os.path.join(abstexdir, texformat)
    if not os.path.isdir(absimdir):
        return False

    if vol_idx != -1:
        absvoldir = os.path.join(absimdir, 'vol%04d' % vol_idx)
        if not os.path.isdir(absvoldir):
            return False
    else:
        absvoldir = os.path.join(absimdir, 'vol%04d' % 0)
        if not os.path.isdir(absvoldir):
            return False
        # TODO: see if all vols are there

    nfiles = len(glob(os.path.join(absimdir, '*')))
    if not nfiles:
        return False

    return True


def load_texdir(texdict):
    """Load a volume texture previously generated in NeuroBlender."""

    texformat = texdict['texformat']
    vol_idx = max(0, texdict['vol_idx'])

    abstexdir = bpy.path.abspath(texdict['texdir'])
    imdir = os.path.join(abstexdir, texformat)
    absimdir = bpy.path.abspath(imdir)

    vols = glob(os.path.join(absimdir, "*"))

    try:
        vol = vols[vol_idx]
        if texformat == "IMAGE_SEQUENCE":
            slices = glob(os.path.join(vol, "*"))
            vol = slices[0]
        texdict['img'] = bpy.data.images.load(vol)

        for pf in ("affine", "dims", "datarange", "labels"):
            npy = os.path.join(abstexdir, "{}.npy".format(pf))
            texdict[pf] = np.load(npy)
    except:
        texdict = create_texdir(texdict)

    texdict['loaded'] = True

    return texdict


def create_texdir(texdict):
    """Generate a NeuroBlender volume texture from a external format."""

    fpath = texdict['fpath']
    sformfile = texdict['sformfile']
    is_label = texdict['is_label']
    fieldname = texdict['dataset']
    vol_idx = texdict['vol_idx']

    abstexdir = bpy.path.abspath(texdict['texdir'])

    niiext = ('.nii', '.nii.gz', '.img', '.hdr', '.h5')
    imext = ('.png', '.jpg', '.tif', '.tiff')

    if fpath.endswith(niiext):

        texdict = prep_nifti(texdict)
        sformfile = sformfile or fpath

    else:  # try to read it as a 3D volume in slices

        texdict['name'] = texdict['name'] or fpath.split(os.sep)[-1]

        srcdir = os.path.dirname(fpath)
        trgdir = os.path.join(abstexdir, texdict['texformat'], 'vol0000')
        nb_ut.mkdir_p(trgdir)

        # educated guess of the files we want to glob
        pat = '*%s' % os.path.splitext(fpath)[1]
        for f in glob(os.path.join(srcdir, pat)):
            fname = os.path.basename(f)
            os.symlink(f, os.path.join(trgdir, fname))

        texdict['img'] = bpy.data.images.load(fpath)

        texdict['dims'] = [s for s in texdict['img'].size] + \
                          [image_sequence_length(fpath)] + [1]
        texdict['texformat'] = "IMAGE_SEQUENCE"
        texdict['datarange'] = [0, 1]
        texdict['labels'] = None
        # TODO: figure out labels and datarange

    texdict['affine'] = read_affine_matrix(sformfile, fieldname)

    # save the essentials to the voltex directory
    for pf in ('affine', 'dims', 'datarange', 'labels'):
        np.save(os.path.join(abstexdir, pf), np.array(texdict[pf]))

    return texdict


def prep_nifti(texdict):
    """Write data in a nifti file to a NeuroBlender volume texture.

    The nifti is read with nibabel with [z,y,x] layout, and is either
    written as an [x,y] PNG image sequence (datarange=[0,1]) or
    as an 8bit raw binary volume with [x,y,z] layout (datarange=[0,255]).
    Labelvolumes: negative labels are ignored (i.e. set to 0)
    """

    scn = bpy.context.scene
    nb = scn.nb

    fpath = texdict['fpath']
    is_label = texdict['is_label']
    fieldname = texdict['dataset']
    vol_idx = texdict['vol_idx']
    texdir = texdict['texdir']
    texformat = texdict['texformat']

    if fpath.endswith('.h5'):
        try:
            import h5py
        except ImportError:
            raise  # TODO: error to indicate how to set up h5py
        else:
            f = h5py.File(fpath, 'r')
            in2out = h5_in2out(f[fieldname])
            data = np.transpose(f[fieldname][:], in2out)
            if vol_idx != -1:  # TODO: make efficient
                data = data[..., vol_idx]

    else:
        try:
            import nibabel as nib
        except ImportError:
            raise  # TODO: error to indicate how to set up nibabel
        else:
            nii_proxy = nib.load(fpath)
            data = nii_proxy.get_data()
            if vol_idx != -1:
                data = data[..., vol_idx]

    data.shape += (1,) * (4 - data.ndim)
    dims = np.array(data.shape)

    if is_label:
        mask = data < 0
        if mask.any():
            print("setting negative labels to 0")
        data[mask] = 0
        labels = np.unique(data)
        labels = labels[labels > 0]
    else:
        labels = None

    data, datarange = normalize_data(data)

    imdir = os.path.join(bpy.path.abspath(texdir), texformat)
    absimdir = bpy.path.abspath(imdir)
    nb_ut.mkdir_p(absimdir)

    data = np.transpose(data)
    fun = eval("write_to_%s" % texformat.lower())
    img = fun(absimdir, data, dims)

    texdict.update({'img': img,
                    'dims': dims,
                    'datarange': datarange,
                    'labels': labels})

    return texdict


def h5_in2out(inds):
    """Permute dimension labels to Fortran order."""

    outlayout = 'xyzct'[0:inds.ndim]
    try:
        inlayout = [d.label for d in inds.dims]
    except:
        inlayout = 'xyzct'[0:inds.ndim]

    in2out = [inlayout.index(l) for l in outlayout]

    return in2out


def normalize_data(data):
    """Normalize data between 0 and 1."""

    data = data.astype('float64')
    datamin = np.amin(data)
    datamax = np.amax(data)
    data -= datamin
    data *= 1/(datamax-datamin)

    return data, [datamin, datamax]


def write_to_image_sequence(absimdir, data, dims):
    """"""

    scn = bpy.context.scene
    ff = scn.render.image_settings.file_format
    cm = scn.render.image_settings.color_mode
    cd = scn.render.image_settings.color_depth

    scn.render.image_settings.file_format = 'PNG'
    scn.render.image_settings.color_mode = 'BW'
    scn.render.image_settings.color_depth = '16'

    for volnr, vol in enumerate(data):
        voldir = os.path.join(absimdir, 'vol%04d' % volnr)
        nb_ut.mkdir_p(voldir)
        vol = np.reshape(vol, [dims[2], -1])
        img = bpy.data.images.new("img", width=dims[0], height=dims[1])
        for slcnr, slc in enumerate(vol):
            pixels = []
            for pix in slc:
                pixels.append([pix, pix, pix, float(pix != 0)])
            pixels = [chan for px in pixels for chan in px]
            img.pixels = pixels
            slcname = str(slcnr).zfill(4) + ".png"
            filepath = os.path.join(voldir, slcname)
            img.filepath_raw = bpy.path.abspath(filepath)
            img.file_format = 'PNG'
#             img.save()
            img.save_render(img.filepath_raw)

    scn.render.image_settings.file_format = ff
    scn.render.image_settings.color_mode = cm
    scn.render.image_settings.color_depth = cd

    return img


def write_to_strip(absimdir, data, dims):
    """"""

    img = bpy.data.images.new("img", width=dims[2]*dims[1], height=dims[0])
    for volnr, vol in enumerate(data):
        vol = np.reshape(vol, [-1, 1])
        pixels = []
        for pix in vol:
            pixels.append([pix, pix, pix, float(pix != 0)])
        pixels = [chan for px in pixels for chan in px]
        img.pixels = pixels
        img.filepath = os.path.join(absimdir, 'vol%04d.png' % volnr)
        img.file_format = 'PNG'
        img.save()

    return img


def write_to_raw_8bit(absimdir, data, dims):
    """"""

    data *= 255
    for volnr, vol in enumerate(data):
        filepath = os.path.join(absimdir, 'vol%04d.8bit_raw' % volnr)
        with open(filepath, "wb") as f:
            f.write(bytes(vol.astype('uint8')))
        img = bpy.data.images.load(filepath)
        img.filepath = filepath

    return img


def image_sequence_length(filepath):
    """Figure out the number of images in a directory.

    from http://blender.stackexchange.com/questions/21092
    """

    basedir, filename = os.path.split(filepath)
    filename_noext, ext = os.path.splitext(filename)

    from string import digits
    if isinstance(filepath, bytes):
        digits = digits.encode()
    filename_nodigits = filename_noext.rstrip(digits)

    if len(filename_nodigits) == len(filename_noext):
        # input isn't from a sequence
        return []

    files = os.listdir(basedir)
    image_list = [os.path.join(basedir, f)
                  for f in files
                  if f.startswith(filename_nodigits) and
                  f.endswith(ext) and
                  f[len(filename_nodigits):-len(ext) if ext else -1].isdigit()]
    n_images = len(image_list)

    return n_images


def add_to_collections(texdict):

    scn = bpy.context.scene
    nb = scn.nb

    name = texdict['name']
    dims = texdict['dims']
    texdir = texdict['texdir']
    datarange = texdict['datarange']
    labels = texdict['labels']

    fpath = texdict['fpath']
    sformfile = texdict['sformfile']
    is_overlay = texdict['is_overlay']
    is_label = texdict['is_label']
    parentpath = texdict['parentpath']

    if is_overlay:

        nb_ob = eval(parentpath)

        props = {"name": name,
                 "filepath": fpath,
                 "dimensions": tuple(dims),
                 "texdir": texdir}

        if is_label:
            labelvals = [int(label) for label in labels]
            props["range"] = (min(labelvals), max(labelvals))
            item = nb_ut.add_item(nb_ob, "labelgroups", props)
            for label in labels:
                colour = nb_ma.get_golden_angle_colour(label) + [1.]
                props = {"name": "label." + str(label).zfill(2),
                         "value": int(label),
                         "colour": tuple(colour)}
                nb_ut.add_item(item, "labels", props)
        else:
            props["range"] = datarange
            item = nb_ut.add_item(nb_ob, "scalargroups", props)
            for volnr in range(dims[3]):
                props = {"name": "%s.vol%04d" % (name, volnr),
                         "range": tuple(datarange)}
                nb_ut.add_item(item, "scalars", props)

    else:
        props = {"name": name,
                 "filepath": fpath,
                 "sformfile": sformfile,
                 "range": tuple(datarange),
                 "dimensions": tuple(dims),
                 "texdir": texdir}
        item = nb_ut.add_item(nb, "voxelvolumes", props)

    return item


def voxelvolume_object_bool(name, dims, affine):
    """"""

    # the voxelvolumebox
    ob = voxelvolume_box_ob(dims, "SliceBox")
    ob.name = name
    ob.matrix_world = affine
    # an empty to hold the sliceboxes
    empty = bpy.data.objects.new(ob.name+"SliceBox", None)
    empty.parent = ob
    empty.location = (0, 0, 0)
    bpy.context.scene.objects.link(empty)
    # create sliceboxes and modifiers
    for dir in 'xyz':
        bool = ob.modifiers.new("bool_%s" % dir, 'BOOLEAN')
        bool.solver = 'CARVE'
        bool.operation = 'INTERSECT'
        sb = voxelvolume_box_ob(dims, "SliceBox")
        sb.name = dir
        sb.parent = empty
        bool.object = sb
        # TODO: no need for vg

    return ob

def voxelvolume_object_slicebox(item, texdict):
    """"""

    scn = bpy.context.scene

    slices = False
    me = bpy.data.meshes.new(texdict["name"])
    ob = bpy.data.objects.new(texdict["name"], me)
    bpy.context.scene.objects.link(ob)
    ob1 = voxelvolume_box_ob(texdict["dims"], "Bounds")
    ob2 = voxelvolume_box_ob(texdict["dims"], "SliceBox")

    ob.select = True
    scn.objects.active = ob
    obs = [ob, ob1, ob2]
    ctx = bpy.context.copy()
    ctx['active_object'] = ob
    ctx['selected_objects'] = obs
    ctx['selected_editable_bases'] = [scn.object_bases[ob.name] for ob in obs]
    bpy.ops.object.join(ctx)

    scn.objects.active = ob
    ob.select = True

    mat = Matrix() if texdict["is_overlay"] else Matrix(texdict["affine"])
    ob.matrix_world = mat

    slicebox = voxelvolume_cutout(ob)

    for idx in range(0,3):
        voxelvolume_slice_drivers_volume(item, slicebox, idx, "scale")
        voxelvolume_slice_drivers_volume(item, slicebox, idx, "location")
        voxelvolume_slice_drivers_volume(item, slicebox, idx, "rotation_euler")

    return ob, slicebox


def voxelvolume_cutout(ob):
    """"""

    scn = bpy.context.scene

    bb_min, bb_max = find_bbox_coordinates([ob])

    for slice in ["SliceBox"]: # , "sagittal", "coronal", "axial"

        empty = bpy.data.objects.new(ob.name+slice, None)
        empty.parent = ob
        empty.location = (0, 0, 0)
#         empty.location = ob.location
#         empty.location[0] = bb_min[0] + (bb_max[0] - bb_min[0]) / 2
#         empty.location[1] = bb_min[1] + (bb_max[1] - bb_min[1]) / 2
#         empty.location[2] = bb_min[2] + (bb_max[2] - bb_min[2]) / 2
        bpy.context.scene.objects.link(empty)
        scn.objects.active = empty

#         saved_location = scn.cursor_location
#         scn.cursor_location = empty.location
#         bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
#         scn.cursor_location = saved_location

        if 0:
            bpy.ops.object.constraint_add(type='LIMIT_SCALE')
            con = empty.constraints["Limit Scale"]
            con.use_transform_limit = True
            con.owner_space = 'LOCAL'
            con.use_min_x = con.use_min_y = con.use_min_z = True
            con.use_max_x = con.use_max_y = con.use_max_z = True
            con.min_x = con.min_y = con.min_z = 0
            con.max_x = con.max_y = con.max_z = 1

            bpy.ops.object.constraint_add(type='LIMIT_LOCATION')
            con = empty.constraints["Limit Location"]
            con.use_transform_limit = True
            con.owner_space = 'LOCAL'
            con.use_min_x = True
            con.use_max_x = True
            con.use_min_y = True
            con.use_max_y = True
            con.use_min_z = True
            con.use_max_z = True
            if slice == "SliceBox":
                con.min_x = con.min_y = con.min_z = 0
                con.max_x = bb_max[0] - bb_min[0]
                con.max_y = bb_max[1] - bb_min[1]
                con.max_z = bb_max[2] - bb_min[2]
                # for GLOBAL space?
    #             con.min_x = bb_min[0]
    #             con.max_x = bb_max[0]
    #             con.min_y = bb_min[1]
    #             con.max_y = bb_max[1]
    #             con.min_z = bb_min[2]
    #             con.max_z = bb_max[2]
            elif slice == "sagittal":
                con.min_x = 0
                con.max_x = dims[0]
                con.min_y = 0
                con.max_y = 0
                con.min_z = 0
                con.max_z = 0
            elif slice == "coronal":
                con.min_x = 0
                con.max_x = 0
                con.min_y = 0
                con.max_y = dims[1]
                con.min_z = 0
                con.max_z = 0
            elif slice == "axial":
                con.min_x = 0
                con.max_x = 0
                con.min_y = 0
                con.max_y = 0
                con.min_z = 0
                con.max_z = dims[2]

        scn.objects.active = ob
        bpy.ops.object.modifier_add(type='HOOK')
        hook = ob.modifiers["Hook"]
        hook.name = slice
        hook.object = empty
        hook.vertex_group = slice
        hook.falloff_type = 'NONE'

    return empty


def voxelvolume_slice_drivers_volume(item, slicebox, index, prop, relative=True):

    scn = bpy.context.scene
    nb = scn.nb

    driver = slicebox.driver_add(prop, index).driver
    driver.type = 'SCRIPTED'

    # dimension of the voxelvolume
    data_path = "%s.dimensions[%d]" % (item.path_from_id(), index)
    nb_rp.create_var(driver, "dim", 'SINGLE_PROP', 'SCENE', scn, data_path)
    # relative slicethickness
    data_path = "%s.slicethickness[%d]" % (item.path_from_id(), index)
    nb_rp.create_var(driver, "slc_th", 'SINGLE_PROP', 'SCENE', scn, data_path)
    # relative sliceposition
    data_path = "%s.sliceposition[%d]" % (item.path_from_id(), index)
    nb_rp.create_var(driver, "slc_pos", 'SINGLE_PROP', 'SCENE', scn, data_path)
    # sliceangle
    data_path = "%s.sliceangle[%d]" % (item.path_from_id(), index)
    nb_rp.create_var(driver, "slc_angle", 'SINGLE_PROP', 'SCENE', scn, data_path)

    if relative:
        if prop == "scale":
            driver.expression = "slc_th"
        elif prop == "rotation_euler":
            driver.expression = "slc_angle"
        elif prop == "location":
            driver.expression = "slc_pos * (dim - slc_th * dim)"
    else:
        if prop == "scale":
            driver.expression = "slc_th / dim"
        elif prop == "rotation_euler":
            driver.expression = "slc_angle"
        elif prop == "location":
            pass

    slicebox.lock_location[index] = True
    slicebox.lock_rotation[index] = True
    slicebox.lock_scale[index] = True


def voxelvolume_slice_drivers_surface(item, tex, index, prop):

    scn = bpy.context.scene
    nb = scn.nb

    driver = tex.driver_add(prop, index).driver
    driver.type = 'SCRIPTED'

    data_path = "%s.slicethickness[%d]" % (item.path_from_id(), index)
    nb_rp.create_var(driver, "slc_th", 'SINGLE_PROP', 'SCENE', scn, data_path)
    if prop == "scale":
        # relative slicethickness
        driver.expression = "slc_th"
    elif prop == "offset":
        # relative sliceposition
        data_path = "%s.sliceposition[%d]" % (item.path_from_id(), index)
        nb_rp.create_var(driver, "slc_pos", 'SINGLE_PROP', 'SCENE', scn, data_path)
        driver.expression = "2*(1/slc_th-1) * slc_pos - (1/slc_th-1)"


def voxelvolume_rendertype_driver(mat, item):

    scn = bpy.context.scene
    nb = scn.nb

    driver = mat.driver_add("type", -1).driver
    driver.type = 'AVERAGE'
    vv_idx = nb.index_voxelvolumes

    data_path = "%s.rendertype" % item.path_from_id()
    nb_rp.create_var(driver, "type", 'SINGLE_PROP', 'SCENE', scn, data_path)


def voxelvolume_slice_drivers_yoke(parent, child, prop, index):

    scn = bpy.context.scene
    nb = scn.nb

    driver = child.driver_add(prop, index).driver
    driver.type = 'SCRIPTED'
    data_path = "%s.%s[%d]" % (parent.path_from_id(), prop, index)
    nb_rp.create_var(driver, "var", 'SINGLE_PROP', 'SCENE', scn, data_path)
    driver.expression = "var"


def find_bbox_coordinates(obs):
    """Find the extreme dimensions in the geometry."""

    bb_world = [ob.matrix_world * Vector(bbco)
                for ob in obs for bbco in ob.bound_box]
    bb_min = np.amin(np.array(bb_world), 0)
    bb_max = np.amax(np.array(bb_world), 0)

    return bb_min, bb_max


def import_overlays(directory, files, name="", parentpath="", ovtype=""):
    """"""

    scn = bpy.context.scene
    nb = scn.nb

    try:
        parent = eval(parentpath)
    except (SyntaxError, NameError):
        parent = nb_ut.active_nb_object()[0]
#     else:
#         obinfo = get_nb_objectinfo(parent.name)
#         nb.objecttype = obinfo['type']
#         exec("nb.index_%s = %s" % (obinfo['type'], obinfo['index']))

    parent_ob = bpy.data.objects[parent.name]

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        importfun = eval("import_%s_%s" % (nb.objecttype, ovtype))

        importfun(fpath, parent_ob, name=name)

    bpy.context.scene.objects.active = parent_ob
    parent_ob.select = True


def import_tracts_scalargroups(fpath, parent_ob, name=""):
    """Import scalar overlay on tract object."""

    # TODO: handle timeseries
    nb_ma.create_vc_overlay_tract(parent_ob, fpath, name=name)


def import_surfaces_scalargroups(fpath, parent_ob, name=""):
    """Import timeseries overlay on surface object."""

    nb_ma.create_vc_overlay(parent_ob, fpath, name=name)


def import_surfaces_scalars(fpath, parent_ob, name=""):
    """Import scalar overlay on surface object.

    TODO: handle timeseries
    """

    if fpath.endswith('.label'):  # but not treated as a label
        nb_ma.create_vg_overlay(parent_ob, fpath, name=name, is_label=False)
    else:  # assumed scalar overlay
        nb_ma.create_vc_overlay(parent_ob, fpath, name=name)


def import_surfaces_labelgroups(fpath, parent_ob, name=""):
    """Import label overlay on surface object.

    TODO: consider using ob.data.vertex_layers_int.new()
    """

    if fpath.endswith('.label'):
        nb_ma.create_vg_overlay(parent_ob, fpath, name=name, is_label=True)
    elif (fpath.endswith('.annot') |
          fpath.endswith('.gii') |
          fpath.endswith('.border')):
        nb_ma.create_vg_annot(parent_ob, fpath, name=name)
        # TODO: figure out from gifti if it is annot or label
    else:  # assumed scalar overlay type with integer labels??
        nb_ma.create_vc_overlay(parent_ob, fpath, name=name)


def import_surfaces_bordergroups(fpath, parent_ob, name=""):
    """Import label overlay on surface object."""

    if fpath.endswith('.border'):
        nb_ma.create_border_curves(parent_ob, fpath, name=name)
    else:
        print("Only Connectome Workbench .border files supported.")


def import_voxelvolumes_scalargroups(fpath, parent_ob, name=""):  # deprecated
    """Import a scalar overlay on a voxelvolume."""

    scn = bpy.context.scene
    nb = scn.nb

    # TODO: handle invalid selections
    # TODO: handle timeseries / groups
    sformfile = ""
    nb_ob = nb_ut.active_nb_object()[0]
    parentpath = nb_ob.path_from_id()

    directory = os.path.dirname(fpath)  # TODO
    filenames = [os.path.basename(fpath)]
    ob = import_voxelvolume(directory, filenames, name,
                            is_overlay=True, is_label=False,
                            parentpath=parentpath)[0]
    ob = ob[0]  # TODO
    ob.parent = parent_ob


def import_voxelvolumes_labelgroups(fpath, parent_ob, name=""):  # deprecated
    """Import a labelgroup overlay on a voxelvolume."""

    scn = bpy.context.scene
    nb = scn.nb

    # TODO: handle invalid selections
    sformfile = ""
    nb_ob, _ = nb_ut.active_nb_object()
    parentpath = nb_ob.path_from_id()

    directory = os.path.dirname(fpath)  # TODO
    filenames = [os.path.basename(fpath)]
    ob = import_voxelvolume(directory, filenames, name,
                            is_overlay=True, is_label=True,
                            parentpath=parentpath)[0]
    ob = ob[0]  # TODO
    ob.parent = parent_ob


def read_tractscalar(fpath):
    """"""

    if fpath.endswith('.npy'):
        scalar = np.load(fpath)
        scalars = [scalar]
    elif fpath.endswith('.npz'):
        npzfile = np.load(fpath)
        for k in npzfile:
            scalar.append(npzfile[k])
        scalars = [scalar]
    elif fpath.endswith('.asc'):
        # mrtrix convention assumed (1 streamline per line)
        scalar = []
        with open(fpath) as f:
            for line in f:
                tokens = line.rstrip("\n").split(' ')
                points = []
                for token in tokens:
                    if token:
                        points.append(float(token))
                scalar.append(points)
        scalars = [scalar]
    if fpath.endswith('.pickle'):
        with open(fpath, 'rb') as f:
            scalars = pickle.load(f)

    return scalars


def read_surfscalar(fpath):
    """Read a surface scalar overlay file."""

    scn = bpy.context.scene
    nb = scn.nb

    # TODO: handle what happens on importing multiple objects
    # TODO: read more formats: e.g. .dpv, .dpf, ...
    if fpath.endswith('.npy'):
        scalars = np.load(fpath)
    elif fpath.endswith('.npz'):
        npzfile = np.load(fpath)
        for k in npzfile:
            scalars.append(npzfile[k])
    elif fpath.endswith('.gii'):
        nib = nb_ut.validate_nibabel('.gii')
        if nb.nibabel_valid:
            gio = nib.gifti.giftiio
            img = gio.read(fpath)
            scalars = []
            for darray in img.darrays:
                scalars.append(darray.data)
            scalars = np.array(scalars)
    elif fpath.endswith('dscalar.nii'):
        # CIFTI not yet working properly: in nibabel?
        nib = nb_ut.validate_nibabel('dscalar.nii')
        if nb.nibabel_valid:
            gio = nib.gifti.giftiio
            nii = gio.read(fpath)
            scalars = np.squeeze(nii.get_data())
    else:  # I will try to read it as a freesurfer binary
        nib = nb_ut.validate_nibabel('')
        if nb.nibabel_valid:
            fsio = nib.freesurfer.io
            scalars = fsio.read_morph_data(fpath)
        else:
            with open(fpath, "rb") as f:
                f.seek(15, os.SEEK_SET)
                scalars = np.fromfile(f, dtype='>f4')

    return np.atleast_2d(scalars)


def read_surflabel(fpath, is_label=False):
    """Read a surface label overlay file."""

    scn = bpy.context.scene
    nb = scn.nb

    if fpath.endswith('.label'):
        nib = nb_ut.validate_nibabel('.label')
        if nb.nibabel_valid:
            fsio = nib.freesurfer.io
            label, scalars = fsio.read_label(fpath, read_scalars=True)
        else:
            labeltxt = np.loadtxt(fpath, skiprows=2)
            label = labeltxt[:, 0]
            scalars = labeltxt[:, 4]

        if is_label:
            scalars = None  # TODO: handle file where no scalars present

    return label, scalars


def read_surfannot(fpath):
    """Read a surface annotation file."""

    scn = bpy.context.scene
    nb = scn.nb

    nib = nb_ut.validate_nibabel('.annot')
    if nb.nibabel_valid:
        if fpath.endswith(".annot"):
            fsio = nib.freesurfer.io
            labels, ctab, bnames = fsio.read_annot(fpath, orig_ids=False)
            names = [name.decode('utf-8') for name in bnames]
        elif fpath.endswith(".gii"):
            gio = nib.gifti.giftiio
            img = gio.read(fpath)
            img.labeltable.get_labels_as_dict()
            labels = img.darrays[0].data
            labeltable = img.labeltable
            labels, ctab, names = gii_to_freesurfer_annot(labels, labeltable)
        elif fpath.endswith('.dlabel.nii'):
            pass  # TODO # CIFTI not yet working properly: in nibabel?
        return labels, ctab, names
    else:
        print('nibabel required for reading .annot files')


def gii_to_freesurfer_annot(labels, labeltable):
    """Convert gifti annotation file to nibabel freesurfer format."""

    names = [name for _, name in labeltable.labels_as_dict.items()]
    ctab = [np.append((np.array(l.rgba)*255).astype(int), l.key)
            for l in labeltable.labels]
    ctab = np.array(ctab)
    # TODO: check scikit-image relabel_sequential code
    # TODO: check if relabeling is necessary
    newlabels = np.zeros_like(labels)
    i = 1
    for _, l in enumerate(labeltable.labels, 1):
        labelmask = np.where(labels == l.key)[0]
        newlabels[labelmask] = i
        if (labelmask != 0).sum():
            i += 1

    return labels, ctab, names


def read_surfannot_freesurfer(fpath):
    """Read a .annot surface annotation file."""

    scn = bpy.context.scene
    nb = scn.nb

    nib = nb_ut.validate_nibabel('.annot')
    if nb.nibabel_valid:
        fsio = nib.freesurfer.io
        labels, ctab, bnames = fsio.read_annot(fpath, orig_ids=False)
        names = [name.decode('utf-8') for name in bnames]
        return labels, ctab, names
    else:
        print('nibabel required for reading .annot files')


def read_surfannot_gifti(fpath):
    """Read a .gii surface annotation file."""

    scn = bpy.context.scene
    nb = scn.nb

    nib = nb_ut.validate_nibabel('.annot')
    if nb.nibabel_valid:
        gio = nib.gifti.giftiio
        img = gio.read(fpath)
        img.labeltable.get_labels_as_dict()
        labels = img.darrays[0].data
        labeltable = img.labeltable
        return labels, labeltable
    else:
        print('nibabel required for reading .annot files')


def read_borders(fpath):
    """Read a Connectome Workbench .border file."""

    root = xml.etree.ElementTree.parse(fpath).getroot()

#     v = root.get('Version')
#     s = root.get('Structure')
#     nv = root.get('SurfaceNumberOfVertices')
#     md = root.find('MetaData')

    borderlist = []
    borders = root.find('Class')
    for border in borders:
        borderdict = {}
        borderdict['name'] = border.get('Name')
        borderdict['rgb'] = (float(border.get('Red')),
                             float(border.get('Green')),
                             float(border.get('Blue')))
        bp = border.find('BorderPart')
        borderdict['closed'] = bp.get('Closed')
        verts = [[int(c) for c in v.split()]
                 for v in bp.find('Vertices').text.split("\n") if v]
        borderdict['verts'] = np.array(verts)
#         weights = [[float(c) for c in v.split()]
#                    for v in bp.find('Weights').text.split("\n") if v]
#         borderdict['weights'] = np.array(weights)
        borderlist.append(borderdict)

    return borderlist


def voxelvolume_box_ob(dims=[256, 256, 256], type="verts"):
    """"""

    me = bpy.data.meshes.new(type)
    ob = bpy.data.objects.new(type, me)
    bpy.context.scene.objects.link(ob)

    nverts = 0

    width = dims[0]
    height = dims[1]
    depth = dims[2]

    v = [(    0,      0,     0),
         (width,      0,     0),
         (width, height,     0),
         (    0, height,     0),
         (    0,      0, depth),
         (width,      0, depth),
         (width, height, depth),
         (    0, height, depth)]

#     vidxs = range(nverts, nverts + 8)
#     faces = [(0, 1, 2, 3), (0, 1, 5, 4), (1, 2, 6, 5),
#              (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    if type=="SliceBox":
        vidxs = range(nverts, nverts + 8)
        faces = [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5),
                 (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    elif type == "Bounds":
        vidxs = range(nverts, nverts + 8)
        faces = []
    elif type == "sagittal":
        vidxs = range(nverts, nverts + 4)
        v = [v[0], v[3], v[7], v[4]]
        faces = [(0, 1, 2, 3)]
    elif type == "coronal":
        vidxs = range(nverts, nverts + 4)
        v = [v[0], v[1], v[5], v[4]]
        faces = [(0, 1, 2, 3)]
    elif type == "axial":
        vidxs = range(nverts, nverts + 4)
        v = [v[0], v[1], v[2], v[3]]
        faces = [(0, 1, 2, 3)]

    me.from_pydata(v, [], faces)
    me.update(calc_edges=True)

    vg = ob.vertex_groups.new(type)
    vg.add(vidxs, 1.0, "REPLACE")

    return ob


def voxelvolume_box(ob=None, dims=[256, 256, 256], type="verts"):
    """Create a box with the dimensions of the voxelvolume."""

    if ob is None:
        me = bpy.data.meshes.new(type)
    else:
        me = ob.data

    nverts = len(me.vertices)

    width = dims[0]
    height = dims[1]
    depth = dims[2]

    v = [(    0,      0,     0),
         (width,      0,     0),
         (width, height,     0),
         (    0, height,     0),
         (    0,      0, depth),
         (width,      0, depth),
         (width, height, depth),
         (    0, height, depth)]

    faces = [(0, 1, 2, 3), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]

    if type=="box":
        vidxs = range(nverts, nverts + 8)
        me.from_pydata(v, [], faces)
        me.update(calc_edges=True)
    elif type == "bounds":
        vidxs = range(nverts, nverts + 8)
        for vco in v:
            me.vertices.add(1)
            me.vertices[-1].co = vco
    elif type == "sagittal":
        vidxs = range(nverts, nverts + 4)
        me.vertices.add(4)
        me.vertices[-4].co = v[0]
        me.vertices[-3].co = v[1]
        me.vertices[-2].co = v[2]
        me.vertices[-1].co = v[3]
        me.edges.add(4)
        me.edges[-4].vertices[0] = nverts
        me.edges[-4].vertices[1] = nverts + 1
        me.edges[-3].vertices[0] = nverts + 1
        me.edges[-3].vertices[1] = nverts + 2
        me.edges[-2].vertices[0] = nverts + 2
        me.edges[-2].vertices[1] = nverts + 3
        me.edges[-1].vertices[0] = nverts + 3
        me.edges[-1].vertices[1] = nverts
        me.polygons.add(1)
        me.polygons[-1].vertices[0] = nverts
        me.polygons[-1].vertices[1] = nverts + 1
        me.polygons[-1].vertices[2] = nverts + 2
        me.polygons[-1].vertices[3] = nverts + 3
    elif type == "coronal":
        pass
    elif type == "axial":
        pass

    vg = ob.vertex_groups.new(type)
    vg.add(vidxs, 1.0, "REPLACE")

    return me


def add_tract_to_collection(name, fpath, sformfile,
                            nsamples, weed_tract, interpolate_streamlines):
    """Add tract to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb
    nb.objecttype = 'tracts'

    tract = nb.tracts.add()

    tract.name = name
    tract.filepath = fpath
    tract.sformfile = sformfile
    tract.nstreamlines = nsamples
    tract.tract_weeded = weed_tract
    tract.streamlines_interpolated = interpolate_streamlines

    nb.index_tracts = (len(nb.tracts)-1)

    return tract

def add_surface_to_collection(name, fpath, sformfile):
    """Add surface to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb
    nb.objecttype = 'surfaces'

    surface = nb.surfaces.add()

    surface.name = name
    surface.filepath = fpath
    surface.sformfile = sformfile

    nb.index_surfaces = (len(nb.surfaces)-1)

    return surface

def add_voxelvolume_to_collection(name, fpath, sformfile, datarange, dims, texdir=""):
    """Add voxelvolume to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb
    nb.objecttype = 'voxelvolumes'

    vvol = nb.voxelvolumes.add()

    vvol.name = name
    vvol.filepath = fpath
    vvol.range = datarange
    vvol.sformfile = sformfile
    vvol.dimensions = dims
    vvol.texdir = texdir

    nb.index_voxelvolumes = (len(nb.voxelvolumes)-1)

    return vvol

def add_scalargroup_to_collection(name, fpath, scalarrange=[0, 1],
                                  dimensions=[0, 0, 0, 0], texdir=""):
    """Add scalargroup to the NeuroBlender collection."""

    nb_ob = nb_ut.active_nb_object()[0]

    scn = bpy.context.scene
    nb = scn.nb
    nb.overlaytype = 'scalargroups'

    scalargroup = nb_ob.scalargroups.add()

    scalargroup.name = name
    scalargroup.filepath = fpath
    scalargroup.range = scalarrange
    scalargroup.dimensions = dimensions
    scalargroup.texdir = texdir

    nb_ob.index_scalargroups = (len(nb_ob.scalargroups)-1)

    return scalargroup

def add_scalar_to_collection(scalargroup, name, fpath, scalarrange, matname="", texname="", tex_idx=0):
    """Add scalar to the NeuroBlender collection."""

    nb_ob = nb_ut.active_nb_object()[0]

    scn = bpy.context.scene
    nb = scn.nb

    if scalargroup:
        nb.overlaytype = 'scalargroups'
        par = scalargroup
    else:
        nb.overlaytype = 'scalars'
        par = nb_ob

    scalar = par.scalars.add()

    scalar.name = name
    scalar.filepath = fpath
    scalar.range = scalarrange
    scalar.matname = matname
    scalar.texname = texname
    scalar.tex_idx = tex_idx

    par.index_scalars = (len(par.scalars)-1)

    return scalar

def add_labelgroup_to_collection(name, fpath,
                                 dimensions=[0, 0, 0, 0], texdir=""):
    """Add labelgroup to the NeuroBlender collection."""

    nb_ob = nb_ut.active_nb_object()[0]

    scn = bpy.context.scene
    nb = scn.nb
    nb.overlaytype = 'labelgroups'

    labelgroup = nb_ob.labelgroups.add()

    labelgroup.name = name
    labelgroup.filepath = fpath
    labelgroup.dimensions = dimensions
    labelgroup.texdir = texdir

    nb_ob.index_labelgroups = (len(nb_ob.labelgroups)-1)

    return labelgroup


def add_label_to_collection(labelgroup, name, value, colour):
    """Add label to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb
    nb.overlaytype = 'labelgroups'

    label = labelgroup.labels.add()

    label.name = name
    label.value = value
    label.colour = colour

    labelgroup.index_labels = (len(labelgroup.labels)-1)

    return label

def add_bordergroup_to_collection(name, fpath):
    """Add bordergroup to the NeuroBlender collection."""

    nb_ob = nb_ut.active_nb_object()[0]

    scn = bpy.context.scene
    nb = scn.nb
    nb.overlaytype = 'bordergroups'

    bordergroup = nb_ob.bordergroups.add()

    bordergroup.name = name
    bordergroup.filepath = fpath

    nb_ob.index_bordergroups = (len(nb_ob.bordergroups)-1)

    return bordergroup


def add_border_to_collection(name, bordergroup, colour):
    """Add border to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb
    nb.overlaytype = 'bordergroups'

    border = bordergroup.borders.add()

    border.name = name
    border.group = bordergroup.name
    border.colour = colour

    bordergroup.index_borders = (len(bordergroup.borders)-1)

    return border


def add_light_to_collection(name, preset=None):
    """Add animation to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb
    if preset is None:
        preset = nb.presets[nb.index_presets]

    light = preset.lights.add()

    light.name = name

    preset.index_lights = (len(preset.lights)-1)

    return light


def add_animation_to_collection(name, preset=None, is_rendered=True):
    """Add animation to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb
    if preset is None:
        preset = nb.presets[nb.index_presets]

    animation = preset.animations.add()

    animation.name = name
    animation.is_rendered = is_rendered

    preset.index_animations = (len(preset.animations)-1)

    return animation


def add_campath_to_collection(name):
    """Add animation to the NeuroBlender collection."""

    scn = bpy.context.scene
    nb = scn.nb

    campath = nb.campaths.add()

    campath.name = name

    nb.index_campaths = (len(nb.campaths)-1)

    return campath


# ========================================================================== #
# reading tract files
# ========================================================================== #


def read_streamlines_npy(tckfile):
    """Read a [Npointsx3] streamline from a *.npy file."""

    streamline = np.load(tckfile)

    return [streamline]


def read_streamlines_npz(tckfile):
    """Return all streamlines from a *.npz file.

    e.g. from 'np.savez_compressed(outfile, streamlines0=streamlines0, ..=..)'
    NOTE: This doesn't work for .npz pickled in Python 2.x,!! ==>
    Unicode unpickling incompatibility
    """

    # TODO: proper checks and error handling
    # TODO: multitract npz
    streamlines = []
    npzfile = np.load(tckfile)
    k = npzfile.files[0]
    if len(npzfile.files) == 0:
        print('No files in archive.')
    elif len(npzfile.files) == 1:      # single tract / streamline
        if len(npzfile[k][0][0]) == 3:    # k contains a list of Nx3 arrays
            streamlines = npzfile[k]
        else:                             # k contains a single Nx3 array
            streamlines.append(npzfile[k])
    elif len(npzfile.files) > 1:       # multiple tracts / streamlines
        if len(npzfile[k][0][0]) == 3:    # k contains a list of Nx3 arrays
            print('multi-tract npz not supported yet.')
        else:                             # each k contains a single Nx3 array
            for k in npzfile:
                streamlines.append(npzfile[k])

    return streamlines


def read_streamlines_dpy(dpyfile):
    """Return all streamlines in a dipy .dpy tract file (uses dipy)."""

    if nb_ut.validate_dipy('.trk'):
        dpr = Dpy(dpyfile, 'r')  # FIXME
        streamlines = dpr.read_tracks()
        dpr.close()

    return streamlines


def read_streamlines_trk(trkfile):
    """Return all streamlines in a Trackvis .trk tract file (uses nibabel)."""

    nib = nb_ut.validate_nibabel('.trk')
    if bpy.context.scene.nb.nibabel_valid:
        tv = nib.trackvis
        streams, hdr = tv.read(trkfile)
        streamlines = [s[0] for s in streams]

        return streamlines


def read_streamlines_tck(tckfile):
    """Return all streamlines in a MRtrix .tck tract file."""

    datatype, offset = read_mrtrix_header(tckfile)
    streamlinevector = read_mrtrix_tracks(tckfile, datatype, offset)
    streamlines = unpack_mrtrix_streamlines(streamlinevector)

    return streamlines


def read_streamlines_vtk(vtkfile):
    """Return all streamlines in a (MRtrix) .vtk tract file."""

    points, tracts, scalars, cscalars, lut = import_vtk_polylines(vtkfile)
    streamlines = unpack_vtk_polylines(points, tracts)

    return streamlines


def read_streamlines_Bfloat(fpath):
    """Return all streamlines in a Camino .Bfloat tract file."""

    streamlines = read_camino_streamlines(fpath, '>f4')

    return streamlines


def read_streamlines_bfloat(fpath):
    """Return all streamlines in a Camino .bfloat tract file."""

    streamlines = read_camino_streamlines(fpath, '<f4')

    return streamlines


def read_streamlines_Bdouble(fpath):
    """Return all streamlines in a Camino .Bdouble tract file."""

    streamlines = read_camino_streamlines(fpath, '>f8')

    return streamlines


def read_streamlines_bdouble(fpath):
    """Return all streamlines in a Camino .bdouble tract file."""

    streamlines = read_camino_streamlines(fpath, '<f8')

    return streamlines


def read_camino_streamlines(fpath, camdtype):
    """Return all streamlines in a Camino tract file."""

    streamlinevec = np.fromfile(fpath, dtype=camdtype)

    streamlines = []
    offset = 0
    while offset < len(streamlinevec):
        npoints = streamlinevec[offset]
        ntokens = npoints * 3
        offset += 2
        streamline = streamlinevec[offset:ntokens + offset]
        streamline = np.reshape(streamline, (npoints, 3))
        offset += ntokens
        streamlines.append(streamline)

    return streamlines


def unpack_camino_streamline(streamlinevec):
    """Extract the first streamline from the streamlinevector.

    streamlinevector contains N streamlines of M points:
    each streamline: [length seedindex M*xyz]
    # DEPRECATED: deletion is incredibly sloooooooowwww
    """

    streamline_npoints = streamlinevec[0]
    streamline_end = streamline_npoints * 3 + 2
    streamline = streamlinevec[2:streamline_end]
    streamline = np.reshape(streamline, (streamline_npoints, 3))
    indices = range(0, streamline_end.astype(int))
    streamlinevec = np.delete(streamlinevec, indices, 0)

    return streamline, streamlinevec


def import_vtk_polylines(vtkfile):
    """Read points and polylines from file"""

    with open(vtkfile) as f:
        scalars = cscalars = lut = None
        read_points = 0
        read_tracts = 0
        read_scalars = 0
        read_cscalars = 0
        read_lut = 0
        for line in f:
            tokens = line.rstrip("\n").split(' ')

            if tokens[0] == "POINTS":
                read_points = 1
                npoints = int(tokens[1])
                points = []
            elif read_points == 1 and len(points) < npoints*3:
                for token in tokens:
                    if token:
                        points.append(float(token))

            elif tokens[0] == "LINES":
                read_tracts = 1
                ntracts = int(tokens[1])
                tracts = []
            elif read_tracts == 1 and len(tracts) < ntracts:
                tract = []
                for token in tokens[1:]:
                    if token:
                        tract.append(int(token))
                tracts.append(tract)

            elif tokens[0] == "POINT_DATA":
                nattr = int(tokens[1])
            elif tokens[0] == "SCALARS":
                read_scalars = 1
                scalar_name = tokens[1]
                scalar_dtype = tokens[2]
                scalar_ncomp = tokens[3]
                scalars = []
            elif read_scalars == 1 and len(scalars) < nattr:
                scalar = []
                for token in tokens:
                    if token:
                        scalar.append(float(token))  # NOTE: floats assumed
                scalars.append(scalar)

            elif tokens[0] == "COLOR_SCALARS":
                read_cscalars = 1
                cscalar_name = tokens[1]
                cscalar_ncomp = tokens[2]
                cscalars = []
            elif read_cscalars == 1 and len(cscalars) < nattr:
                cscalar = []
                for token in tokens:
                    if token:
                        cscalar.append(float(token))
                cscalars.append(cscalar)

            elif tokens[0] == "LOOKUP_TABLE":
                read_lut = 1
                lut_name = tokens[1]
                lut_size = tokens[2]
                lut = []
            elif read_lut == 1 and len(lut) < lut_size:
                entry = []
                for token in tokens:
                    if token:
                        entry.append(float(token))
                lut.append(entry)

            elif tokens[0] == '':
                pass
            else:
                pass

        points = np.reshape(np.array(points), (npoints, 3))

    return points, tracts, scalars, cscalars, lut

# TODO SCALARS
# SCALARS dataName dataType numComp
# LOOKUP_TABLE tableName
# s0
# s1
# TODO COLOR_SCALARS
# POINT_DATA 754156
# COLOR_SCALARS scalars 4
# 0 1 0.988235 1 0 1 0.988235 1 0 1 0.996078 1
# 0 0.980392 1 1 0 0.956863 1 1
# 0 0.854902 1 1 0 0.560784 1 1


def unpack_vtk_polylines(points, tracts):
    """Convert indexed polylines to coordinate lists."""

    streamlines = []
    for tract in tracts:
        streamline = []
        for point in tract:
            streamline.append(points[point])
        stream = np.reshape(streamline, (len(streamline), 3))
        streamlines.append(stream)

    return streamlines


def read_mrtrix_header(tckfile):
    """Return the datatype and offset for a MRtrix .tck tract file."""

    with open(tckfile, 'rb') as f:
        data = f.read()
        lines = data.split(b'\n')
        for line in lines:
            if line == b'END':
                break
            else:
                tokens = line.decode("utf-8").rstrip("\n").split(' ')
                if tokens[0] == 'datatype:':
                    datatype = tokens[1]
                elif tokens[0] == 'file:':
                    offset = int(tokens[2])

        return datatype, offset


def read_mrtrix_tracks(tckfile, datatype, offset):
    """Return the data from a MRtrix .tck tract file."""

    f = open(tckfile, "rb")
    f.seek(offset)
    if datatype.startswith('Float32'):
        ptype = 'f4'
    if datatype.endswith('BE'):
        ptype = '>' + ptype
    elif datatype.endswith('LE'):
        ptype = '<' + ptype
    streamlinevector = np.fromfile(f, dtype=ptype)

    return streamlinevector


def unpack_mrtrix_streamlines(streamlinevector):
    """Extract the streamlines from the streamlinevector.

    streamlinevector contains N streamlines
    separated by 'nan' triplets and ended with an 'inf' triplet
    """

    streamlines = []
    streamlinevector = np.reshape(streamlinevector, [-1, 3])
    idxs_nan = np.where(np.isnan(streamlinevector))[0][0::3]
    i = 0
    for j in idxs_nan:
        streamlines.append(streamlinevector[i:j, :])
        i = j + 1

    return streamlines


# ========================================================================== #
# creating streamlines
# ========================================================================== #


def make_polyline(objname, curvename, cList):
    """Create a 3D curve from a list of points."""

    curvedata = bpy.data.curves.new(name=curvename, type='CURVE')
    curvedata.dimensions = '3D'

    objectdata = bpy.data.objects.new(objname, curvedata)
    objectdata.location = (0, 0, 0)
    bpy.context.scene.objects.link(objectdata)

    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(cList)-1)
    for num in range(len(cList)):
        x, y, z = cList[num]
        polyline.points[num].co = (x, y, z, 1)

    return objectdata


def make_polyline_ob(curvedata, cList):
    """Create a 3D curve from a list of points."""

    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(cList)-1)
    for num in range(len(cList)):
        x, y, z = cList[num]
        polyline.points[num].co = (x, y, z, 1)
    polyline.order_u = len(polyline.points)-1
    polyline.use_endpoint_u = True


def make_polyline_ob_vi(curvedata, ob, vi_list):
    """Create a 3D curve from a list of vertex indices."""

    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(vi_list)-1)
    for i, vi in enumerate(vi_list):
        polyline.points[i].co[:3] = ob.data.vertices[vi].co
    polyline.order_u = len(polyline.points)-1
    polyline.use_endpoint_u = True
    polyline.use_cyclic_u = True


# ========================================================================== #
# reading surface files
# ========================================================================== #


def read_surfaces_obj(fpath, name, sformfile):
    """Import a surface from a .obj file."""
    # TODO: multiple objects import

    # need split_mode='OFF' for loading scalars onto the correct vertices
    bpy.ops.import_scene.obj(filepath=fpath,
                             axis_forward='Y', axis_up='Z',
                             split_mode='OFF')
    ob = bpy.context.selected_objects[0]
    ob.name = name
    affine = read_affine_matrix(sformfile)

    return [(ob, affine, sformfile)]


def read_surfaces_stl(fpath, name, sformfile):
    """Import a surface from a .stl file."""
    # TODO: multiple objects import

    bpy.ops.import_mesh.stl(filepath=fpath,
                            axis_forward='Y', axis_up='Z')
    ob = bpy.context.selected_objects[0]
    ob.name = name
    affine = read_affine_matrix(sformfile)

    return [(ob, affine, sformfile)]


def read_surfaces_gii(fpath, name, sformfile):
    """Import a surface from a .gii file."""
    # TODO: multiple objects import

    scn = bpy.context.scene
    nb = scn.nb

    nib = nb_ut.validate_nibabel('.gifti')

    gio = nib.gifti.giftiio
    img = gio.read(fpath)
    verts = [tuple(vert) for vert in img.darrays[0].data]
    faces = [tuple(face) for face in img.darrays[1].data]
    xform = img.darrays[0].coordsys.xform
    if len(xform) == 16:
        xform = np.reshape(xform, [4, 4])
    affine = Matrix(xform)
    sformfile = fpath

    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.objects.link(ob)

    return [(ob, affine, sformfile)]


def read_surfaces_fs(fpath, name, sformfile):
    """Import a surface from a FreeSurfer file."""

    scn = bpy.context.scene
    nb = scn.nb

    nib = nb_ut.validate_nibabel('.gifti')

    fsio = nib.freesurfer.io
    verts, faces = fsio.read_geometry(fpath)
    verts = [tuple(vert) for vert in verts]
    faces = [tuple(face) for face in faces]
    affine = Matrix()

    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.objects.link(ob)

    return [(ob, affine, sformfile)]


read_surfaces_white = read_surfaces_fs
read_surfaces_pial = read_surfaces_fs
read_surfaces_inflated = read_surfaces_fs
read_surfaces_sphere = read_surfaces_fs
read_surfaces_orig = read_surfaces_fs


def read_surfaces_blend(fpath, name, sformfile):
    """Import a surface from a .blend file."""

    with bpy.data.libraries.load(fpath) as (data_from, data_to):
        data_to.objects = data_from.objects

    surfaces = []
    for ob in data_to.objects:
        if ob is not None:
            bpy.context.scene.objects.link(ob)
            surfaces.append((ob, ob.matrix_world, ''))

    return surfaces


# ========================================================================== #
# geometry spatial transformations
# ========================================================================== #


def read_affine_matrix(filepath, fieldname='stack'):
    """Get the affine transformation matrix from the nifti or textfile."""

    scn = bpy.context.scene
    nb = scn.nb

    if not filepath:
        affine = Matrix()
    elif (filepath.endswith('.nii') | filepath.endswith('.nii.gz')):
        nib = nb_ut.validate_nibabel('nifti')
        if nb.nibabel_valid:
            affine = nib.load(filepath).header.get_sform()
    elif filepath.endswith('.gii'):
        nib = nb_ut.validate_nibabel('gifti')
        if nb.nibabel_valid:
            gio = nib.gifti.giftiio
            img = gio.read(filepath)
            xform = img.darrays[0].coordsys.xform
            if len(xform) == 16:
                xform = np.reshape(xform, [4, 4])
            affine = Matrix(xform)
    elif filepath.endswith('.h5'):
        affine = h5_affine(filepath, fieldname)
    elif filepath.endswith('.npy'):
        affine = np.load(filepath)
    else:
        affine = np.loadtxt(filepath)
        # TODO: check if matrix if valid
#         if affine.shape is not (4,4):
#             return {'cannot calculate transform: \
#                     invalid affine transformation matrix'}

    return Matrix(affine)


def h5_affine(fpath, fieldname):
    """Read an 'affine' matrix from h5 element sizes."""

    try:
        import h5py
    except ImportError:
        raise  # TODO: error to indicate how to set up h5py
    else:
#         h5_path = fpath.split('.h5')
#         f = h5py.File(h5_fpath[0] + '.h5', 'r')
        f = h5py.File(fpath, 'r')
        in2out = h5_in2out(f[fieldname])

        affine = [[1, 0, 0, 0],
                  [0, 1, 0, 0],
                  [0, 0, 1, 0],
                  [0, 0, 0, 1]]
        try:
            element_size_um = [f[fieldname].attrs['element_size_um'][i]
                               for i in in2out]
        except:
            pass
        else:
            affine[0][0] = element_size_um[0]
            affine[1][1] = element_size_um[1]
            affine[2][2] = element_size_um[2]

        return affine
