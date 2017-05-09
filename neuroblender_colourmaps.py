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


"""The NeuroBlender colourmap module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements the colourmap system for NeuroBlender.
"""


# =========================================================================== #


import os
from glob import glob

import bpy

from bpy.props import (StringProperty,
                       FloatProperty)
from bpy.types import (Menu,
                       Operator,
                       PropertyGroup)
from bl_operators.presets import (AddPresetBase,
                                  ExecutePreset)

from . import neuroblender_utils as nb_utils
from . import neuroblender_import as nb_imp

# =========================================================================== #


class OBJECT_MT_colourmap_presets(Menu):
    bl_label = "Colourmap Presets"
    bl_description = "Choose a NeuroBlender Colourmap Preset"
    preset_subdir = "neuroblender_cmaps"
    preset_operator = "script.execute_preset_cr"
    draw = Menu.draw_preset


class ExecutePreset_CR(ExecutePreset, Operator):
    """Execute a preset"""
    bl_idname = "script.execute_preset_cr"
    bl_label = "NeuroBlender Colourmap Presets"
    bl_description = "Load a NeuroBlender Colourmap Preset"

    filepath = StringProperty(
            subtype='FILE_PATH',
            options={'SKIP_SAVE'},
            )
    menu_idname = StringProperty(
             name="Menu ID Name",
            description="ID name of the menu this was called from",
            options={'SKIP_SAVE'},
            default="OBJECT_MT_colourmap_presets"  # FIXME: not as default
            )
    cr_path = StringProperty(name="CR path",
            description="Data path to colour ramp",
            options={'SKIP_SAVE'})

    def execute(self, context):
        from os.path import basename, splitext
        filepath = self.filepath


        cre, crrange = self.get_elements(context)
        n_new = self.get_number_of_elements()
        self.equalize_elements(cre, n_new)

        # change the menu title to the most recently chosen option
        preset_class = getattr(bpy.types, self.menu_idname)
        preset_class.bl_label = bpy.path.display_name(basename(filepath))

        ext = splitext(filepath)[1].lower()

        # execute the preset using script.python_file_run
        if ext == ".py":
            bpy.ops.script.python_file_run(filepath=filepath)
        elif ext == ".xml":
            import rna_xml
            rna_xml.xml_file_run(context,
                                 filepath,
                                 preset_class.preset_xml_map)
        else:
            self.report({'ERROR'}, "unknown filetype: %r" % ext)
            return {'CANCELLED'}

        self.restore_range(cre, crrange)

        return {'FINISHED'}

    def get_elements(self, context):
        """Get the colour ramp elements."""

        scn = context.scene
        nb = scn.nb

        try:
            cr = eval(self.cr_path)
        except SyntaxError:
            cr = eval(nb.cr_path)

        cre = cr.elements

        if nb.cr_keeprange:
            crrange = [cre[0].position, cre[-1].position]
        else:
            crrange = [0, 1]

        return cre, crrange

    def equalize_elements(self, cre, n_new):
        """Prepare the colour ramp for receiving n_new elements."""

        n_current = len(cre)

        if n_new > n_current:
            for i in range(n_current, n_new):
                cre.new(i)
        elif n_new < n_current:
            for i in range(n_current, n_new, -1):
                cre.remove(cre[i-1])

    def get_number_of_elements(self):
        """Peek how many elements should be in cmap."""

        with open(self.filepath) as f:
            lines = f.readlines()
            el = lines[-1].split('.')[0]
            n_new = int(el.split('[')[-1].split(']')[0]) + 1

        return n_new

    def restore_range(self, cre, crrange):
        """Restore the range of the colour ramp."""

        # FIXME: this does not account for preset cmaps
        # that do not range from 0 to 1
        crdiff = crrange[1] - crrange[0]
        for el in cre:
            el.position = crrange[0] + el.position * crdiff


class AddPresetNeuroBlenderColourmap(AddPresetBase, Operator):
    bl_idname = "nb.colourmap_presets"
    bl_label = "NeuroBlender Colourmap Presets"
    bl_description = "Add/Delete a NeuroBlender Colourmap Preset"
    preset_menu = "OBJECT_MT_colourmap_presets"

    preset_subdir = "neuroblender_cmaps"

    @property
    def preset_defines(self):

        scn = bpy.context.scene
        nb = scn.nb
        cr = eval(nb.cr_path)
        cre = cr.elements

        preset_defines = ["scn = bpy.context.scene",
                          "nb = scn.nb",
                          "cr = eval(nb.cr_path)",
                          "cre = cr.elements"]

        return preset_defines

    @property
    def preset_values(self):

        scn = bpy.context.scene
        nb = scn.nb
        cr = eval(nb.cr_path)
        cre = cr.elements

        preset_values = ["scn.nb.cr_keeprange",
                         "cr.color_mode",
                         "cr.interpolation",
                         "cr.hue_interpolation"]

        for i, el in enumerate(cre):
            preset_values.append("cre[{}].position".format(i))
            preset_values.append("cre[{}].color".format(i))

        return preset_values


class ResetColourmaps(Operator):
    bl_idname = "nb.reset_colourmaps"
    bl_label = "Reset NeuroBlender Colourmap Presets"
    bl_description = "Reset all NeuroBlender Colourmap Presets to defaults"
    bl_options = {"REGISTER"}

    name = StringProperty(
        name="Name",
        default="foo")

    def execute(self, context):

        crrange = [0, 1]
        crdiff = crrange[1] - crrange[0]

        cmdictlist = [
            {"name": "grey",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (0, 0, 0, 0)},
                          {"position": crrange[1],
                           "color": (1, 1, 1, 1)}]},
            {"name": "jet",
             "color_mode": "HSV",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (0, 0, 1, 0)},
                          {"position": crrange[1],
                           "color": (1, 0, 0, 1)}]},
            {"name": "hsv",
             "color_mode": "HSV",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (1, 0, 0.000, 0)},
                          {"position": crrange[1],
                           "color": (1, 0, 0.001, 1)}]},
            {"name": "hot",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (0, 0, 0, 0.0000)},
                          {"position": crrange[0] + 0.3333 * crdiff,
                           "color": (1, 0, 0, 0.3333)},
                          {"position": crrange[0] + 0.6667 * crdiff,
                           "color": (1, 1, 0, 0.6667)},
                          {"position": crrange[1],
                           "color": (1, 1, 1, 1.0000)}]},
            {"name": "cool",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (0, 1, 1, 0)},
                          {"position": crrange[1],
                           "color": (1, 0, 1, 1)}]},
            {"name": "spring",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (1, 0, 1, 0)},
                          {"position": crrange[1],
                           "color": (1, 1, 0, 1)}]},
            {"name": "summer",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (0, 0.216, 0.133, 0)},
                          {"position": crrange[1],
                           "color": (1, 1.000, 0.133, 1)}]},
            {"name": "autumn",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (1, 0, 0, 0)},
                          {"position": crrange[1],
                           "color": (1, 1, 0, 1)}]},
            {"name": "winter",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (0, 0, 1.000, 0)},
                          {"position": crrange[1],
                           "color": (0, 1, 0.216, 1)}]},
            {"name": "parula",
             "color_mode": "RGB",
             "interpolation": "LINEAR",
             "hue_interpolation": "FAR",
             "elements": [{"position": crrange[0],
                           "color": (0.036, 0.023, 0.242, 0.0)},
                          {"position": crrange[0] + 0.2 * crdiff,
                           "color": (0.005, 0.184, 0.708, 0.2)},
                          {"position": crrange[0] + 0.4 * crdiff,
                           "color": (0.002, 0.402, 0.533, 0.4)},
                          {"position": crrange[0] + 0.6 * crdiff,
                           "color": (0.195, 0.521, 0.202, 0.6)},
                          {"position": crrange[0] + 0.8 * crdiff,
                           "color": (0.839, 0.485, 0.072, 0.8)},
                          {"position": crrange[1],
                           "color": (0.947, 0.965, 0.004, 1.0)}]}
                      ]

        scn = context.scene
        nb = scn.nb

        show_manage_colourmaps = nb.show_manage_colourmaps

        # this will generate dummy texture and set nb.cr_path
        nb.show_manage_colourmaps = not show_manage_colourmaps
        nb.show_manage_colourmaps = True

        tex = bpy.data.textures['manage_colourmaps']
        for cmdict in cmdictlist:
            self.replace_colourmap(tex.color_ramp, cmdict)
            bpy.ops.nb.colourmap_presets(name=cmdict["name"])

        info = ['all original colour maps have been reset to default values']
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def replace_colourmap(self, cr, cmdict):

        cr.color_mode = cmdict["color_mode"]
        cr.interpolation = cmdict["interpolation"]
        cr.hue_interpolation = cmdict["hue_interpolation"]

        cre = cr.elements
        while len(cre) > 1:
            cre.remove(cre[0])

        cre[0].position = cmdict["elements"][0]["position"]
        cre[0].color = cmdict["elements"][0]["color"]
        for elem in cmdict["elements"][1:]:
            el = cre.new(elem["position"])
            el.color = elem["color"]


class ColorRampProperties(PropertyGroup):
    """Custom properties of color ramps."""

    name = StringProperty(
        name="Name",
        description="The name of the color stop",
        update=nb_utils.update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    nn_position = FloatProperty(
        name="nn_position",
        description="The non-normalized position of the color stop",
        default=0,
        precision=4)

    def calc_nn_position(self, position, range):
        """Calculate the non-normalized positions of elements."""

        dmin = range[0]
        dmax = range[1]
        drange = dmax-dmin
        self.nn_position = position * drange + dmin


def colourmap_enum_callback(self, context):
    """Populate the enum based on available options."""

    def order_cmaps(mapnames, pref_order):
        """Order a list starting with with a prefered ordering."""

        mapnames_ordered = []
        for mapname in pref_order:
            if mapname in mapnames:
                mapnames_ordered.append(mapname)
                mapnames.pop(mapnames.index(mapname))
        if mapnames:
            mapnames_ordered += mapnames

        return mapnames_ordered

    cmap_dir = os.path.join("presets","neuroblender_cmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    files = glob(os.path.join(preset_path, '*.py'))

    mapnames = [os.path.splitext(os.path.basename(f))[0]
                for i, f in enumerate(files)]

    pref_order = ["grey", "jet", "hsv", "hot", "cool", 
                  "spring", "summer", "autumn", "winter",
                  "parula"]
    mapnames = order_cmaps(mapnames, pref_order)

    items = []
    for i, mapname in enumerate(mapnames):
        displayname = bpy.path.display_name(mapname)
        items.append((mapname, displayname, "", i))

    return items


def colourmap_enum_update(self, context):
    """Assign a new colourmap to the object."""

    scn = context.scene
    nb = scn.nb

    nb_ob = nb_utils.active_nb_object()[0]
    if hasattr(nb_ob, 'slicebox'):
        cr = bpy.data.textures[self.name].color_ramp
        cr_parentpath = 'bpy.data.textures["{}"]'.format(self.name)
    else:
        if hasattr(nb_ob, "nstreamlines"):
            ng = bpy.data.node_groups.get("TractOvGroup")
            cr = ng.nodes["ColorRamp"].color_ramp
            ng_path = 'bpy.data.node_groups["TractOvGroup"]'
            # FIXME: include self.name
            cr_parentpath = '{}.nodes["ColorRamp"]'.format(ng_path)
        elif hasattr(nb_ob, "sphere"):
            nt = bpy.data.materials[self.name].node_tree
            cr = nt.nodes["ColorRamp"].color_ramp
            nt_path = 'bpy.data.materials["{}"].node_tree'.format(self.name)
            cr_parentpath = '{}.nodes["ColorRamp"]'.format(nt_path)

    colourmap = self.colourmap_enum

    # load preset
    cr_path = '{}.color_ramp'.format(cr_parentpath)
    nb.cr_path = cr_path
    menu_idname = "OBJECT_MT_colourmap_presets"

    cmap_dir = os.path.join("presets","neuroblender_cmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    filepath = os.path.join(preset_path, '{}.py'.format(colourmap))

    bpy.ops.script.execute_preset_cr(filepath=filepath,
                                     menu_idname=menu_idname,
                                     cr_path=cr_path)


def managecmap_update(self, context):
    """Generate/delete dummy objects to manage colour maps."""

    scn = context.scene
    nb = scn.nb

    def gen_dummies(name="manage_colourmaps"):

        cube = nb_imp.voxelvolume_box_ob([2,2,2], "SliceBox")
        cube.hide = cube.hide_render = True
        cube.name = cube.data.name = name
        bpy.data.materials.new(name)
        mat = bpy.data.materials.get(name)
        mat.volume.density = 0

        bpy.data.textures.new(name, type='DISTORTED_NOISE')
        tex = bpy.data.textures.get(name)
        tex.use_preview_alpha = True
        tex.use_color_ramp = True

        texslot = mat.texture_slots.add()
        texslot.texture = tex

        texslot.use_map_density = True
        texslot.texture_coords = 'ORCO'
        texslot.use_map_emission = True

        cube.data.materials.append(mat)

    def del_dummies(name="manage_colourmaps"):

        tex = bpy.data.textures.get(name)
        bpy.data.textures.remove(tex)
        mat = bpy.data.materials.get(name)
        bpy.data.materials.remove(mat)
        me = bpy.data.meshes.get(name)
        bpy.data.meshes.remove(me)

    name="manage_colourmaps"

    if self.show_manage_colourmaps:
        gen_dummies(name)

        # FIXME: this is unsafe
        cr_parentpath = "bpy.data.textures['{}']".format(name)
        cr_path = '{}.color_ramp'.format(cr_parentpath)
        context.scene.nb.cr_path = cr_path

        # load preset
        cr_path = '{}.color_ramp'.format(cr_parentpath)
        nb.cr_path = cr_path
        menu_idname = "OBJECT_MT_colourmap_presets"

        preset_class = getattr(bpy.types, menu_idname)
        preset_class.bl_label = bpy.path.display_name(basename(filepath))

    else:
        del_dummies(name)


def calc_nn_elpos(nb_ov, ramp):
    """Calculate the non-normalized positions of elements."""

    def equalize_elements(nnels, n_els):
        """Prepare the listobject for displaying n_new elements."""

        n_nnels = len(nnels)

        if n_els > n_nnels:
            for _ in range(n_els - n_nnels):
                nnels.add()
        elif n_els < n_nnels:
            for _ in range(n_nnels - n_els):
                nnels.remove(0)

    els = ramp.color_ramp.elements
    nnels = nb_ov.nn_elements

    equalize_elements(nnels, len(els))

    for i, el in enumerate(nnels):
        el.calc_nn_position(els[i].position, nb_ov.range)

