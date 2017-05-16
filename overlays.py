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


"""The NeuroBlender overlays module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements operations on overlays.
"""


import os
import re

import bpy
from bpy.types import (Operator,
                       OperatorFileListElement,
                       UIList)
from bpy.props import (StringProperty,
                       IntProperty,
                       CollectionProperty)
from bpy_extras.io_utils import (ImportHelper,
                                 ExportHelper)

from . import (materials as nb_ma,
               properties as nb_pr,
               utils as nb_ut)


class RevertLabel(Operator):
    bl_idname = "nb.revert_label"
    bl_label = "Revert label"
    bl_description = "Revert changes to imported label colour/transparency"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        item = eval(self.data_path)

        mat = bpy.data.materials[item.name]
        rgb = mat.node_tree.nodes["RGB"]
        rgb.outputs[0].default_value = item.colour
        trans = mat.node_tree.nodes["Transparency"]
        trans.outputs[0].default_value = item.colour[3]

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_it = nb_ut.active_nb_overlayitem()[0]
        self.data_path = nb_it.path_from_id()

        return self.execute(context)


class WeightPaintMode(Operator):
    bl_idname = "nb.wp_preview"
    bl_label = "wp_mode button"
    bl_description = "Go to weight paint mode for preview"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = bpy.context.scene

        nb_ob = nb_ut.active_nb_object()[0]
        scn.objects.active = bpy.data.objects[nb_ob.name]

        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")

        nb_pr.index_scalars_update_func()

        return {"FINISHED"}


class VertexWeight2VertexColors(Operator):
    bl_idname = "nb.vw2vc"
    bl_label = "VW to VC"
    bl_description = "Bake vertex group weights to vertex colours"
    bl_options = {"REGISTER"}

    itemname = StringProperty(
        name="Name",
        description="Specify the vertex group to bake",
        default="")
    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    index = IntProperty(
        name="index",
        description="index",
        default=-1)
    matname = StringProperty(
        name="Name",
        description="Specify the material to bake to",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_ob = eval('.'.join(self.data_path.split('.')[:2]))
        group = eval('.'.join(self.data_path.split('.')[:3]))
        ob = bpy.data.objects[nb_ob.name]

        vcs = ob.data.vertex_colors
        vc = vcs.new(name=self.itemname)
        ob.data.vertex_colors.active = vc

        if hasattr(group, 'scalars'):
            scalar = eval(self.data_path)
            vgs = [ob.vertex_groups[scalar.name]]
            ob = nb_ma.assign_vc(ob, vc, vgs)
            mat = ob.data.materials[self.matname]
            nodes = mat.node_tree.nodes
            nodes["Attribute"].attribute_name = self.itemname

        elif hasattr(group, 'labels'):
            vgs = [ob.vertex_groups[label.name] for label in group.labels]
            ob = nb_ma.assign_vc(ob, vc, vgs, group, colour=[0.5, 0.5, 0.5])

        bpy.ops.object.mode_set(mode="VERTEX_PAINT")

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        nb_ov = nb_ut.active_nb_overlay()[0]
        nb_it = nb_ut.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels

        self.data_path = nb_it.path_from_id()

        self.itemname = nb_it.name
        self.matname = nb_ov.name

        return self.execute(context)


class VertexWeight2UV(Operator, ExportHelper):
    bl_idname = "nb.vw2uv"
    bl_label = "Bake vertex weights"
    bl_description = "Bake vertex weights to texture (via vcol)"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    itemname = StringProperty(
        name="Name",
        description="Specify the vertex group to bake",
        default="")
    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    index = IntProperty(
        name="index",
        description="index",
        default=-1)
    matname = StringProperty(
        name="Name",
        description="Specify the material name for the group",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_ob_path = '.'.join(self.data_path.split('.')[:2])
        nb_ob = scn.path_resolve(nb_ob_path)
        group_path = '.'.join(self.data_path.split('.')[:3])
        group = scn.path_resolve(group_path)

        # cancel if surface is not unwrapped
        if not nb_ob.is_unwrapped:  # surf.data.uv_layers
            return {"CANCELLED"}

        # prep directory
        if not bpy.data.is_saved:
            nb_ut.force_save(nb.settingprops.projectdir)
        if not group.texdir:
            group.texdir = "//uvtex_{}".format(group.name)
        nb_ut.mkdir_p(bpy.path.abspath(group.texdir))

        # set the surface as active object
        surf = bpy.data.objects[nb_ob.name]
        for ob in bpy.data.objects:
            ob.select = False
        surf.select = True
        context.scene.objects.active = surf

        # save old and set new render settings for baking
        engine = scn.render.engine
        scn.render.engine = "CYCLES"
        samples = scn.cycles.samples
        preview_samples = scn.cycles.preview_samples
        scn.cycles.samples = 5
        scn.cycles.preview_samples = 5
        scn.cycles.bake_type = 'EMIT'

        # save old and set new materials for baking
        ami = surf.active_material_index
        matnames = [ms.name for ms in surf.material_slots]
        surf.data.materials.clear()
        uvres = nb.settingprops.uv_resolution
        img = self.create_baking_material(surf, uvres, "bake_vcol")

        # select the item(s) to bake
        dp_split = re.findall(r"[\w']+", self.data_path)
        data_path = "{}.{}".format(group.path_from_id(), dp_split[-2])
        items = scn.path_resolve(data_path)
        if not nb.settingprops.uv_bakeall:
            items = [items[self.index]]

        # bake
        vcs = surf.data.vertex_colors
        for i, item in enumerate(items):
            dp = item.path_from_id()
            bpy.ops.nb.vw2vc(itemname=item.name, data_path=dp,
                             index=i, matname="bake_vcol")
            img.source = 'GENERATED'
            bpy.ops.object.bake()
            if len(items) > 1:
                itemname = item.name[-5:]
            else:
                itemname = item.name
            img.filepath_raw = os.path.join(group.texdir, itemname + ".png")
            img.save()
            vc = vcs[vcs.active_index]
            vcs.remove(vc)

        # reinstate materials and render settings
        surf.data.materials.pop(0)
        for matname in matnames:
            surf.data.materials.append(bpy.data.materials[matname])
        surf.active_material_index = ami
        scn.render.engine = engine
        scn.cycles.samples = samples
        scn.cycles.preview_samples = preview_samples

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        nb_ov = nb_ut.active_nb_overlay()[0]
        nb_it = nb_ut.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels
        self.data_path = nb_it.path_from_id()
        self.itemname = nb_it.name
        self.matname = nb_ov.name

        return self.execute(context)

    @staticmethod
    def create_baking_material(surf, uvres, name):
        """Create a material to bake vertex colours to."""

        mat = nb_ma.make_material_bake_cycles(name)
        surf.data.materials.append(mat)

        nodes = mat.node_tree.nodes
        itex = nodes['Image Texture']
        attr = nodes['Attribute']
        out = nodes['Material Output']

        img = bpy.data.images.new(name, width=uvres, height=uvres)
        img.file_format = 'PNG'
        img.source = 'GENERATED'
        itex.image = img
        attr.attribute_name = name

        for node in nodes:
            node.select = False
        out.select = True
        nodes.active = out

        return img


class UnwrapSurface(Operator):
    bl_idname = "nb.unwrap_surface"
    bl_label = "Unwrap surface"
    bl_description = "Unwrap a surface with sphere projection"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name_surface = StringProperty(
        name="Surface name",
        description="Specify the name for the surface to unwrap",
        default="")
    name_sphere = StringProperty(
        name="Sphere name",
        description="Specify the name for the sphere object to unwrap from",
        default="")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the spherical surface",
        subtype="FILE_PATH")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        surf = bpy.data.objects[self.name_surface]

        if self.name_sphere == "Select":
            directory = os.path.dirname(self.filepath)
            fname = os.path.basename(self.filepath)
            bpy.ops.nb.import_surfaces(filepath=self.filepath,
                                       directory=directory,
                                       files=[{"name": fname, "name": fname}],
                                       name="sphere")
            self.name_sphere = context.scene.objects.active.name

        sphere = bpy.data.objects[self.name_sphere]

        # select sphere and project
        for ob in bpy.data.objects:
            ob.select = False
        sphere.select = True
        scn.objects.active = sphere
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.sphere_project()
        bpy.ops.object.mode_set(mode='OBJECT')
        # TODO: perhaps do scaling here to keep all vertices within range

        # copy the UV map: select surf then sphere
        surf.select = True
        scn.objects.active = sphere
        bpy.ops.object.join_uvs()

        nb_ob = nb.surfaces.get(surf.name)
        nb_ob.is_unwrapped = True

        if nb_ob.sphere == "Select":
            data_path = 'nb.surfaces["{}"]'.format(self.name_sphere)
            bpy.ops.nb.oblist_ops(action='REMOVE_L1', data_path=data_path)

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]

        if nb_ob.sphere == "Select":
            bpy.ops.nb.import_surfaces('INVOKE_DEFAULT')
            self.name_sphere = context.scene.objects.active.name
        else:
            self.name_sphere = nb_ob.sphere

        self.name_surface = nb_ob.name

        return self.execute(context)


class ObjectListTS(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text="Time index:")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)
