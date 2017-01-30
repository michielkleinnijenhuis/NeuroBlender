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
import sys
import errno

# ========================================================================== #
# general utilities
# ========================================================================== #


def check_name(name, fpath, checkagainst,
               nzfill=3, forcefill=False, maxlen=40, firstfill=0):
    """Make sure a unique name is given."""

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


def active_tb_object():
    """Identify the active object in the ImportPanel UIList."""

    tb = bpy.context.scene.tb
    ob_idx = eval("tb.index_%s" % tb.objecttype)
    tb_ob = eval("tb.%s[%d]" % (tb.objecttype, ob_idx))

    return tb_ob, ob_idx


def active_tb_overlay():
    """Identify the active overlay in the ImportPanel UIList."""

    tb = bpy.context.scene.tb
    ob_idx = eval("tb.index_%s" % tb.objecttype)
    tb_ob = eval("tb.%s[%d]" % (tb.objecttype, ob_idx))

    ov_idx = eval("tb_ob.index_%s" % tb.overlaytype)
    tb_ov = eval("tb_ob.%s[%d]" % (tb.overlaytype, ov_idx))

    return tb_ov, ov_idx


def active_tb_overlayitem():
    """Identify the active overlay item in the ImportPanel UIList."""

    tb = bpy.context.scene.tb
    ob_idx = eval("tb.index_%s" % tb.objecttype)
    tb_ob = eval("tb.%s[%d]" % (tb.objecttype, ob_idx))

    ov_idx = eval("tb_ob.index_%s" % tb.overlaytype)
    tb_ov = eval("tb_ob.%s[%d]" % (tb.overlaytype, ov_idx))

    it_type = tb.overlaytype.replace("groups", "s")
    it_idx = eval("tb_ov.index_%s" % it_type)
    tb_it = eval("tb_ov.%s[%d]" % (it_type, it_idx))

    return tb_it, it_idx


def get_tb_objectinfo(objectname):
    """"""

    obtypes = ["tracts", "surfaces", "voxelvolumes"]
    idxs = [tb.tracts.find(parent),
            tb.surfaces.find(parent),
            tb.voxelvolumes.find(parent)]
    obinfo['name'] = parent
    obinfo['type'] = obtypes[[i>-1 for i in idxs].index(True)]
    obinfo['idx'] = idxs[[i>-1 for i in idxs].index(True)]

    return obinfo

def validate_texture_path(voxelvolume):
    """"""

    tex = bpy.data.textures[voxelvolume.name]

    return os.path.isfile(tex.voxel_data.filepath)


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
# >>> cp <path-to-TractBlender-addon>/import_nibabel_startup.py \
# <path-to-blender-startup-scripts>
# E.g. on Mac these path would usually be something like:
# ~/Library/Application Support/Blender/<version>/scripts/addons/TractBlender/
# and
# /Applications/blender.app/Contents/Resources/<version>/scripts/startup/
# ========================================================================== #


def validate_nibabel(ext):
    """Try to import nibabel."""

    scn = bpy.context.scene
    tb = scn.tb

    add_path(tb.nibabel_path)
    try:
        import nibabel as nib
        tb.nibabel_valid = True
        return nib
    except ImportError:
        tb.nibabel_valid = False
        raise
#         return {'cannot read ' + ext + ': nibabel not found'}


def validate_dipy(ext):
    """Try to import dipy."""

    tb = bpy.context.scene.tb

    add_path(tb.nibabel_path)
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
    if (check_result == []):
        sys.path.append(aux_path)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def validate_tb_objects(collections):
    """Validate that TractBlender objects can be found in Blender."""

    itemtype = "object"
    for collection in collections:
        for item in collection:
            try:
                ob = bpy.data.objects[item.name]
            except KeyError:
                print("The " + itemtype + " '" + item.name +
                      "' seems to have been removed or renamed " +
                      "outside of TractBlender")
                item.is_valid = False
            else:
                item.is_valid = True
                # descend into the object's vertexgroups
                validate_tb_overlays(ob, [item.scalars] +
                                     [lg.labels for lg in item.labelgroups])


def validate_tb_overlays(ob, collections):
    """Validate that a TractBlender vertexgroup can be found in Blender."""

    itemtype = "vertexgroup"
    for collection in collections:
        for item in collection:
            try:
                vg = ob.vertex_groups[item.name]
            except KeyError:
                print("The " + itemtype + " '" + item.name +
                      "' seems to have been removed or renamed " +
                      "outside of TractBlender")
                item.is_valid = False
            else:
                item.is_valid = True

