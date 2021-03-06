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


"""The NeuroBlender utilities module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module hosts generally useful functions.
"""


import os
import sys
import errno
import tempfile
import random
from glob import glob

import numpy as np
from mathutils import Matrix

import bpy


# ========================================================================== #
# general utilities
# ========================================================================== #


def get_nb_collections(context,
                       parentpaths=["nb"],
                       colltypes=["tracts", "surfaces", "voxelvolumes"]):
    """Get NeuroBlender collections and item lists.

    The default returns the top-level NeuroBlender collections.
    """

    scn = context.scene

    nb_collections = []
    nb_items = []
    for parent in parentpaths:
        for colltype in colltypes:
            datapath = "{}.{}".format(parent, colltype)
            try:
                nb_collection = scn.path_resolve(datapath)
            except ValueError:
                pass
            else:
                nb_collections.append(nb_collection)
                nb_items += nb_collection

    nb_dpaths = [item.path_from_id() for item in nb_items]

    return nb_collections, nb_items, nb_dpaths


def compare_names(name, ca_collections,
                  newname_funs, newname_argdict,
                  prefix_parentname=True):
    """Rename items with names taht occur in collections."""

    def find_intersect(old_names, new_names, ca):
        """Determine intersecting names and suggest a new set."""

        intersect = set(old_names) & set(new_names)
        new_names = [check_name(name, "", ca) if name in intersect else name
                     for name in new_names]
        return intersect, new_names

    all_names = [fun(name, newname_argdict) for fun in newname_funs]

    while True:
        intersect = set([])
        i = 0
        for ca, proposed_names in zip(ca_collections, all_names):

            old_names = [k for c in ca for k in c.keys()]

            iter_intersect, proposed_names = find_intersect(old_names,
                                                            proposed_names,
                                                            ca)

            if i == 0 and iter_intersect:
                # change groupname
                all_names[0] = proposed_names
                # update itemnames with new groupname
                for j, fun in enumerate(newname_funs[1:]):
                    all_names[j+1] = fun(proposed_names[0],
                                         newname_argdict)
            if i != 0 and iter_intersect:
                # keep groupname
                all_names[0] = newname_funs[0](all_names[0][0],
                                               newname_argdict)
                # change itemnames
                all_names[i] = proposed_names

            intersect = intersect or iter_intersect
            i += 1

        if (not bool(intersect)):
            break

    return tuple(all_names)


def check_name(name, fpath, checkagainst=[],
               nzfill=3, forcefill=False,
               maxlen=40, firstfill=0):
    """Make sure a unique name is given."""


    def get_full_set():

        context = bpy.context

        # NeuroBlender objects and overlays
        obc, _, obpaths = get_nb_collections(context)
        ovtypes = ["scalargroups", "labelgroups", "bordergroups"]
        ovc, _, ovpaths = get_nb_collections(context, obpaths, ovtypes)
        oitypes = ["scalars", "labels", "borders"]
        oic, _, _ = get_nb_collections(context, ovpaths, oitypes)

        # vertex groups, vertex colors, uv maps
        _, surfs, _ = get_nb_collections(context, colltypes=["surfaces"])
        vgs = [bpy.data.objects[s.name].vertex_groups for s in surfs]
        vcs = [bpy.data.objects[s.name].data.vertex_colors for s in surfs]
        uvl = [bpy.data.objects[s.name].data.uv_layers for s in surfs]

        # blender datablocks
        bdb = [bpy.data.materials,
               bpy.data.textures,
               bpy.data.objects,
               bpy.data.meshes,
               bpy.data.lamps,
               bpy.data.images,
               bpy.data.curves,
               bpy.data.cameras]

        return obc + ovc + oic + vgs + vcs + uvl + bdb

    if not checkagainst:
        ca = get_full_set()

    # if unspecified, derive a name from the filename
    if not name:
        name = os.path.basename(fpath)

    # long names are not handled in Blender (maxbytes=63)
    if len(name) > maxlen:
        name = name[-maxlen:]
        print('name too long: truncated basename to ', name)

    # force a numeric postfix on the basename
    if forcefill:
        firstname = name + "." + str(firstfill).zfill(nzfill)
    else:
        firstname = name

    # check if the name already exists ...
    # in whatever collection(s) it is checked against
    present = [ca.get(firstname) for ca in checkagainst]
    if any(present):  # the name does exist somewhere
        i = firstfill
        while any([ca.get(name + '.' + str(i).zfill(nzfill))
                   for ca in checkagainst]):
            i += 1
        # found the first available postfix
        name = name + '.' + str(i).zfill(nzfill)
    else:
        name = firstname

    return name


def random_RGBA():
    """Get a random RGB triplet + alpha."""

    return [random.random() for _ in range(4)]


def random_RGB():
    """Get a random RGB triplet."""

    return [random.random() for _ in range(3)]


def move_to_layer(ob, layer):
    """Move object to layer."""

    ob.layers[layer] = True
    for i in range(20):
        ob.layers[i] = (i == layer)


def active_nb_object():
    """Identify the active object in the ImportPanel UIList."""

    nb = bpy.context.scene.nb
    ob_idx = eval("nb.index_%s" % nb.objecttype)
    nb_ob = eval("nb.%s[%d]" % (nb.objecttype, ob_idx))

    return nb_ob, ob_idx


def active_nb_overlay():
    """Identify the active overlay in the ImportPanel UIList."""

    nb = bpy.context.scene.nb
    ob_idx = eval("nb.index_%s" % nb.objecttype)
    nb_ob = eval("nb.%s[%d]" % (nb.objecttype, ob_idx))

    ov_idx = eval("nb_ob.index_%s" % nb.overlaytype)
    nb_ov = eval("nb_ob.%s[%d]" % (nb.overlaytype, ov_idx))

    return nb_ov, ov_idx


def active_nb_overlayitem():
    """Identify the active overlay item in the ImportPanel UIList."""

    nb = bpy.context.scene.nb
    ob_idx = eval("nb.index_%s" % nb.objecttype)
    nb_ob = eval("nb.%s[%d]" % (nb.objecttype, ob_idx))

    ov_idx = eval("nb_ob.index_%s" % nb.overlaytype)
    nb_ov = eval("nb_ob.%s[%d]" % (nb.overlaytype, ov_idx))

    it_type = nb.overlaytype.replace("groups", "s")
    it_idx = eval("nb_ov.index_%s" % it_type)
    nb_it = eval("nb_ov.%s[%d]" % (it_type, it_idx))

    return nb_it, it_idx


def get_nb_objectinfo(parent):
    """"""

    scn = bpy.context.scene
    nb = scn.nb

    obtypes = ["tracts", "surfaces", "voxelvolumes"]
    layerdict = {'tracts': 0, 'surfaces': 1, 'voxelvolumes': 2}

    idxs = [nb.tracts.find(parent),
            nb.surfaces.find(parent),
            nb.voxelvolumes.find(parent)]
    obinfo = {}
    obinfo['name'] = parent
    obinfo['type'] = obtypes[[i > -1 for i in idxs].index(True)]
    obinfo['idx'] = idxs[[i > -1 for i in idxs].index(True)]
    obinfo['layer'] = layerdict[obinfo['type']]

    return obinfo


def validate_texture_path(voxelvolume):
    """"""

    tex = bpy.data.textures[voxelvolume.name]

    return os.path.isfile(tex.voxel_data.filepath)


def force_save(projectdir):
    """Save the project to the default directory with unique name."""

    defaultpath = tempfile.mkstemp(suffix='.blend',
                                   prefix='untitled_',
                                   dir=projectdir)
    bpy.ops.wm.save_as_mainfile(filepath=defaultpath[1])

    return defaultpath[1]


def validate_anims_campath(anims):
    """Validate the set of camera trajectory animations."""

    for i, anim in enumerate(anims):

        if not validate_campath(anim.campaths_enum):
            anim.is_valid = False
            continue
        if not validate_timings(anims, i):
            anim.is_valid = False
            continue

        anim.is_valid = True

        # TODO: validate cam and constraints


def validate_timings(anims, index_animations):
    """Check if an animation overlaps in time with others."""

    anim = anims[index_animations]
    frames = range(anim.frame_start, anim.frame_end + 1)
    lca = [range(anim_ca.frame_start, anim_ca.frame_end + 1)
           for j, anim_ca in enumerate(anims) if j != index_animations]
    frames_ca = [item for sublist in lca for item in sublist]

    return bool(len(set(frames) & set(frames_ca)))


def validate_campath(campathname):
    """Check if a camera trajectory curve is valid."""

    scn = bpy.context.scene
    nb = scn.nb

    campath = nb.campaths.get(campathname)
    if campath:
        campath.is_valid = bool(bpy.data.objects.get(campath.name))
        return campath.is_valid
    else:
        return False


# ========================================================================== #
# nibabel-related functions
# ========================================================================== #
# #Environment prep:
# conda create --name blender2.77 python=3.5.1
# source activate blender2.77
# #on Mac installed packages would be the directory:
# #<conda root dir>/envs/blender2.77/lib/python3.5/site-packages
# pip install git+git://github.com/nipy/nibabel.git@master
# pip install git+git://github.com/nipy/nipype.git@master
# conda install cython
# pip install git+git://github.com/nipy/dipy.git@master
# #install of pysurfer fails: mayavi not available for python3
# conda install Ipython scipy matplotlib mayavi
# pip install git+git://github.com/nipy/pysurfer.git#egg=pysurfer
#
# #On startup blender scans the scripts/startup/ directory
# #for python modules and imports them
# #For persistent loading of nibabel at blender startup:
# >>> cp <path-to-NeuroBlender-addon>/import_nibabel_startup.py \
# <path-to-blender-startup-scripts>
# E.g. on Mac these path would usually be something like:
# ~/Library/Application Support/Blender/<version>/scripts/addons/NeuroBlender/
# and
# /Applications/blender.app/Contents/Resources/<version>/scripts/startup/
# ========================================================================== #


def validate_nibabel(ext):
    """Try to import nibabel."""

    scn = bpy.context.scene
    nb = scn.nb

    add_path(nb.settingprops.esp_path)
    try:
        import nibabel as nib
        nb.settingprops.nibabel_valid = True
        return nib
    except ImportError:
        nb.settingprops.nibabel_valid = False
        raise
#         return {'cannot read ' + ext + ': nibabel not found'}


def validate_dipy(ext='tck'):
    """Try to import dipy."""

    nb = bpy.context.scene.nb

    add_path(nb.settingprops.esp_path)
    try:
        import dipy
        valid = True
    except ImportError:
        valid = False

    return valid


def add_path(aux_path):
    """Add the path to the syspath."""

    sys_paths = sys.path
    check_result = [s for s in sys_paths if aux_path in s]
    if not check_result:
        sys.path.append(aux_path)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def validate_nb_objects(collections):
    """Validate that NeuroBlender objects can be found in Blender."""

    itemtype = "object"
    for collection in collections:
        for item in collection:
            try:
                ob = bpy.data.objects[item.name]
            except KeyError:
                print("The " + itemtype + " '" + item.name +
                      "' seems to have been removed or renamed " +
                      "outside of NeuroBlender")
                item.is_valid = False
            else:
                item.is_valid = True
                # descend into the object's vertexgroups
                validate_nb_overlays(ob,
                                     [sg.scalars for sg in item.scalargroups] +
                                     [lg.labels for lg in item.labelgroups])


def validate_nb_overlays(ob, collections):
    """Validate that a NeuroBlender vertexgroup can be found in Blender."""

    itemtype = "vertexgroup"
    for collection in collections:
        for item in collection:
            try:
                ob.vertex_groups[item.name]
            except KeyError:
                print("The " + itemtype + " '" + item.name +
                      "' seems to have been removed or renamed " +
                      "outside of NeuroBlender")
                item.is_valid = False
            else:
                item.is_valid = True


def add_item(parent, childpath, props):
    """Add an item to a collection."""

    scn = bpy.context.scene

    parentpath = parent.path_from_id()
    coll = eval("scn.%s.%s" % (parentpath, childpath))
    item = coll.add()
    exec("scn.%s.index_%s = (len(coll)-1)" % (parentpath, childpath))

    for k, v in props.items():
        if isinstance(v, tuple):
            for i, c in enumerate(v):
                exec("item.%s[i] = c" % k)
        else:
            item[k] = v

    if 'name' in props:
        item.name_mem = props['name']

    return item


# ========================================================================== #
# geometry spatial transformations
# ========================================================================== #


def read_affine_matrix(filepath, fieldname='stack'):
    """Get the affine transformation matrix from the nifti or textfile."""

    scn = bpy.context.scene
    nb = scn.nb

    if not filepath:
        affine = Matrix()
    elif filepath.endswith('.nii') | filepath.endswith('.nii.gz'):
        nib = validate_nibabel('nifti')
        if nb.settingprops.nibabel_valid:
            affine = nib.load(filepath).header.get_sform()
    elif filepath.endswith('.gii'):
        nib = validate_nibabel('gifti')
        if nb.settingprops.nibabel_valid:
            img = nib.load(filepath)
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


def h5_in2out(inds):
    """Permute dimension labels to Fortran order."""

    outlayout = 'xyzct'[0:inds.ndim]
    try:
        inlayout = [d.label for d in inds.dims]
    except:
        inlayout = 'xyzct'[0:inds.ndim]

    in2out = [inlayout.index(l) for l in outlayout]

    return in2out


def slice_rotations(matrix_world, index_ijk):
    """Find closest quadrant rotation and direction of affine."""

    row = matrix_world.row[index_ijk][:3]
    index_xyz = np.argmax(np.absolute(row))
    if row[index_xyz] > 0:
        p = 'slc_pos'
    else:
        p = '(1 - slc_pos)'

    return index_xyz, p


def make_polyline(curvedata, clist,
                  radius=0.2, radius_variation=False,
                  use_endpoint_u=True, use_cyclic_u=False):
    """Create a 3D curve from a list of points."""

    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(clist)-1)
    for num in range(len(clist)):
        polyline.points[num].co = tuple(clist[num][0:3]) + (1,)
        if len(clist[num]) > 3:
            radius = clist[num][3]
        elif radius_variation:
            radius = radius + random.random() * radius
        polyline.points[num].radius = radius
        if len(clist[-1]) > 6:  # branchpoint
            polyline.points[num].weight = clist[num][6]
    if len(clist[-1]) > 4:  # structure
        polyline.material_index = int(clist[-1][4])
    if len(clist[-1]) > 7:  # colourcode
        polyline.material_index = int(clist[-1][7])
    polyline.order_u = len(polyline.points)-1
    polyline.use_endpoint_u = use_endpoint_u
    polyline.use_cyclic_u = use_cyclic_u


def normalize_data(data):
    """Normalize data between 0 and 1."""

    data = data.astype('float64')
    datamin = np.amin(data)
    datamax = np.amax(data)
    data -= datamin
    data *= 1/(datamax-datamin)

    return data, [datamin, datamax]


def validate_texdir(texdir, texformat, overwrite=False, vol_idx=-1):
    """Check whether path is in a valid NeuroBlender volume texture."""

    objecttype = 'surfaces' if texformat == 'png' else 'voxelvolumes'

    # TODO: for surface textures
    if overwrite:
        return False

    abstexdir = bpy.path.abspath(texdir)
    if not os.path.isdir(abstexdir):
        return False

    pfs = ('datarange', 'labels')
    if objecttype == 'voxelvolumes':
        pfs += ('affine', 'dims')
    for pf in pfs:
        f = os.path.join(abstexdir, "{}.npy".format(pf))
        if not os.path.isfile(f):
            return False

    if objecttype == 'voxelvolumes':
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
    elif objecttype == 'surfaces':
        absimdir = abstexdir

    # TODO: see if all vols are there (this just checks if imdir is not empty)
    nfiles = len(glob(os.path.join(absimdir, '*')))
    if not nfiles:
        return False

    return True


def labels2meshes_vtk(surfdir, compdict, labelimage, labels=[],
                      spacing=[1, 1, 1], offset=[0, 0, 0], nvoxthr=0):
    """Generate meshes from a labelimage with vtk marching cubes."""

    try:
        import vtk
    except ImportError:
        return

    if not labels:
        labels = np.unique(labelimage)
        labels = np.delete(labels, 0)
        # labels = np.unique(labelimage[labelimage > 0])
    print('number of labels to process: ', len(labels))

    labelimage = np.lib.pad(labelimage.tolist(),
                            ((1, 1), (1, 1), (1, 1)),
                            'constant')
    dims = labelimage.shape

    vol = vtk.vtkImageData()
    vol.SetDimensions(dims[0], dims[1], dims[2])
    vol.SetOrigin(offset[0] * spacing[0] + spacing[0],
                  offset[1] * spacing[1] + spacing[1],
                  offset[2] * spacing[2] + spacing[2])
    # vol.SetOrigin(0, 0, 0)
    vol.SetSpacing(spacing[0], spacing[1], spacing[2])

    sc = vtk.vtkFloatArray()
    sc.SetNumberOfValues(labelimage.size)
    sc.SetNumberOfComponents(1)
    sc.SetName('tnf')
    for ii, val in enumerate(np.ravel(labelimage.swapaxes(0, 2))):
        # FIXME: why swapaxes???
        sc.SetValue(ii, val)
    vol.GetPointData().SetScalars(sc)

    dmc = vtk.vtkDiscreteMarchingCubes()
    dmc.SetInput(vol)
    dmc.ComputeNormalsOn()

    for label in labels:
        try:
            labelname = compdict[label]['name']
        except KeyError:
            labelname = 'label.{:05d}'.format(label)
        fpath = os.path.join(surfdir, '{:s}.stl'.format(labelname))
        print("Processing label {} (value: {:05d})".format(labelname, label))
        dmc.SetValue(0, label)
        dmc.Update()

        writer = vtk.vtkSTLWriter()
        writer.SetInputConnection(dmc.GetOutputPort())
        writer.SetFileName(fpath)
        writer.Write()


def force_object_update(context, ob):
    """Force an update on an object."""

    if isinstance(ob, bpy.types.Object):
        scn = context.scene
        for obj in bpy.data.objects:
            obj.select = False
        ob.select = True
        current_active = scn.objects.active
        scn.objects.active = ob
        scn.update()
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')
        scn.objects.active = current_active


def add_constraint(ob, ctype, name, target, val=None):
    """Add a constraint to the camera."""

    cns = ob.constraints.new(ctype)
    cns.name = name
    cns.target = target
    cns.owner_space = 'WORLD'
    cns.target_space = 'WORLD'
    if name.startswith('TrackTo'):
        cns.track_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
    elif name.startswith('LimitDistOut'):
        cns.limit_mode = 'LIMITDIST_OUTSIDE'
        cns.distance = val
    elif name.startswith('LimitDistIn'):
        cns.limit_mode = 'LIMITDIST_INSIDE'
        cns.distance = val
    elif name.startswith('FollowPath'):
        cns.forward_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
        cns.use_curve_follow = val == "TrackPath"
    elif name.startswith('Child Of'):
        if val is not None:
            for k, v in val.items():
                exec("cns.{} = v".format(k))

    return cns


def get_slicer(ts_slice, tdim=-1):
    """Get slicer for timeseries."""

    if list(ts_slice) != [0, -1, 1]:
        if ts_slice[1] < 0:
            ts_slice[1] = tdim
        ts_slicer = slice(ts_slice[0], ts_slice[1], ts_slice[2])
    else:
        ts_slicer = None

    return ts_slicer
