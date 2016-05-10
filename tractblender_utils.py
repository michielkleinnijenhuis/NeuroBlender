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

# ========================================================================== #
# general utilities
# ========================================================================== #


def check_name(name, fpath, checkagainst):
    """Make sure a unique name is given."""

    if not name:
        name = os.path.basename(fpath)

    if checkagainst.get(name) is not None:
        i = 0
        while checkagainst.get(name + '.' + str(i)) is not None:
            i += 1
        name = name + '.' + str(i)

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

    tb = bpy.context.scene.tb

    add_path(tb.nibabel_path)
    try:
        import nibabel as nib
        tb.nibabel_valid = True
        return nib
    except ImportError:
        tb.nibabel_valid = False
        return {'cannot read ' + ext + ': nibabel not found'}


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
