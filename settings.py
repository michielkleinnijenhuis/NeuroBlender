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


"""The NeuroBlender settings module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements the NeuroBlender configuration.
"""


import bpy
from bpy.types import (Operator,
                       Menu)
from bpy.props import StringProperty
from bl_operators.presets import (AddPresetBase,
                                  ExecutePreset)

from . import animations as nb_an


class OBJECT_MT_setting_presets(Menu):
    # https://docs.blender.org/api/blender_python_api_2_77_0/bpy.types.Menu.html
    bl_label = "NeuroBlender Settings Presets"
    bl_description = "Load a NeuroBlender Settings Preset"
    preset_subdir = "neuroblender_settings"
    preset_operator = "script.execute_preset_se"
    draw = Menu.draw_preset


class ExecutePreset_SE(ExecutePreset, Operator):
    """Execute a preset"""
    bl_idname = "script.execute_preset_se"
    bl_label = "NeuroBlender Settings Presets"
    bl_description = "Load a NeuroBlender Settings Preset"

    filepath = StringProperty(
        subtype='FILE_PATH',
        options={'SKIP_SAVE'},
        )
    menu_idname = StringProperty(
        name="Menu ID Name",
        description="ID name of the menu this was called from",
        options={'SKIP_SAVE'},
        default="OBJECT_MT_setting_presets"  # FIXME: not as default
        )

    def execute(self, context):
        from os.path import basename, splitext
        filepath = self.filepath

        # change the menu title to the most recently chosen option
        preset_class = getattr(bpy.types, self.menu_idname)
        preset_class.bl_label = bpy.path.display_name(basename(filepath))
        nb = bpy.context.scene.nb
        nb.settingprops.sp_presetlabel = preset_class.bl_label

        ext = splitext(filepath)[1].lower()

        # execute the preset using script.python_file_run
        if ext == ".py":
#             bpy.ops.script.python_file_run(override, filepath=filepath)
            # NOTE: override because of RuntimeError on running from headless
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    override = bpy.context.copy()
                    override['area'] = area
                    bpy.ops.script.python_file_run(override, filepath=filepath)
                    break
        elif ext == ".xml":
            import rna_xml
            rna_xml.xml_file_run(context,
                                 filepath,
                                 preset_class.preset_xml_map)
        else:
            self.report({'ERROR'}, "unknown filetype: %r" % ext)
            return {'CANCELLED'}

        return {'FINISHED'}



class AddPresetNeuroBlenderSettings(AddPresetBase, Operator):
    bl_idname = "nb.setting_presets"
    bl_label = "NeuroBlender Setting Presets"
    bl_description = "Add/Delete a NeuroBlender Settings Preset"
    preset_menu = "OBJECT_MT_setting_presets"

    preset_defines = ["scn = bpy.context.scene",
                      "nb = scn.nb"]
    preset_values = ["nb.settingprops.projectdir",
                     "nb.settingprops.esp_path",
                     "nb.settingprops.mode",
                     "nb.settingprops.engine",
                     "nb.settingprops.camera_rig",
                     "nb.settingprops.texformat",
                     "nb.settingprops.texmethod",
                     "nb.settingprops.uv_resolution",
                     "nb.settingprops.advanced",
                     "nb.settingprops.verbose"]
    preset_subdir = "neuroblender_settings"
