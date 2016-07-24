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

import bpy

import os
import numpy as np
import mathutils
from random import sample
import tempfile
import random
import xml.etree.ElementTree

from . import tractblender_beautify as tb_beau
from . import tractblender_materials as tb_mat
from . import tractblender_utils as tb_utils

# ========================================================================== #
# brain data import functions
# ========================================================================== #


def import_objects(directory, files, importfun,
                   importtype, specname,
                   colourtype, colourpicker, transparency,
                   beautify, info=None):
    """Import streamlines or surfaces.

    Streamlines:
    This imports the streamlines found in the specified directory/files.
    Valid formats include:
    - .Bfloat (Camino big-endian floats; from 'track' command)
      http://camino.cs.ucl.ac.uk/index.php?n=Main.Fileformats
    - .vtk (vtk polydata (ASCII); e.g. from MRtrix's 'tracks2vtk' command)
      http://www.vtk.org/wp-content/uploads/2015/04/file-formats.pdf
    - .tck (MRtrix)
      http://jdtournier.github.io/mrtrix-0.2/appendix/mrtrix.html
    - .npy (2d numpy arrays [Npointsx3]; single streamline per file)
    - .npz (zipped archive of Nstreamlines .npy files)
      http://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.savez.html

    It joins the individual streamlines into one 'Curve' object.
    Tracts are scaled according to the 'scale' box.
    Beautify functions/modifiers are applied to the tract.

    Surfaces: TODO

    """

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)
        name = tb_utils.check_name(specname, fpath, bpy.data.objects)

        ob = importfun(fpath, name, info=info)

        tb_mat.materialise(ob, colourtype, colourpicker, transparency)

        if beautify:
            tb_beau.beautify_brain(ob, importtype)

        ob.select = True
        bpy.context.scene.objects.active = ob

    return {"FINISHED"}


def import_tract(fpath, name, sformfile="", info=None):
    """Import a tract object."""

    scn = bpy.context.scene
    tb = scn.tb

    weed_tract = info['weed_tract']
    interpolate_streamlines = info['interpolate_streamlines']

    if fpath.endswith('.vtk'):
        streamlines = read_vtk_streamlines(fpath)

    elif fpath.endswith('.Bfloat'):
        streamlines = read_camino_streamlines(fpath)

    elif fpath.endswith('.tck'):
        streamlines = read_mrtrix_streamlines(fpath)

    elif fpath.endswith('.trk'):
        streamlines = read_trackvis_streamlines(fpath)

    elif fpath.endswith('.npy'):
        streamlines = read_numpy_streamline(fpath)

    elif fpath.endswith('.npz'):
        streamlines = read_numpyz_streamlines(fpath)

    elif fpath.endswith('.dpy'):
        streamlines = read_dipy_streamline(fpath)

    else:
        print('file format not understood; please use default extensions')
        return

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
            if interpolate_streamlines < 1.:
                subsample_streamlines = int(1/interpolate_streamlines)
                streamline = streamline[1::subsample_streamlines, :]
#                 TODO: interpolation
#                 from scipy import interpolate
#                 x = interpolate.splprep(list(np.transpose(streamline)))
            make_polyline_ob(curve, streamline)

    # TODO: handle cases where transform info is included in tractfile
    affine = read_affine_matrix(sformfile)
    ob.matrix_world = affine

    tract = tb.tracts.add()
    tb.index_tracts = (len(tb.tracts)-1)
    tract.name = name
    tract.nstreamlines = nsamples
    tract.tract_weeded = weed_tract
    tract.streamlines_interpolated = interpolate_streamlines
    tract.sformfile = sformfile

    tb_utils.move_to_layer(ob, 0)
    scn.layers[0] = True

    return bpy.data.objects[name]


def import_surface(fpath, name, sformfile="", info=None):
    """Import a surface object."""
    # TODO: subsampling? (but has to be compatible with loading overlays)

    scn = bpy.context.scene
    tb = scn.tb

    if fpath.endswith('.obj'):
        # need split_mode='OFF' for loading scalars onto the correct vertices
        bpy.ops.import_scene.obj(filepath=fpath,
                                 axis_forward='Y', axis_up='Z',
                                 split_mode='OFF')
        ob = bpy.context.selected_objects[0]
        ob.name = name
        affine = read_affine_matrix(sformfile)

    elif fpath.endswith('.stl'):
        bpy.ops.import_mesh.stl(filepath=fpath,
                                axis_forward='Y', axis_up='Z')
        ob = bpy.context.selected_objects[0]
        ob.name = name
        affine = read_affine_matrix(sformfile)

    elif (fpath.endswith('.gii') |
          fpath.endswith('.white') |
          fpath.endswith('.pial') |
          fpath.endswith('.inflated')
          ):
        nib = tb_utils.validate_nibabel('.gifti')
        if tb.nibabel_valid:
            if (fpath.endswith('.gii')) | (fpath.endswith('.surf.gii')):
                gio = nib.gifti.giftiio
                img = gio.read(fpath)
                verts = [tuple(vert) for vert in img.darrays[0].data]
                faces = [tuple(face) for face in img.darrays[1].data]
                xform = img.darrays[0].coordsys.xform
                if len(xform) == 16:
                    xform = np.reshape(xform, [4, 4])
                affine = mathutils.Matrix(xform)
                sformfile = fpath
            elif (fpath.endswith('.white') |
                  fpath.endswith('.pial') |
                  fpath.endswith('.inflated')
                  ):
                fsio = nib.freesurfer.io
                verts, faces = fsio.read_geometry(fpath)
                verts = [tuple(vert) for vert in verts]
                faces = [tuple(face) for face in faces]
                affine = mathutils.Matrix()
            me = bpy.data.meshes.new(name)
            me.from_pydata(verts, [], faces)
            ob = bpy.data.objects.new(name, me)
            bpy.context.scene.objects.link(ob)
            bpy.context.scene.objects.active = ob
            ob.select = True
            if (fpath.endswith('.func.gii')) | (fpath.endswith('.shape.gii')):
                pass  # TODO: create nice overlays for functionals etc

        else:
            print('file format not understood; please use default extensions')
            return

    ob.matrix_world = affine

    surface = tb.surfaces.add()
    tb.index_surfaces = (len(tb.surfaces)-1)
    surface.name = name
    surface.sformfile = sformfile

    tb_utils.move_to_layer(ob, 1)
    scn.layers[1] = True

    return ob


def import_voxelvolume(directory, files, specname,
                       sformfile="", tb_ob=None, is_label=False):
    """Import a voxelvolume."""

    scn = bpy.context.scene
    tb = scn.tb

    is_overlay = tb_ob is not None

    scn.render.engine = "BLENDER_RENDER"

    fpath = os.path.join(directory, files[0])
    name = tb_utils.check_name(specname, fpath, bpy.data.meshes)

    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.objects.link(ob)

    matname = tb_mat.get_voxmatname(name)

    if (fpath.endswith('.nii') | fpath.endswith('.nii.gz')):
        file_format = "RAW_8BIT"  # "IMAGE_SEQUENCE"
        if file_format == "IMAGE_SEQUENCE":
            tmppath = tempfile.mkdtemp(prefix=matname, dir=bpy.app.tempdir)
        elif file_format == "RAW_8BIT":
            tmppath = tempfile.mkstemp(prefix=matname, dir=bpy.app.tempdir)[1]
        dims, datarange, labels, img = prep_nifti(fpath, tmppath,
                                                  is_label, file_format)
        if not is_overlay:
            sformfile = fpath
    elif (fpath.endswith('.png') |
          fpath.endswith('.jpg') |
          fpath.endswith('.tif') |
          fpath.endswith('.tiff')):
        file_format = "IMAGE_SEQUENCE"
        img = bpy.data.images.load(fpath)
        dims = [s for s in img.size] + [image_sequence_length(fpath)]
        # TODO: figure out labels and datarange
        labels = None

    else:
        print('file format not understood; please use default extensions')
        return

    if file_format == "IMAGE_SEQUENCE":
        img.name = matname
        img.source = 'SEQUENCE'
        img.reload()

    items = []
    if is_label:
        for label in labels:
            item = tb_ob.labels.add()
            item.name = name + "." + str(label).zfill(8)
            item.value = label
            item.colour = tb_mat.get_golden_angle_colour(label) + [1.]
            items.append(item)
        tb_ob.index_labels = (len(tb_ob.labels)-1)
    elif is_overlay:
        item = tb_ob.scalars.add()
        item.name = name
        item.range = datarange
        tb_ob.index_scalars = (len(tb_ob.scalars)-1)
        items.append(item)
    else:
        item = tb.voxelvolumes.add()
        tb.index_voxelvolume = (len(tb.voxelvolumes)-1)
        item.name = name
        item.sformfile = sformfile

    affine = read_affine_matrix(sformfile)
    ob.matrix_world = affine

    mat = tb_mat.get_voxmat(matname, img, dims, file_format,
                            is_overlay, is_label, items)
    tb_mat.set_materials(me, mat)

    voxelvolume_box(me, dims)

    tb_utils.move_to_layer(ob, 2)
    scn.layers[2] = True

    return ob


def voxelvolume_box(me, dims=[256, 256, 256]):
    """Create a box with the dimensions of the voxelvolume."""

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

    me.from_pydata(v, [], faces)
    me.update(calc_edges=True)


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


def normalize_data(data):
    """Normalize data between 0 and 1."""

    data = data.astype('float64')
    datamin = np.amin(data)
    datamax = np.amax(data)
    data -= datamin
    data *= 1/(datamax-datamin)

    return data, [datamin, datamax]


def prep_nifti(fpath, tmppath, is_label=False, file_format="RAW_8BIT"):
    """Write data in a nifti file to a temp directory.

    The nifti is read with nibabel with [z,y,x] layout, and is either
    written as an [x,y] PNG image sequence (datarange=[0,1]) or
    as an 8bit raw binary volume with [x,y,z] layout (datarange=[0,255]).
    Labelvolumes: negative labels are ignored (i.e. set to 0)
    Only 3D volumes are handled.
    TODO: check which colorspace is expected of the data
    ...and convert here accordingly
    """

    scn = bpy.context.scene
    tb = scn.tb

    nib = tb_utils.validate_nibabel('nifti')
    if tb.nibabel_valid:

        nii = nib.load(fpath)
        dims = np.array(nii.shape)[::-1]
        if len(dims) != 3:  # TODO: extend to 4D?
            print("Please supply a 3D nifti volume.")
            return

#         data = np.transpose(nii.get_data())
        data = nii.get_data()

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

        if file_format == "IMAGE_SEQUENCE":
            data = np.reshape(data, [dims[2], -1])
            img = bpy.data.images.new("img", width=dims[0], height=dims[1])
            for slcnr, slc in enumerate(data):
                pixels = []
                for pix in slc:
                    pixval = pix
                    pixels.append([pixval, pixval, pixval, 1.0])
                pixels = [chan for px in pixels for chan in px]
                img.pixels = pixels
                img.filepath_raw = os.path.join(tmppath,
                                                str(slcnr).zfill(4) + ".png")
                img.file_format = 'PNG'
                img.save()
        elif file_format == "RAW_8BIT":
            data *= 255
            with open(tmppath, "wb") as f:
                f.write(bytes(data.astype('uint8')))
            img = tmppath

    return dims, datarange, labels, img


def import_scalars(directory, filenames, name=""):
    """Import overlay as continuous scalars."""

    scn = bpy.context.scene
    tb = scn.tb

    if tb.objecttype == "tracts":
        import_tractscalars(directory, filenames, name=name)
    elif tb.objecttype == "surfaces":
        import_surfscalars(directory, filenames, name=name)
    elif tb.objecttype == "voxelvolumes":
        import_voxoverlay(directory, filenames, name=name)


def import_labels(directory, filenames, name=""):
    """Import overlay as discrete labels."""

    scn = bpy.context.scene
    tb = scn.tb

    if tb.objecttype == "tracts":
        pass
#         import_tractlabels(directory, filenames)  # TODO
    elif tb.objecttype == "surfaces":
        import_surflabels(directory, filenames, name=name)
    elif tb.objecttype == "voxelvolumes":
        import_voxoverlay(directory, filenames, name=name, is_label=True)


def import_borders(directory, filenames, name=""):
    """Import overlay as curves."""

    scn = bpy.context.scene
    tb = scn.tb

    if tb.objecttype == "tracts":
        pass
    elif tb.objecttype == "surfaces":
        import_surfborders(directory, filenames, name=name)
    elif tb.objecttype == "voxelvolumes":
        pass


def import_tractscalars(directory, files, name=""):
    """Import scalar overlay on tract object."""

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        tb_ob = tb_utils.active_tb_object()[0]
        ob = bpy.data.objects[tb_ob.name]

        tb_mat.create_vc_overlay_tract(ob, fpath, name=name)


def read_tractscalar(fpath):
    """"""

    if fpath.endswith('.npy'):
        scalars = np.load(fpath)
    elif fpath.endswith('.npz'):
        npzfile = np.load(fpath)
        for k in npzfile:
            scalars.append(npzfile[k])
    elif fpath.endswith('.asc'):
        # mrtrix convention assumed (1 streamline per line)
        scalars = []
        with open(fpath) as f:
            for line in f:
                tokens = line.rstrip("\n").split(' ')
                points = []
                for token in tokens:
                    if token:
                        points.append(float(token))
                scalars.append(points)

    return scalars


def import_tractlabels(directory, files, name=""):
    """Import label overlay on tract object."""

    pass  # TODO


def import_surfscalars(directory, files, name=""):
    """Import scalar overlay on surface object."""

    # TODO: handle timeseries
    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        tb_ob = tb_utils.active_tb_object()[0]
        ob = bpy.data.objects[tb_ob.name]

        if fpath.endswith('.label'):  # but not treated as a label
            tb_mat.create_vg_overlay(ob, fpath, name=name, is_label=False)
        else:  # assumed scalar overlay
            tb_mat.create_vc_overlay(ob, fpath, name=name)


def import_surflabels(directory, files, name=""):
    """Import label overlay on surface object."""

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        tb_ob = tb_utils.active_tb_object()[0]
        ob = bpy.data.objects[tb_ob.name]

        if fpath.endswith('.label'):
            tb_mat.create_vg_overlay(ob, fpath, name=name, is_label=True)
        elif (fpath.endswith('.annot') | 
              fpath.endswith('.gii') | 
              fpath.endswith('.border')):
            tb_mat.create_vg_annot(ob, fpath, name=name)
            # TODO: figure out from gifti if it is annot or label
        else:  # assumed scalar overlay type with integer labels??
            tb_mat.create_vc_overlay(ob, fpath, name=name)
#         TODO: consider using ob.data.vertex_layers_int.new()??


def import_surfborders(directory, files, name=""):
    """Import label overlay on surface object."""

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        tb_ob = tb_utils.active_tb_object()[0]
        ob = bpy.data.objects[tb_ob.name]

        if fpath.endswith('.border'):
            tb_mat.create_border_curves(ob, fpath, name=name)
        else:
            print("Only Connectome Workbench .border files supported")


def read_surfscalar(fpath):
    """Read a surface scalar overlay file."""

    scn = bpy.context.scene
    tb = scn.tb

    # TODO: handle what happens on importing multiple objects
    # TODO: read more formats: e.g. .dpv, .dpf, ...
    if fpath.endswith('.npy'):
        scalars = np.load(fpath)
    elif fpath.endswith('.npz'):
        npzfile = np.load(fpath)
        for k in npzfile:
            scalars.append(npzfile[k])
    elif fpath.endswith('.gii'):
        nib = tb_utils.validate_nibabel('.gii')
        if tb.nibabel_valid:
            gio = nib.gifti.giftiio
            img = gio.read(fpath)
            scalars = img.darrays[0].data
    elif fpath.endswith('dscalar.nii'):  # CIFTI not yet working properly: in nibabel?
        nib = tb_utils.validate_nibabel('dscalar.nii')
        if tb.nibabel_valid:
            gio = nib.gifti.giftiio
            nii = gio.read(fpath)
            scalars = np.squeeze(nii.get_data())
    else:  # I will try to read it as a freesurfer binary
        nib = tb_utils.validate_nibabel('')
        if tb.nibabel_valid:
            fsio = nib.freesurfer.io
            scalars = fsio.read_morph_data(fpath)
        else:
            with open(fpath, "rb") as f:
                f.seek(15, os.SEEK_SET)
                scalars = np.fromfile(f, dtype='>f4')

    return scalars


def read_surflabel(fpath, is_label=False):
    """Read a surface label overlay file."""

    scn = bpy.context.scene
    tb = scn.tb

    if fpath.endswith('.label'):
        nib = tb_utils.validate_nibabel('.label')
        if tb.nibabel_valid:
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
    tb = scn.tb

    nib = tb_utils.validate_nibabel('.annot')
    if tb.nibabel_valid:
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
            pass  #TODO # CIFTI not yet working properly: in nibabel?
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
    i=1
    for _, l in enumerate(labeltable.labels, 1):
        labelmask = np.where(labels == l.key)[0]
        newlabels[labelmask] = i
        if (labelmask != 0).sum():
            i+=1

    return labels, ctab, names


def read_surfannot_freesurfer(fpath):
    """Read a .annot surface annotation file."""

    scn = bpy.context.scene
    tb = scn.tb

    nib = tb_utils.validate_nibabel('.annot')
    if tb.nibabel_valid:
        fsio = nib.freesurfer.io
        labels, ctab, bnames = fsio.read_annot(fpath, orig_ids=False)
        names = [name.decode('utf-8') for name in bnames]
        return labels, ctab, names
    else:
        print('nibabel required for reading .annot files')


def read_surfannot_gifti(fpath):
    """Read a .gii surface annotation file."""

    scn = bpy.context.scene
    tb = scn.tb

    nib = tb_utils.validate_nibabel('.annot')
    if tb.nibabel_valid:
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


def import_voxoverlay(directory, filenames, name="", is_label=False):
    """Import an overlay on a voxelvolume."""

    scn = bpy.context.scene
    tb = scn.tb

    # TODO: handle invalid selections
    sformfile = ""
    tb_ob, _ = tb_utils.active_tb_object()
    ob = import_voxelvolume(directory, filenames, name,
                            sformfile, tb_ob, is_label)
    parentvolume = bpy.data.objects[tb_ob.name]
    ob.parent = parentvolume


def add_scalar_to_collection(name, scalarrange):
    """Add scalar to the TractBlender collection."""

    scn = bpy.context.scene
    tb = scn.tb

    tb_ob = tb_utils.active_tb_object()[0]

    scalar = tb_ob.scalars.add()
    scalar.name = name
    scalar.range = scalarrange

    tb_ob.index_scalars = (len(tb_ob.scalars)-1)


def add_label_to_collection(name, value, colour):
    """Add label to the TractBlender collection."""

    scn = bpy.context.scene
    tb = scn.tb

    tb_ob = tb_utils.active_tb_object()[0]

    label = tb_ob.labels.add()
    label.name = name
    label.value = value
    label.colour = colour

    tb_ob.index_labels = (len(tb_ob.labels)-1)


def add_border_to_collection(name, colour,
                            bevel_depth=0.5, bevel_resolution=10,
                            iterations=10, factor=0.5):
    """Add border to the TractBlender collection."""

    scn = bpy.context.scene
    tb = scn.tb

    tb_ob = tb_utils.active_tb_object()[0]

    border = tb_ob.borders.add()
    border.name = name
    border.colour = colour
    border.bevel_depth = bevel_depth
    border.bevel_resolution = bevel_resolution
    border.iterations = iterations
    border.factor = factor

    tb_ob.index_borders = (len(tb_ob.borders)-1)


# ========================================================================== #
# reading tract files
# ========================================================================== #


def read_dipy_streamlines(dpyfile):
    """Return all streamlines in a dipy .dpy tract file (uses dipy)."""

    if tb_utils.validate_dipy('.trk'):
        dpr = Dpy('fornix.dpy', 'r')
        streamlines = dpr.read_tracks()
        dpr.close()

    return streamlines


def read_trackvis_streamlines(trkfile):
    """Return all streamlines in a Trackvis .trk tract file (uses nibabel)."""

    nib = tb_utils.validate_nibabel('.trk')
    if bpy.context.scene.tb.nibabel_valid:
        tv = nib.trackvis
        streams, hdr = tv.read(trkfile)
        streamlines = [s[0] for s in streams]

        return streamlines


def read_camino_streamlines(bfloatfile):
    """Return all streamlines in a Camino .bfloat/.Bfloat tract file."""

    if bfloatfile.endswith('.Bfloat'):
        streamlinevec = np.fromfile(bfloatfile, dtype='>f4')
    elif bfloatfile.endswith('.bfloat'):
        streamlinevec = np.fromfile(bfloatfile, dtype='<f4')
    elif bfloatfile.endswith('.Bdouble'):
        streamlinevec = np.fromfile(bfloatfile, dtype='>f8')
    elif bfloatfile.endswith('.bdouble'):
        streamlinevec = np.fromfile(bfloatfile, dtype='<f8')

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


def read_vtk_streamlines(vtkfile):
    """Return all streamlines in a (MRtrix) .vtk tract file."""

    points, tracts, scalars, cscalars, lut = import_vtk_polylines(vtkfile)
    streamlines = unpack_vtk_polylines(points, tracts)

    return streamlines


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


def read_mrtrix_streamlines(tckfile):
    """Return all streamlines in a MRtrix .tck tract file."""

    datatype, offset = read_mrtrix_header(tckfile)
    streamlinevector = read_mrtrix_tracks(tckfile, datatype, offset)
    streamlines = unpack_mrtrix_streamlines(streamlinevector)

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


def read_numpy_streamline(tckfile):
    """Read a [Npointsx3] streamline from a *.npy file."""

    streamline = np.load(tckfile)

    return [streamline]


def read_numpyz_streamlines(tckfile):
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
# geometry spatial transformations
# ========================================================================== #


def read_affine_matrix(filepath):
    """Get the affine transformation matrix from the nifti or textfile."""

    scn = bpy.context.scene
    tb = scn.tb

    if not filepath:
        affine = mathutils.Matrix()
    elif (filepath.endswith('.nii') | filepath.endswith('.nii.gz')):
        nib = tb_utils.validate_nibabel('nifti')
        if tb.nibabel_valid:
            affine = nib.load(filepath).header.get_sform()
    elif filepath.endswith('.gii'):
        nib = tb_utils.validate_nibabel('gifti')
        if tb.nibabel_valid:
            gio = nib.gifti.giftiio
            img = gio.read(filepath)
            xform = img.darrays[0].coordsys.xform
            if len(xform) == 16:
                xform = np.reshape(xform, [4, 4])
            affine = mathutils.Matrix(xform)
    else:
        affine = np.loadtxt(filepath)
        # TODO: check if matrix if valid
#         if affine.shape is not (4,4):
#             return {'cannot calculate transform: \
#                     invalid affine transformation matrix'}

    return mathutils.Matrix(affine)
