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


def compare_names(name, old_names, newname_funs, newname_argdict, ca=[]):
    """"""

    while True:
        intersect = set([])
        for old_names, fun in zip(old_names, newname_funs):
            new_names = fun(name, newname_argdict)
            intersect = intersect or set(new_names) & set(old_names)
        if (not bool(intersect)):
            break
        name = check_name(name, "", ca)

    return name


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
    idxs = [nb.tracts.find(parent),
            nb.surfaces.find(parent),
            nb.voxelvolumes.find(parent)]
    obinfo = {}
    obinfo['name'] = parent
    obinfo['type'] = obtypes[[i > -1 for i in idxs].index(True)]
    obinfo['idx'] = idxs[[i > -1 for i in idxs].index(True)]

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


def validate_dipy(ext):
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


def h5_in2out(inds):
    """Permute dimension labels to Fortran order."""

    outlayout = 'xyzct'[0:inds.ndim]
    try:
        inlayout = [d.label for d in inds.dims]
    except:
        inlayout = 'xyzct'[0:inds.ndim]

    in2out = [inlayout.index(l) for l in outlayout]

    return in2out


def make_polyline(curvedata, clist):
    """Create a 3D curve from a list of points."""

    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(clist)-1)
    for num in range(len(clist)):
        x, y, z = clist[num]
        polyline.points[num].co = (x, y, z, 1)
    polyline.order_u = len(polyline.points)-1
    polyline.use_endpoint_u = True


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

    if overwrite:
        return False

    abstexdir = bpy.path.abspath(texdir)
    if not os.path.isdir(abstexdir):
        return False

    for pf in ('affine', 'dims', 'datarange', 'labels'):
        f = os.path.join(abstexdir, "{}.npy".format(pf))
        if not os.path.isfile(f):
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
