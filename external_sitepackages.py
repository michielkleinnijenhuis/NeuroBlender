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
import subprocess
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty

# ========================================================================== #


bl_info = {
    "name": "External site-packages",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 1),
    "blender": (2, 77, 0),
    "location": "",
    "description": """
        Script for persistently importing site-packages at blender startup
        packages could be installed in a 'shadow' conda-env, e.g. using:
        >>> conda create --name blender2.77 python=3.5.1
        >>> source activate blender2.77
        >>> pip install git+git://github.com/nipy/nibabel.git@master
        >>> pip install git+git://github.com/nipy/dipy.git@master
        ...
        on Mac this would be the directory:
        <conda root dir>/envs/blender2.77/lib/python3.5/site-packages
        On startup blender scans the 'scripts/startup/' directory
        for python modules and imports them
        For persistent loading of packages at blender startup:
        >>> cp <path-to-addons>/TractBlender/import_nibabel_startup.py \
        <path-to-startup-scripts>
        E.g. on Mac these path would usually be something like:
        ~/Library/Application\ Support/Blender/<version>/scripts/addons/
        and
        /Applications/blender.app/Contents/Resources/<version>/scripts/startup/
        """,
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "System"}


# ========================================================================== #


class ExternalSitePackages(Operator, ImportHelper):
    bl_idname = "wm.external_sitepackages"
    bl_label = "Expose site-packages"
    bl_description = "Exposes external site-packages directory to blender"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        add_path(self.directory)

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


def menu_func(self, context):
    self.layout.operator("wm.external_sitepackages")


def initialize():
    directory = os.path.dirname(__file__)
    basename = 'external_sitepackages'
    aux_path_file = os.path.join(directory, basename + '.txt')
    with open(aux_path_file, 'r') as f:
        aux_path = f.read()
    add_path(aux_path)


def add_path(aux_path):
    """"""
    sys_paths = sys.path
    check_result = [s for s in sys_paths if aux_path in s]
    if (check_result == []):
        sys.path.append(aux_path)


def get_conda_root():  # FIXME
    """"""
    bash_command = "echo $(conda info --root)"
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    conda_root_dir = process.communicate()[0]

    return conda_root_dir


def get_python_version():
    """"""
    python_version = 'python' + \
        sys.version_info.major + '.' + \
        sys.version_info.major

    return python_version


def build_aux_path(root_dir, conda_env, python_version):
    """"""
    os.path.join(root_dir, 'envs',
                 conda_env, 'lib',
                 python_v, 'site-packages')

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
