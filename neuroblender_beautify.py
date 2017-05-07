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


# =========================================================================== #


"""The NeuroBlender beautify functionality.

This module's functions can be called to enhance the appearance
of the objects loaded in with NeuroBlender.
"""


# =========================================================================== #


import bpy

# =========================================================================== #

def beautify_brain(ob, importtype, beautify, argdict):
    """Beautify the object."""

    if beautify:
        try:
            if importtype == 'tracts':
                beautify_tracts(ob, argdict)
            elif importtype == 'surfaces':
                beautify_surfaces(ob, argdict)
            elif importtype == 'voxelvolumes':
                beautify_voxelvolumes(ob, argdict)
        except AttributeError:
            info = "no %s to beautify" % importtype
    else:
        info = "no beautification"

    return info


def beautify_tracts(ob, argdict={"mode": "FULL",
                                 "depth": 0.5,
                                 "res": 10}):
    """Bevel the streamlines."""

    ob.data.fill_mode = argdict["mode"]
    ob.data.bevel_depth = argdict["depth"]
    ob.data.bevel_resolution = argdict["res"]

    info = "bevel: mode=%s; depth=%.3f; resolution=%3d" \
            % (argdict["mode"], argdict["depth"], argdict["res"])

    return info


def beautify_surfaces(ob, argdict={"iterations": 10,
                                   "factor": 0.5,
                                   "use_x": True,
                                   "use_y": True,
                                   "use_z": True}):
    """Smooth the surface mesh."""

    mod = ob.modifiers.new("smooth", type='SMOOTH')
    mod.iterations = argdict["iterations"]
    mod.factor = argdict["factor"]
    mod.use_x = argdict["use_x"]
    mod.use_y = argdict["use_y"]
    mod.use_z = argdict["use_z"]

    info = "smooth: iterations=%3d; factor=%.3f; use_xyz=%s %s %s" \
            % (argdict["iterations"], argdict["factor"],
               argdict["use_x"], argdict["use_y"], argdict["use_z"])

    return info


def beautify_voxelvolumes(ob, argdict={}):
    """Particlise the voxelvolume."""

    info = ""  # TODO

    return info
