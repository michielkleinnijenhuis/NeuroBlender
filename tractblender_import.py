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
    """Import streamlines, surfaces or volumes.

    Streamlines:
    This imports the streamlines found in the specified directory/files.
    Valid formats include:
    - .Bfloat (Camino big-endian floats; from 'track' command)
      == http://camino.cs.ucl.ac.uk/index.php?n=Main.Fileformats
    - .vtk (vtk polydata (ASCII); e.g. from MRtrix's 'tracks2vtk' command)
      == http://www.vtk.org/wp-content/uploads/2015/04/file-formats.pdf
    - .tck (MRtrix)
      == http://jdtournier.github.io/mrtrix-0.2/appendix/mrtrix.html
    - .npy (2d numpy arrays [Npointsx3]; single streamline per file)
    - .npz (zipped archive of Nstreamlines .npy files)
      == http://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.savez.html

    It joins the individual streamlines into one 'Curve' object.
    Tracts are scaled according to the 'scale' box.
    Beautify functions/modifiers are applied to the tract.

    Surfaces: TODO

    Volumes: TODO

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


def import_tract(fpath, name, sformfile = "", info=None):
    """"""

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


def import_surface(fpath, name, sformfile = "", info=None):
    """"""
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


def import_voxelvolume(directory, files, specname, sformfile="", tb_ob=None, is_label=False):
    """"""

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
        if not is_overlay:
            sformfile = fpath
        file_format = "RAW_8BIT"  # "IMAGE_SEQUENCE"  # 
        if file_format == "IMAGE_SEQUENCE":
            tmppath = tempfile.mkdtemp(prefix=matname, dir=bpy.app.tempdir)
        elif file_format == "RAW_8BIT":
            tmppath = tempfile.mkstemp(prefix=matname, dir=bpy.app.tempdir)[1]
        dims, datarange, labels, img = prep_nifti(fpath, tmppath, is_label, file_format=file_format)
    elif (fpath.endswith('.png') |
          fpath.endswith('.jpg') |
          fpath.endswith('.tif') |
          fpath.endswith('.tiff')):
        file_format = "IMAGE_SEQUENCE"
        img = bpy.data.images.load(fpath)
        dims = [s for s in img.size] + [len(image_sequence_resolve_all(fpath))]
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

    mat = tb_mat.get_voxmat(matname, img, dims, file_format, is_overlay, is_label, items)

    tb_mat.set_materials(me, mat)

    voxelvolume_box(me, dims)

    tb_utils.move_to_layer(ob, 2)
    scn.layers[2] = True

    return ob


def voxelvolume_box(me, dims=[256, 256, 256]):
    """"""

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

    faces=[(0,1,2,3), (0,1,5,4), (1,2,6,5),
           (2,3,7,6), (3,0,4,7), (4,5,6,7)]

    me.from_pydata(v, [], faces)
    me.update(calc_edges=True)


def image_sequence_resolve_all(filepath):
    """
    http://blender.stackexchange.com/questions/21092
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
    return [
        os.path.join(basedir, f)
        for f in files
        if f.startswith(filename_nodigits) and
           f.endswith(ext) and
           f[len(filename_nodigits):-len(ext) if ext else -1].isdigit()]


def normalize_data(data):
    """"""

    data = data.astype('float64')
    datamin = np.amin(data)
    datamax = np.amax(data)
    data -= datamin
    data *= 1/(datamax-datamin)
    return data, [datamin, datamax]


def prep_nifti(fpath, tmppath, is_label=False, file_format="IMAGE_SEQUENCE"):
    """"""

    scn = bpy.context.scene
    tb = scn.tb

    nib = tb_utils.validate_nibabel('nifti')
    if tb.nibabel_valid:

        nii = nib.load(fpath)
        dims = np.array(nii.shape)[::-1]

        if len(dims) == 3:

            data = np.transpose(nii.get_data())

            if is_label:
                mask = data<0
                if mask.any():
                    print("setting negative labels to 0")
                data[mask] = 0
                labels = np.unique(data)
                labels = labels[labels>0]
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
                    img.filepath_raw = os.path.join(tmppath, str(slcnr).zfill(4) + ".png")
                    img.file_format = 'PNG'
                    img.save()
            elif file_format == "RAW_8BIT":
                data *= 255
                with open(tmppath, "wb") as f:
                    f.write(bytes(data.astype('uint8')))
                img = tmppath

        else:
            print("please supply a 3D nifti volume")  # TODO: extend to 4D?
            return

    return dims, datarange, labels, img


def import_scalars(directory, filenames):
    """"""

    scn = bpy.context.scene
    tb = scn.tb

    if tb.objecttype == "tracts":
        pass
    elif tb.objecttype == "surfaces":
        import_surfscalars(directory, filenames)
    elif tb.objecttype == "voxelvolumes":
        import_voxoverlay(directory, filenames, False)


def import_labels(directory, filenames):
    """"""

    scn = bpy.context.scene
    tb = scn.tb

    if tb.objecttype == "tracts":
        pass
    elif tb.objecttype == "surfaces":
        import_surflabels(directory, filenames)
    elif tb.objecttype == "voxelvolumes":
        import_voxoverlay(directory, filenames, True)


def import_tractscalars(ob, scalarpath):
    """"""

    # TODO: handle what happens on importing multiple objects
    if scalarpath.endswith('.npy'):
        scalars = np.load(scalarpath)
    elif scalarpath.endswith('.npz'):
        npzfile = np.load(scalarpath)
        for k in npzfile:
            scalars.append(npzfile[k])
    # TODO: check out Tractometer, etc (see what's in DIPY), camino tractstats

    return scalars


def import_tractlabels(ob, scalarpath):
    """"""

    pass


def import_surfscalars(directory, files):
    """Import scalar overlays onto a selected object.

    """

    # TODO: handle timeseries
    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        tb_ob, _ = tb_utils.active_tb_object()
        ob = bpy.data.objects[tb_ob.name]

        if fpath.endswith('.label'):
            # but do not treat it as a label
            tb_mat.create_vg_overlay(ob, fpath, is_label=False)
        else:  # assumed scalar overlay
            tb_mat.create_vc_overlay(ob, fpath)


def import_surflabels(directory, files):
    """Import overlays onto a selected object.

    """

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        tb_ob, _ = tb_utils.active_tb_object()
        ob = bpy.data.objects[tb_ob.name]

        if fpath.endswith('.label'):
            tb_mat.create_vg_overlay(ob, fpath, True)
        elif fpath.endswith('.annot'):
            tb_mat.create_vg_annot(ob, fpath)
        elif fpath.endswith('.gii'):
            # TODO: figure out from gifti if it is annot or label
            tb_mat.create_vg_annot(ob, fpath)
        else:  # assumed scalar overlay type with integer labels??
            tb_mat.create_vc_overlay(ob, fpath)
#         TODO: consider using ob.data.vertex_layers_int.new()??


def import_surfscalar(ob, scalarpath):
    """"""

    tb = bpy.context.scene.tb

    # TODO: handle what happens on importing multiple objects
    # TODO: read more formats: e.g. .dpv, .dpf, ...
    if scalarpath.endswith('.npy'):
        scalars = np.load(scalarpath)
    elif scalarpath.endswith('.npz'):
        npzfile = np.load(scalarpath)
        for k in npzfile:
            scalars.append(npzfile[k])
    elif scalarpath.endswith('.gii'):
        nib = tb_utils.validate_nibabel('.gii')
        if tb.nibabel_valid:
            gio = nib.gifti.giftiio
            img = gio.read(scalarpath)
            scalars = img.darrays[0].data
    else:  # I will try to read it as a freesurfer binary
        nib = tb_utils.validate_nibabel('')
        if tb.nibabel_valid:
            fsio = nib.freesurfer.io
            scalars = fsio.read_morph_data(scalarpath)
        else:
            with open(scalarpath, "rb") as f:
                f.seek(15, os.SEEK_SET)
                scalars = np.fromfile(f, dtype='>f4')

    return scalars


def import_surflabel(ob, labelpath, is_label=False):
    """"""

    tb = bpy.context.scene.tb

    if labelpath.endswith('.label'):
        nib = tb_utils.validate_nibabel('.label')
        if tb.nibabel_valid:
            fsio = nib.freesurfer.io
            label, scalars = fsio.read_label(labelpath, read_scalars=True)
        else:
            labeltxt = np.loadtxt(labelpath, skiprows=2)
            label = labeltxt[:, 0]
            scalars = labeltxt[:, 4]

        if is_label:
            scalars = None  # TODO: handle file where no scalars present

    return label, scalars


def import_surfannot(labelpath):
    """"""

    tb = bpy.context.scene.tb

    if labelpath.endswith('.annot'):
        nib = tb_utils.validate_nibabel('.annot')
        if bpy.context.scene.tb.nibabel_valid:
            fsio = nib.freesurfer.io
            labels, ctab, bnames = fsio.read_annot(labelpath, orig_ids=False)
            names = [name.decode('utf-8') for name in bnames]
            return labels, ctab, names
    else:
        # I'm going to be lazy and require nibabel for .annot import
        print('nibabel required for reading .annot files')


def import_surfannot_gii(labelpath):
    """"""

    tb = bpy.context.scene.tb

    if labelpath.endswith('.gii'):
        nib = tb_utils.validate_nibabel('.gii')
        if tb.nibabel_valid:
            gio = nib.gifti.giftiio
            img = gio.read(labelpath)
            img.labeltable.get_labels_as_dict()
            labels = img.darrays[0].data
            labeltable = img.labeltable
            return labels, labeltable
#             names = [name for _, name in lt.labels_as_dict.items()]
#             ctab = [np.append((np.array(l.rgba)*255).astype(int), l.key)
#                     for l in lt.labels]
#             ctab = np.array(ctab)
#             return labels, ctab, names
    else:
        print('nibabel required for reading gifti files')


def import_voxoverlay(directory, filenames, is_label):
    """"""

    scn = bpy.context.scene
    tb = scn.tb

    # TODO: handle bad selections
    name = ""
    sformfile = ""
    tb_ob, _ = tb_utils.active_tb_object()
    ob = import_voxelvolume(directory, filenames, name, sformfile, tb_ob, is_label)
    parentvolume = bpy.data.objects[tb_ob.name]
    ob.parent = parentvolume


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
#         if not i % 100:
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
