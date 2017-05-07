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


"""Persistent import of external site-packages into Blender.

Packages could be conveniently installed in a 'shadow' conda-env, e.g. using:
>>> conda create --name blender python=3.5.1
>>> source activate blender
>>> pip install git+git://github.com/nipy/nibabel.git@master
>>> pip install git+git://github.com/nipy/dipy.git@master
on Mac these packages would end up in the directory:
<conda root dir>/envs/blender/lib/python3.5/site-packages

On enabling the add-on, it looks for a path to site-packages in the file:
<add-on directory>/external_sitepackages.txt
On Mac <add-on directory> would usually be something like:
~/Library/Application\ Support/Blender/<version>/scripts/addons

If not found, it looks for:
<conda root dir>/envs/blender/lib/python3.5/site-packages



"""


# ========================================================================== #


import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty

import os
import sys
import subprocess


# ========================================================================== #


bl_info = {
    "name": "External site-packages",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 2),
    "blender": (2, 78, 0),
    "location": "",
    "description": "Script for persistent import of external site-packages",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "System"}
    # FIXME: documentation/tracker links


# ========================================================================== #


class ExternalSitePackages(Operator, ImportHelper):
    """Exposes external site-packages directory to blender."""

    bl_idname = "wm.external_sitepackages"
    bl_label = "Expose site-packages"
    bl_description = "Exposes external site-packages directory to blender"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="DIR_PATH")

    def execute(self, context):

        addon_dir = os.path.dirname(__file__)
        save_path(addon_dir, self.directory)

        info = add_path(self.directory)

        self.report({'INFO'}, info)

        return {'FINISHED'}

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


def menu_func(self, context):
    """Create a menu item."""

    self.layout.operator("wm.external_sitepackages")


def initialize():
    """Add external site-packages to Blender."""

    # see if we can find site-packages in accompanying textfile
    addon_dir = os.path.dirname(__file__)
    basename = 'external_sitepackages'
    aux_path_file = os.path.join(addon_dir, basename + '.txt')
    try:
        with open(aux_path_file, 'r') as f:
            aux_path = f.read()
    except:
        infostring = 'no external site-packages file found: {}'
        # see if we can find the setup decribed in the module's docstring
        conda_root = get_conda_root()
        python_version = get_python_version()
        aux_path = build_aux_path(conda_root, 'blender', python_version)
        if os.path.exists(aux_path):
            info = add_path(aux_path)
        else:
            info = 'no site-packages found at {}'.format(aux_path)
    else:
        info = add_path(aux_path)

    print(info)


def add_path(aux_path):
    """Add a path to sys.path."""

    sys_paths = sys.path
    already_in_path = [s for s in sys_paths if aux_path in s]
    if not already_in_path:
        sys.path.append(aux_path)
        info = 'site-packages appended to sys.path: {}'.format(aux_path)
    else:
        info = 'site-packages already in sys.path: {}'.format(aux_path)

    return info

def save_path(addon_dir, aux_path):
    """Write site-packages path to file in addon directory."""

    nibdir_txt = os.path.join(addon_dir, 'external_sitepackages.txt')
    with open(nibdir_txt, 'w') as f:
        f.write(aux_path)


def get_conda_root():
    """Get the Anaconda root directory."""

    bash_command = "conda info --root"
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    conda_root_dir = process.communicate()[0].strip().decode("utf-8")

    return conda_root_dir


def get_python_version():
    """Get the python version."""

    python_version = 'python{}.{}'.format(sys.version_info.major,
                                          sys.version_info.minor)

    return python_version


def build_aux_path(root_dir, conda_env, python_version):
    """Build the path to a conda env site-packages directory."""

    aux_path = os.path.join(root_dir, 'envs',
                            conda_env, 'lib',
                            python_version, 'site-packages')

    return aux_path


# ========================================================================== #


def register():
    bpy.utils.register_module(__name__)
    bpy.types.CONSOLE_MT_console.append(menu_func)
    initialize()


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.CONSOLE_MT_console.remove(menu_func)


if __name__ == "__main__":
    register()
