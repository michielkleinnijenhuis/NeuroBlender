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

# ========================================================================== #
# geometry enhancements
# ========================================================================== #


def beautify_brain(ob, importtype):
    """Beautify the object."""

    if importtype == 'tracts':
        beautify_tracts(ob)
    elif importtype == 'surfaces':
        beautify_surfaces(ob)
    elif importtype == 'volumes':
        beautify_volumes(ob)


def beautify_tracts(ob, depth=0.5, res=10):
    """Bevel the streamlines."""

    ob.data.fill_mode = 'FULL'
    ob.data.bevel_depth = depth
    ob.data.bevel_resolution = res


def beautify_surfaces(ob, iterations=10, factor=0.5,
                      use_x=True, use_y=True, use_z=True):
    """Smooth the surface mesh."""

    mod = ob.modifiers.new("smooth", type='SMOOTH')
    mod.iterations = iterations
    mod.factor = factor
    mod.use_x = use_x
    mod.use_y = use_y
    mod.use_z = use_z


def beautify_volumes():  # TODO
    """Particlise the volume."""

    pass
