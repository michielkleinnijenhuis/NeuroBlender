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

import numpy as np

import bpy
from bpy.types import (Operator,
                       OperatorFileListElement,
                       UIList)
from bpy.props import (BoolProperty,
                       StringProperty,
                       IntProperty,
                       CollectionProperty)
from bpy_extras.io_utils import (ImportHelper,
                                 ExportHelper)

from . import (materials as nb_ma,
               properties as nb_pr,
               utils as nb_ut)
from .imports import (import_tracts as nb_it,
                      import_surfaces as nb_is,
                      import_voxelvolumes as nb_iv)


class NB_OT_revert_label(Operator):
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


class NB_OT_separate_labels(Operator):
    bl_idname = "nb.separate_labels"
    bl_label = "Separate labels"
    bl_description = "Separate a surface by it's labels"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    duplicate = BoolProperty(
        name="Duplicate",
        description="Retain a copy of the original surface",
        default=True)

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        split_path = self.data_path.split('.')
        nb_ob = scn.path_resolve('.'.join(split_path[:2]))
        labelgroup = scn.path_resolve('.'.join(split_path[:3]))

        bpy.ops.object.select_all(action='DESELECT')

        surf = bpy.data.objects[nb_ob.name]
        surf.select = True
        bpy.context.scene.objects.active = surf
        bpy.ops.object.duplicate()

        # FIXME: make sure of material assignment according to labels

        # separate
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT')

        # create empty
        sepname = '{}.separated'.format(surf.name)
        empty = bpy.data.objects.new(sepname, None)
        scn.objects.link(empty)

        # rename new objects
        for ob in bpy.context.scene.objects:
            if ob.select:
                name = ob.data.materials[0].name

                if name == surf.name:
                    name = '{}.unassigned'.format(labelgroup.name)
                    mat = surf.data.materials[0].copy()
                    mat.name = name
                    ob.data.materials[0] = mat

                ob.name = ob.data.name = name
                ob.parent = empty

                for vg in ob.vertex_groups:
                    ob.vertex_groups.remove(vg)

                props = {"name": name}  # FIXME: check name
                surface_to_nb = nb_is.NB_OT_import_surfaces.surface_to_nb
                surface_to_nb(context, props, ob)

        if not self.duplicate:
            bpy.ops.nb.nblist_ops(action="REMOVE_L1",
                                  data_path='.'.join(split_path[:2]))

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ov = nb_ut.active_nb_overlay()[0]
        self.data_path = nb_ov.path_from_id()

        return self.execute(context)


class NB_OT_weightpaint(Operator):
    bl_idname = "nb.weightpaint"
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


class NB_OT_vertexweight_to_vertexcolors(Operator):
    bl_idname = "nb.vertexweight_to_vertexcolors"
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

#         bpy.ops.object.mode_set(mode="VERTEX_PAINT")

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


class NB_OT_vertexweight_to_uv(Operator, ExportHelper):
    bl_idname = "nb.vertexweight_to_uv"
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
    uv_bakeall = BoolProperty(
        name="Bake all",
        description="Bake single or all scalars in a group",
        default=True)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_ob_path = '.'.join(self.data_path.split('.')[:2])
        nb_ob = scn.path_resolve(nb_ob_path)
        group_path = '.'.join(self.data_path.split('.')[:3])
        group = scn.path_resolve(group_path)

        # cancel if surface is not unwrapped
        if not nb_ob.is_unwrapped:  # surf.data.uv_layers
            info = "Surface has not been unwrapped"
            self.report({'ERROR'}, info)
            return {"CANCELLED"}

        # prep directory
        if not bpy.data.is_saved:
            dpath = nb_ut.force_save(nb.settingprops.projectdir)
            if nb.settingprops.verbose:
                infostring = 'Blend-file had not been saved: saved file to {}'
                info = infostring.format(dpath)
                self.report({'INFO'}, info)
        if not group.texdir:
            group.texdir = "//uvtex_{groupname}".format(groupname=group.name)
        abstexdir = bpy.path.abspath(group.texdir)
        nb_ut.mkdir_p(abstexdir)

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
        if not self.uv_bakeall:
            items = [items[self.index]]

        # bake
        vcs = surf.data.vertex_colors
        for i, item in enumerate(items):
            dp = item.path_from_id()
            bpy.ops.nb.vertexweight_to_vertexcolors(
                itemname=item.name, data_path=dp,
                index=i, matname="bake_vcol"
                )
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

        # save the essentials to the texture directory
        texdict = {'datarange': group.range, 'labels': None}
        for pf in ('datarange', 'labels'):
            np.save(os.path.join(abstexdir, pf), np.array(texdict[pf]))

        # reinstate materials and render settings
        surf.data.materials.pop(0)
        for matname in matnames:
            surf.data.materials.append(bpy.data.materials[matname])
        surf.active_material_index = ami
        scn.render.engine = engine
        scn.cycles.samples = samples
        scn.cycles.preview_samples = preview_samples

        # load the texture
        group.texdir = group.texdir
        # TODO: switch to frame 0 on loading single timepoint?

        bpy.ops.object.mode_set(mode="TEXTURE_PAINT")

        if nb.settingprops.verbose:
            infostring = 'Baked {0} textures at {1}x{1} to {2}'
            info = infostring.format(len(items), uvres, abstexdir)
            self.report({'INFO'}, info)

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

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
        self.uv_bakeall = nb.settingprops.uv_bakeall

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


class NB_OT_unwrap_surface(Operator, ImportHelper):
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
    delete_sphere = BoolProperty(
        name="Delete",
        description="Delete sphere object after unwrapping",
        default=True)
    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        # NOTE: multiline comment """ """ not working here
        default="*.obj;*.stl;" +
                "*.gii;" +
                "*.white;*.pial;*.inflated;*.sphere;*.orig;" +
                "*.blend")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        surf = bpy.data.objects[self.name_surface]
        nb_ob = nb.surfaces.get(surf.name)

        if self.files:
            fname = self.files[0].name
            fpath = os.path.join(self.directory, fname)
            bpy.ops.nb.import_surfaces(filepath=fpath,
                                       directory=self.directory,
                                       files=[{"name": fname, "name": fname}],
                                       name=self.name_sphere)
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

        nb_ob.is_unwrapped = True

        if self.delete_sphere:
            data_path = 'nb.surfaces["{}"]'.format(self.name_sphere)
            bpy.ops.nb.nblist_ops(action='REMOVE_L1', data_path=data_path)

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        self.name_surface = nb_ob.name

        if nb_ob.sphere != "Select":
            self.name_sphere = nb_ob.sphere
            self.delete_sphere = False
            return self.execute(context)
        else:
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
