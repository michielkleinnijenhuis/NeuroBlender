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


"""The NeuroBlender imports (voxelvolumes) module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements importing voxelvolumes into NeuroBlender.
"""


import os
from glob import glob
import numpy as np
from mathutils import Vector, Matrix

import bpy
from bpy.types import (Operator,
                       OperatorFileListElement)
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       IntProperty)
from bpy_extras.io_utils import ImportHelper

from .. import (materials as nb_ma,
                renderpresets as nb_rp,
                utils as nb_ut)
from . import import_tracts as nb_it

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

    self.has_valid_texdir = nb_ut.validate_texdir(self.texdir,
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
    except (OSError, TypeError) as e:
        items = [("dataset", "no dataset available", str(e), 0)]
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
        # NOTE: multiline comment """ """ not working here
        default="*.nii;*.nii.gz;*.img;*.hdr;" +
                "*.h5;" +
                "*.png;*.jpg;*.tif;*.tiff;")

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

    import_objects = nb_it.ImportTracts.import_objects

    def execute(self, context):

        importtype = "voxelvolumes"
        importfun = self.import_voxelvolume
        impdict = {"is_overlay": self.is_overlay,
                   "is_label": self.is_label,
                   "parentpath": self.parentpath,
                   "texdir": self.texdir,
                   "texformat": self.texformat,
                   "overwrite": self.overwrite,
                   "dataset": self.dataset,
                   "vol_idx": self.vol_idx}
        beaudict = {}

        self.import_objects(importfun, importtype, impdict, beaudict)

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

    def import_voxelvolume(self, fpath, name, sformfile="", texdict={
            "is_overlay": False, "is_label": False,
            "parentpath": "", "sformfile": "",
            "texdir": "", "texformat": "IMAGE_SEQUENCE",
            "overwrite": False, "dataset": 'stack',
            "vol_idx": -1}):
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
            nb_ut.force_save(nb.settingprops.projectdir)
        abstexdir = bpy.path.abspath(texdir)
        nb_ut.mkdir_p(abstexdir)

        outcome = "failed"
        ext = os.path.splitext(fpath)[1]

        texdict = self.load_texdir(texdict)

        item = self.add_to_collections(texdict)

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
                if nb.settingprops.texmethod == 4:
                    tex = nb_ma.get_voxtex(mat, texdict, volname, scalar)

        # create the voxelvolume object
#         ob = voxelvolume_object_bool(name, texdict['dims'],
#                                      texdict['affine'])
        ob, sbox = self.voxelvolume_object_slicebox(item, texdict)

        # single texture slot for simple switching
        texslot = mat.texture_slots.add()
        texslot.texture = tex
        texslot.use_map_density = True
        texslot.texture_coords = 'ORCO'
        texslot.use_map_emission = True

        self.voxelvolume_rendertype_driver(mat, item)

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

    def load_texdir(self, texdict):
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
            texdict = self.create_texdir(texdict)

        texdict['loaded'] = True

        return texdict

    def create_texdir(self, texdict):
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

            texdict = self.prep_nifti(texdict)
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
                              [self.image_sequence_length(fpath)] + [1]
            texdict['texformat'] = "IMAGE_SEQUENCE"
            texdict['datarange'] = [0, 1]
            texdict['labels'] = None
            # TODO: figure out labels and datarange

        texdict['affine'] = nb_ut.read_affine_matrix(sformfile, fieldname)

        # save the essentials to the voltex directory
        for pf in ('affine', 'dims', 'datarange', 'labels'):
            np.save(os.path.join(abstexdir, pf), np.array(texdict[pf]))

        return texdict

    def prep_nifti(self, texdict):
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
                in2out = nb_ut.h5_in2out(f[fieldname])
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

        data, datarange = nb_ut.normalize_data(data)

        imdir = os.path.join(bpy.path.abspath(texdir), texformat)
        absimdir = bpy.path.abspath(imdir)
        nb_ut.mkdir_p(absimdir)

        data = np.transpose(data)
        fun = eval("self.write_to_%s" % texformat.lower())
        img = fun(absimdir, data, dims)

        texdict.update({'img': img,
                        'dims': dims,
                        'datarange': datarange,
                        'labels': labels})

        return texdict

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
                      f[len(filename_nodigits):-len(ext)
                        if ext else -1].isdigit()]
        n_images = len(image_list)

        return n_images

    @staticmethod
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

    def voxelvolume_object_bool(self, name, dims, affine):
        """"""

        # the voxelvolumebox
        ob = self.voxelvolume_box_ob(dims, "SliceBox")
        ob.name = name
        ob.matrix_world = affine
        # an empty to hold the sliceboxes
        empty = bpy.data.objects.new(ob.name+"SliceBox", None)
        empty.parent = ob
        empty.location = (0, 0, 0)
        bpy.context.scene.objects.link(empty)
        # create sliceboxes and modifiers
        for direc in 'xyz':
            boolmod = ob.modifiers.new("bool_%s" % direc, 'BOOLEAN')
            boolmod.solver = 'CARVE'
            boolmod.operation = 'INTERSECT'
            sb = self.voxelvolume_box_ob(dims, "SliceBox")
            sb.name = direc
            sb.parent = empty
            boolmod.object = sb
            # TODO: no need for vg

        return ob

    def voxelvolume_object_slicebox(self, item, texdict):
        """"""

        scn = bpy.context.scene

        slices = False
        me = bpy.data.meshes.new(texdict["name"])
        ob = bpy.data.objects.new(texdict["name"], me)
        bpy.context.scene.objects.link(ob)
        ob1 = self.voxelvolume_box_ob(texdict["dims"], "Bounds")
        ob2 = self.voxelvolume_box_ob(texdict["dims"], "SliceBox")

        ob.select = True
        scn.objects.active = ob
        obs = [ob, ob1, ob2]
        ctx = bpy.context.copy()
        ctx['active_object'] = ob
        ctx['selected_objects'] = obs
        ctx['selected_editable_bases'] = [scn.object_bases[ob.name]
                                          for ob in obs]
        bpy.ops.object.join(ctx)

        scn.objects.active = ob
        ob.select = True

        mat = Matrix() if texdict["is_overlay"] else Matrix(texdict["affine"])
        ob.matrix_world = mat

        slicebox = self.voxelvolume_cutout(ob)

        for idx in range(0, 3):
            self.voxelvolume_slice_drivers_volume(item, slicebox,
                                                  idx, "scale")
            self.voxelvolume_slice_drivers_volume(item, slicebox,
                                                  idx, "location")
            self.voxelvolume_slice_drivers_volume(item, slicebox,
                                                  idx, "rotation_euler")

        return ob, slicebox

    def voxelvolume_cutout(self, ob):
        """"""

        scn = bpy.context.scene

        bb_min, bb_max = self.find_bbox_coordinates([ob])

        for slicetype in ["SliceBox"]:  # , "sagittal", "coronal", "axial"

            empty = bpy.data.objects.new(ob.name+slicetype, None)
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
                if slicetype == "SliceBox":
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
                elif slicetype == "sagittal":
                    con.min_x = 0
                    con.max_x = dims[0]
                    con.min_y = 0
                    con.max_y = 0
                    con.min_z = 0
                    con.max_z = 0
                elif slicetype == "coronal":
                    con.min_x = 0
                    con.max_x = 0
                    con.min_y = 0
                    con.max_y = dims[1]
                    con.min_z = 0
                    con.max_z = 0
                elif slicetype == "axial":
                    con.min_x = 0
                    con.max_x = 0
                    con.min_y = 0
                    con.max_y = 0
                    con.min_z = 0
                    con.max_z = dims[2]

            scn.objects.active = ob
            bpy.ops.object.modifier_add(type='HOOK')
            hook = ob.modifiers["Hook"]
            hook.name = slicetype
            hook.object = empty
            hook.vertex_group = slicetype
            hook.falloff_type = 'NONE'

        return empty

    @staticmethod
    def voxelvolume_slice_drivers_volume(item, slicebox,
                                         index, prop, relative=True):

        scn = bpy.context.scene
        nb = scn.nb

        driver = slicebox.driver_add(prop, index).driver
        driver.type = 'SCRIPTED'

        # dimension of the voxelvolume
        data_path = "%s.dimensions[%d]" % (item.path_from_id(), index)
        nb_rp.create_var(driver, "dim",
                         'SINGLE_PROP', 'SCENE',
                         scn, data_path)
        # relative slicethickness
        data_path = "%s.slicethickness[%d]" % (item.path_from_id(), index)
        nb_rp.create_var(driver, "slc_th",
                         'SINGLE_PROP', 'SCENE',
                         scn, data_path)
        # relative sliceposition
        data_path = "%s.sliceposition[%d]" % (item.path_from_id(), index)
        nb_rp.create_var(driver, "slc_pos",
                         'SINGLE_PROP', 'SCENE',
                         scn, data_path)
        # sliceangle
        data_path = "%s.sliceangle[%d]" % (item.path_from_id(), index)
        nb_rp.create_var(driver, "slc_angle",
                         'SINGLE_PROP', 'SCENE',
                         scn, data_path)

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

    @staticmethod
    def voxelvolume_slice_drivers_surface(item, tex, index, prop):

        scn = bpy.context.scene
        nb = scn.nb

        driver = tex.driver_add(prop, index).driver
        driver.type = 'SCRIPTED'

        data_path = "%s.slicethickness[%d]" % (item.path_from_id(), index)
        nb_rp.create_var(driver, "slc_th",
                         'SINGLE_PROP', 'SCENE',
                         scn, data_path)
        if prop == "scale":
            # relative slicethickness
            driver.expression = "slc_th"
        elif prop == "offset":
            # relative sliceposition
            data_path = "%s.sliceposition[%d]" % (item.path_from_id(), index)
            nb_rp.create_var(driver, "slc_pos",
                             'SINGLE_PROP', 'SCENE',
                             scn, data_path)
            driver.expression = "2*(1/slc_th-1) * slc_pos - (1/slc_th-1)"

    def voxelvolume_rendertype_driver(self, mat, item):

        scn = bpy.context.scene
        nb = scn.nb

        driver = mat.driver_add("type", -1).driver
        driver.type = 'AVERAGE'
        vv_idx = nb.index_voxelvolumes

        data_path = "%s.rendertype" % item.path_from_id()
        nb_rp.create_var(driver, "type",
                         'SINGLE_PROP', 'SCENE',
                         scn, data_path)

    @staticmethod
    def voxelvolume_slice_drivers_yoke(parent, child, prop, index):

        scn = bpy.context.scene
        nb = scn.nb

        driver = child.driver_add(prop, index).driver
        driver.type = 'SCRIPTED'
        data_path = "%s.%s[%d]" % (parent.path_from_id(), prop, index)
        nb_rp.create_var(driver, "var", 'SINGLE_PROP', 'SCENE', scn, data_path)
        driver.expression = "var"

    @staticmethod
    def find_bbox_coordinates(obs):
        """Find the extreme dimensions in the geometry."""

        bb_world = [ob.matrix_world * Vector(bbco)
                    for ob in obs for bbco in ob.bound_box]
        bb_min = np.amin(np.array(bb_world), 0)
        bb_max = np.amax(np.array(bb_world), 0)

        return bb_min, bb_max

    @staticmethod
    def voxelvolume_box_ob(dims=[256, 256, 256], slicetype="verts"):
        """"""

        me = bpy.data.meshes.new(slicetype)
        ob = bpy.data.objects.new(slicetype, me)
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
        if slicetype == "SliceBox":
            vidxs = range(nverts, nverts + 8)
            faces = [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5),
                     (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
        elif slicetype == "Bounds":
            vidxs = range(nverts, nverts + 8)
            faces = []
        elif slicetype == "sagittal":
            vidxs = range(nverts, nverts + 4)
            v = [v[0], v[3], v[7], v[4]]
            faces = [(0, 1, 2, 3)]
        elif slicetype == "coronal":
            vidxs = range(nverts, nverts + 4)
            v = [v[0], v[1], v[5], v[4]]
            faces = [(0, 1, 2, 3)]
        elif slicetype == "axial":
            vidxs = range(nverts, nverts + 4)
            v = [v[0], v[1], v[2], v[3]]
            faces = [(0, 1, 2, 3)]

        me.from_pydata(v, [], faces)
        me.update(calc_edges=True)

        vg = ob.vertex_groups.new(slicetype)
        vg.add(vidxs, 1.0, "REPLACE")

        return ob

    @staticmethod
    def voxelvolume_box(ob=None, dims=[256, 256, 256], slicetype="verts"):
        """Create a box with the dimensions of the voxelvolume."""

        if ob is None:
            me = bpy.data.meshes.new(slicetype)
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

        if slicetype == "box":
            vidxs = range(nverts, nverts + 8)
            me.from_pydata(v, [], faces)
            me.update(calc_edges=True)
        elif slicetype == "bounds":
            vidxs = range(nverts, nverts + 8)
            for vco in v:
                me.vertices.add(1)
                me.vertices[-1].co = vco
        elif slicetype == "sagittal":
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
        elif slicetype == "coronal":
            pass
        elif slicetype == "axial":
            pass

        vg = ob.vertex_groups.new(slicetype)
        vg.add(vidxs, 1.0, "REPLACE")

        return me

    @staticmethod
    def beautify_voxelvolumes(ob, argdict={}):
        """Particlise the voxelvolume."""

        info = ""  # TODO

        return info
