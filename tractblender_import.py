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

from . import tractblender_beautify as tb_beau
from . import tractblender_materials as tb_mat
from . import tractblender_utils as tb_utils

# ========================================================================== #
# brain data import functions
# ========================================================================== #


def import_objects(directory, files, importfun,
                   importtype, specname, colourtype, colourpicker, beautify,
                   info=None):
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

        ob = importfun(fpath, name, info)

#         if sform:
#             tmat = read_transformation_matrix(sform)
#             ob.data.transform(tmat)

        tb_mat.materialise(ob, colourtype, colourpicker)
#         if scalarpath:
#             tb_mat.create_vc_overlay(ob, scalarpath)
#             tb_mat.create_vg_overlay(ob, scalarpath)

        if beautify:
            tb_beau.beautify_brain(ob, importtype)
        
        ob.select = True
        bpy.context.scene.objects.active = ob 

    return {"FINISHED"}

def import_tract(fpath, name, info=None):
    """"""

    tb = bpy.context.scene.tb
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
        return {'file format not understood; please use default extensions'}

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
#                 TODO: interpolation
#                 from scipy import interpolate
#                 x = interpolate.splprep(list(np.transpose(streamline)))
                subsample_streamlines = int(1/interpolate_streamlines)
                streamline = streamline[1::subsample_streamlines,:]
            ob = make_polyline_ob(curve, streamline)

    tract = tb.tracts.add()
    tb.index_tracts = (len(tb.tracts)-1)
    tract.name = name
    tract.nstreamlines = nsamples
    tract.tract_weeded = weed_tract
    tract.streamlines_interpolated = interpolate_streamlines

    return bpy.data.objects[name]


def import_surface(fpath, name, info=None):
    """"""
    # TODO: subsampling? (but has to be compatible with loading overlays)

    tb = bpy.context.scene.tb

    if fpath.endswith('.obj'):
        bpy.ops.import_scene.obj(filepath=fpath,
                                 axis_forward='Y', axis_up='Z',
                                 split_mode='OFF')  # needed for surfscalars
        ob = bpy.context.selected_objects[0]
        ob.name = name

    elif fpath.endswith('.stl'):
        bpy.ops.import_mesh.stl(filepath=fpath,
                                axis_forward='Y', axis_up='Z')
        ob = bpy.context.selected_objects[0]
        ob.name = name

    elif (fpath.endswith('.gii') |
          fpath.endswith('.white') |
          fpath.endswith('.pial') |
          fpath.endswith('.inflated')
          ):
        nib = tb_utils.validate_nibabel('.gifti')
        if bpy.context.scene.tb.nibabel_valid:
            gio = nib.gifti.giftiio
            fsio = nib.freesurfer.io
            if (fpath.endswith('.gii')) | (fpath.endswith('.surf.gii')):
                img = gio.read(fpath)
                verts = [tuple(vert) for vert in img.darrays[0].data]
                faces = [tuple(face) for face in img.darrays[1].data]
                tmat = img.darrays[0].coordsys.xform
                # TODO: implement/apply transform?
            elif (fpath.endswith('.white') |
                  fpath.endswith('.pial') |
                  fpath.endswith('.inflated')
                  ):
                verts, faces = fsio.read_geometry(fpath)
                verts = [tuple(vert) for vert in verts]
                faces = [tuple(face) for face in faces]
            me = bpy.data.meshes.new(name)
            me.from_pydata(verts, [], faces)
            ob = bpy.data.objects.new(name, me)
            bpy.context.scene.objects.link(ob)
            bpy.context.scene.objects.active = ob
            ob.select = True
            if (fpath.endswith('.func.gii')) | (fpath.endswith('.shape.gii')):
                pass  # TODO: additional to .gii?
        else:
            print('surface import failed')
            return

    surface = tb.surfaces.add()
    tb.index_surfaces = (len(tb.surfaces)-1)
    surface.name = name

    return ob


def import_voxelvolume(fpath, name, info=None):
    """"""

    # TODO
    if (fpath.endswith('.nii')) | (fpath.endswith('.nii.gz')):

        nib = tb_utils.validate_nibabel('nifti')
        if bpy.context.scene.tb.nibabel_valid:
            pass

    elif fpath.endswith('.png'):
        pass

    voxelvolume = tb.voxelvolumes.add()
    tb.index_voxelvolume = (len(tb.voxelvolumes)-1)
    voxelvolume.name = name

    return ob


def import_scalars(directory, files):
    """Import scalar overlays onto a selected object.

    """

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        selected_obs = bpy.context.selected_objects
        if len(selected_obs) != 1:  # TODO
            return {'can only apply overlays to one object'}

        ob = selected_obs[0]
        if fpath.endswith('.label'):
            # but do not treat it as a label
            tb_mat.create_vg_overlay(ob, fpath, labelflag=False)
        else:  # assumed scalar overlay
            tb_mat.create_vc_overlay(ob, fpath)


def import_labels(directory, files):
    """Import overlays onto a selected object.
    
    """

    if not files:
        files = os.listdir(directory)

    for f in files:
        fpath = os.path.join(directory, f)

        selected_obs = bpy.context.selected_objects
        if len(selected_obs) != 1:  # TODO
            return {'can only apply overlays to one object'}

        ob = selected_obs[0]
        if fpath.endswith('.label'):
            tb_mat.create_vg_overlay(ob, fpath, True)
        elif fpath.endswith('.annot'):
            tb_mat.create_vg_annot(ob, fpath)
        else:  # assumed scalar overlay type with integer labels??
            tb_mat.create_vc_overlay(ob, fpath)
#         TODO: consider using ob.data.vertex_layers_int.new()??


def import_tractscalars(ob, scalarpath):  # TODO
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


def import_surfscalars(ob, scalarpath):
    """"""

    # TODO: handle what happens on importing multiple objects
    if scalarpath.endswith('.npy'):
        scalars = np.load(scalarpath)
    elif scalarpath.endswith('.npz'):
        npzfile = np.load(scalarpath)
        for k in npzfile:
            scalars.append(npzfile[k])
    # TODO: read more formats: e.g. .dpv, .dpf, ...
    else:  # I will try to read it as a freesurfer binary
        nib = tb_utils.validate_nibabel('')
        if bpy.context.scene.tb.nibabel_valid:
            fsio = nib.freesurfer.io
            scalars = fsio.read_morph_data(scalarpath)
        else:
            with open(scalarpath, "rb") as f:
                f.seek(15, os.SEEK_SET)
                scalars = np.fromfile(f, dtype='>f4')

    return scalars


def import_surflabel(ob, labelpath, labelflag=False):
    """"""

    if labelpath.endswith('.label'):
        nib = tb_utils.validate_nibabel('.label')
        if bpy.context.scene.tb.nibabel_valid:
            fsio = nib.freesurfer.io
            label, scalars = fsio.read_label(labelpath, read_scalars=True)
        else:
            labeltxt = np.loadtxt(labelpath, skiprows=2)
            label = labeltxt[:,0]
            scalars = labeltxt[:,4]
    
        if labelflag: scalars = None  # TODO: handle file where no scalars present

    return label, scalars


def import_surfannot(ob, labelpath):
    """"""
    
    if labelpath.endswith('.annot'):
        nib = tb_utils.validate_nibabel('.annot')
        if bpy.context.scene.tb.nibabel_valid:
            fsio = nib.freesurfer.io
            labels, ctab, names = fsio.read_annot(labelpath, orig_ids=False)
            return labels, ctab, names
    else:
        # I'm going to be lazy and require nibabel for .annot import
        print('nibabel required for reading .annot files')


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


def update_affine_transform(tb_ob, affine_new):
    """"""

    ob = bpy.data.objects[tb_ob.name]

    affine_old = mathutils.Matrix((tb_ob.srow_x,
                                   tb_ob.srow_y,
                                   tb_ob.srow_z,
                                   [0,0,0,1]))
    affine = np.linalg.inv(affine_old).dot(affine_new)

    ob.data.transform(affine)
#     ob.matrix_world = affine_new

    if affine_old.is_negative is not affine_new.is_negative:
        # FIXME: this takes a lot of time
        bpy.context.scene.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.editmode_toggle()


def read_affine_matrix(filepath):
    """Get the affine transformation matrix from the nifti or textfile."""

    if not filepath:
        affine = mathutils.Matrix()
    elif (filepath.endswith('.nii') | filepath.endswith('.nii.gz')):
        nib = tb_utils.validate_nibabel('nifti')
        affine = nib.load(filepath).header.get_sform()
    elif filepath.endswith('.gii'):
        # TODO: read from gifti
        pass
    else:
        affine = np.loadtxt(filepath)
        # TODO: check if matrix if valid
#         if affine.shape is not (4,4):
#             return {'cannot calculate transform: \
#                     invalid affine transformation matrix'}

    return mathutils.Matrix(affine)
