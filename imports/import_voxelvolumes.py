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
from mathutils import Matrix

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
                utils as nb_ut)


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
    except (OSError, TypeError, IndexError) as e:
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
    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial smoothing on surfaces",
        default=True)
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

        if self.has_valid_texdir and (not self.overwrite):

            info = self.import_voxelvolume(context, fpath='')
            self.report({'INFO'}, info)

        else:

            filenames = [f.name for f in self.files]
            if self.directory and (not filenames):
                filenames = os.listdir(self.directory)

            for f in filenames:
                fpath = os.path.join(self.directory, f)
                info = self.import_voxelvolume(context, fpath)
                self.report({'INFO'}, info)

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

    def import_voxelvolume(self, context, fpath):  # TODO: separate op?
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

        scn = context.scene
        nb = scn.nb

        ca = [bpy.data.objects,
              bpy.data.meshes,
              bpy.data.materials,
              bpy.data.textures]
        name = nb_ut.check_name(self.name, fpath, ca)


        if not self.sformfile:
            self.sformfile = fpath

        texdict = {"fpath": fpath,
                   "name": name,
                   "sformfile": self.sformfile,
                   "is_overlay": self.is_overlay,
                   "is_label": self.is_label,
                   "parentpath": self.parentpath,
                   "texdir": self.texdir,
                   "texformat": self.texformat,
                   "overwrite": self.overwrite,
                   "dataset": self.dataset,
                   "vol_idx": self.vol_idx}

        # prep texture directory
        if not bpy.data.is_saved:
            dpath = nb_ut.force_save(nb.settingprops.projectdir)
            if nb.settingprops.verbose:
                infostring = 'Blend-file had not been saved: saved file to {}'
                info = infostring.format(dpath)
                self.report({'INFO'}, info)
        abstexdir = bpy.path.abspath(self.texdir)
        nb_ut.mkdir_p(abstexdir)

        # TODO: error handling
#         outcome = "failed"
#         ext = os.path.splitext(fpath)[1]

        texdict, info_load = self.load_texdir(texdict)

        item = self.add_to_collections(texdict)

        tex = self.get_voxtex(context, texdict, 'vol0000', item)
        item.texname = tex.name

        if self.is_label:

            nb_ob = eval(self.parentpath)
            mat = bpy.data.materials[nb_ob.name]

            for volnr, label in enumerate(item.labels):
                pass  # TODO

        elif self.is_overlay:

            nb_ob = scn.path_resolve(self.parentpath)
            ob = bpy.data.objects[nb_ob.name]
            mat = bpy.data.materials[nb_ob.name]

            for scalar in item.scalars:
                volname = scalar.name[-7:]  # FIXME: this is not secure
                pfdict = {"IMAGE_SEQUENCE": os.path.join(volname, '0000.png'),
                          "STRIP": volname + '.png',
                          "8BIT_RAW": volname + '.raw_8bit'}
                scalarpath = os.path.join(self.texdir, self.texformat,
                                          pfdict[self.texformat])
                scalar.filepath = scalarpath
                scalar.matname = mat.name
                scalar.texname = tex.name
                if nb.settingprops.texmethod == 4:
                    tex = self.get_voxtex(context, texdict, volname, scalar)

            item.index_scalars = 0  # induce switch

        else:

            # create the voxelvolume object
            ob = self.voxelvolume_box_ob(name, texdict['dims'])
            ob.matrix_world = texdict['affine']

            mat = self.get_voxmat(name)
            nb_ma.set_materials(ob.data, mat)

            nb_ut.move_to_layer(ob, 2)
            scn.layers[2] = True

            group = bpy.data.groups.get("voxelvolumes") or \
                bpy.data.groups.new("voxelvolumes")
            group.objects.link(ob)

        self.add_tex_to_mat(mat, tex, 'OBJECT', ob)

        nb.settingprops.engine = 'BLENDER_RENDER'

        # force updates on voxelvolumes
        nb.index_voxelvolumes = nb.index_voxelvolumes
        if not self.is_overlay:
            item.rendertype = item.rendertype
            item.sformfile = item.sformfile

        info = "Voxelvolume import successful"
        if nb.settingprops.verbose:
            infostring = "{}\n"
            infostring += "name: '{}'\n"
            infostring += "path: '{}'\n"
            infostring += "transform: \n"
            infostring += "{}\n"
            infostring += "dimensions: [{:4d}, {:4d}, {:4d}, {:4d}]\n"
            infostring += "datarange: [{:.6f}, {:.6f}]\n"
            infostring += "{}"
            info = infostring.format(info, name, fpath,
                                     Matrix(texdict["affine"]),
                                     *texdict['dims'],
                                     *texdict['datarange'],
                                     info_load)

        return info

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
            texdict['sformfile'] = os.path.join(abstexdir, "affine.npy")

            texsource = "LOADED"

        except:

            texsource = "CREATED"
            texdict = self.create_texdir(texdict)

        if texdict['is_label']:
            vvoltype = 'label overlay'
        elif texdict['is_overlay']:
            vvoltype = 'scalar overlay'
        else:
            vvoltype = 'base volume'
        infostring = "texture: \n"
        infostring += "    {0} and imported as {3}\n"
        infostring += "    format: '{2}'\n"
        infostring += "    texture directory: '{1}'"
        info = infostring.format(texsource, abstexdir, texformat, vvoltype)

        texdict['loaded'] = True

        return texdict, info

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

    @staticmethod
    def prep_nifti(texdict):
        """Write data in a nifti file to a NeuroBlender volume texture.

        The nifti is read with nibabel with [z,y,x] layout, and is either
        written as an [x,y] PNG image sequence (datarange=[0,1]) or
        as an 8bit raw binary volume with [x,y,z] layout (datarange=[0,255]).
        Labelvolumes: negative labels are ignored (i.e. set to 0)
        """

        # TODO: make these available outside prep_nifti namespace
        def write_to_image_sequence(absimdir, data, dims):
            """Write data to a stack of slices."""

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
#                     img.save()
                    img.save_render(img.filepath_raw)

            scn.render.image_settings.file_format = ff
            scn.render.image_settings.color_mode = cm
            scn.render.image_settings.color_depth = cd

            return img

        def write_to_strip(absimdir, data, dims):
            """Write data to an image strip."""

            img = bpy.data.images.new("img",
                                      width=dims[2]*dims[1],
                                      height=dims[0])
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
            """Write data to a 8bit_raw volume."""

            data *= 255
            for volnr, vol in enumerate(data):
                filepath = os.path.join(absimdir, 'vol%04d.8bit_raw' % volnr)
                with open(filepath, "wb") as f:
                    f.write(bytes(vol.astype('uint8')))
                img = bpy.data.images.load(filepath)
                img.filepath = filepath

            return img

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
        fun = eval("write_to_%s" % texformat.lower())
        img = fun(absimdir, data, dims)

        texdict.update({'img': img,
                        'dims': dims,
                        'datarange': datarange,
                        'labels': labels})

        return texdict

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

    @staticmethod
    def voxelvolume_box_ob(name, dims=[256, 256, 256]):
        """Create a RAS-box of certain dimension."""

        me = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.objects.link(ob)

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

        faces = [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5),
                 (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]

        me.from_pydata(v, [], faces)
        me.update(calc_edges=True)

        return ob

    @staticmethod
    def get_voxmat(name):
        """Create a material to hold a voxel_data texture."""

        mat = bpy.data.materials.new(name)
        mat.type = "VOLUME"
        mat.use_transparency = True
        mat.alpha = 0.
        mat.volume.density = 0.
        mat.volume.reflection = 0.
        mat.use_shadeless = True
        mat.preview_render_type = 'CUBE'
        mat.use_fake_user = True

        return mat

    def get_voxtex(self, context, texdict, volname, item):
        """Create a voxel_data texture."""

        scn = context.scene

        img = texdict['img']
        dims = texdict['dims']
        texdir = texdict['texdir']
        texformat = texdict['texformat']
        is_overlay = texdict['is_overlay']
        is_label = texdict['is_label']

        tex = bpy.data.textures.new(item.name, 'VOXEL_DATA')
        tex.use_preview_alpha = True
        tex.use_color_ramp = True
        tex.use_fake_user = True
        if texformat == 'STRIP':  # TODO: this should be handled with cycles
            texformat = "IMAGE_SEQUENCE"
        tex.voxel_data.file_format = texformat
        tex.voxel_data.use_still_frame = True
        tex.voxel_data.still_frame = scn.frame_current
        tex.voxel_data.interpolation = 'TRILINEAR'  # 'NEREASTNEIGHBOR'

        if texformat == "IMAGE_SEQUENCE":
            texpath = os.path.join(texdir, texformat, volname, '0000.png')
            img = bpy.data.images.load(bpy.path.abspath(texpath))
            img.name = item.name
            img.source = 'SEQUENCE'
            img.colorspace_settings.name = 'Non-Color'  # TODO: check
            img.reload()
            tex.image_user.frame_duration = dims[2]
            tex.image_user.frame_start = 1
            tex.image_user.frame_offset = 0
            tex.image = img
        elif texformat == "8BIT_RAW":
            tex.voxel_data.filepath = bpy.path.abspath(img.filepath)
            tex.voxel_data.resolution = [int(dim) for dim in dims[:3]]

        if is_label:
            tex.voxel_data.interpolation = "NEREASTNEIGHBOR"
            if len(item.labels) < 33:
                self.generate_label_ramp(tex, item)
            else:  # too many labels: switching to continuous ramp
                item.colourmap_enum = "jet"
        elif is_overlay:
            item.colourmap_enum = "jet"
        else:
            item.colourmap_enum = "grey"

        return tex

    def add_tex_to_mat(self, mat, tex, texture_coords='ORCO', ob=None):
        """Add a texture to a material."""

        texslot = mat.texture_slots.add()
        texslot.texture = tex
        texslot.use_map_density = True
        texslot.texture_coords = texture_coords
        if texture_coords == 'OBJECT':
            texslot.object = ob
        texslot.use_map_emission = True

    @staticmethod
    def generate_label_ramp(tex, item):
        """Make a color ramp from a label collection."""

        cr = tex.color_ramp
        cr.interpolation = 'CONSTANT'
        cre = cr.elements
        maxlabel = max([label.value for label in item.labels])
        step = 1. / maxlabel
        offset = step / 2.
        cre[1].position = item.labels[0].value / maxlabel - offset
        cre[1].color = item.labels[0].colour
        for label in item.labels[1:]:
            pos = label.value / maxlabel - offset
            el = cre.new(pos)
            el.color = label.colour

    @staticmethod
    def beautify_voxelvolumes(ob, argdict={}):
        """Particlise the voxelvolume."""

        info = ""  # TODO

        return info
