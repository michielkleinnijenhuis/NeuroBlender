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
from bpy.types import PropertyGroup as pg
from bpy.types import (Operator,
                       OperatorFileListElement,
                       UIList)
from bpy.props import (BoolProperty,
                       StringProperty,
                       IntProperty,
                       FloatProperty,
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

        split_path = self.data_path.split('.')
        nb_ob = scn.path_resolve('.'.join(split_path[:2]))
        nb_ov = scn.path_resolve('.'.join(split_path[:3]))
        item = scn.path_resolve(self.data_path)

        try:
            pg_sc1 = bpy.types.VoxelvolumeProperties
        except AttributeError:
            pg_sc1 = pg.bl_rna_get_subclass_py("VoxelvolumeProperties")

        if isinstance(nb_ob, pg_sc1):
            tex = bpy.data.textures[nb_ov.name]
            el_idx = nb_ov.labels.find(item.name) + 1
            el = tex.color_ramp.elements[el_idx]
            el.color = item.colour
        else:
            mat = bpy.data.materials[item.name]
            rgb = mat.node_tree.nodes["RGB"]
            rgb.outputs[0].default_value = item.colour
            trans = mat.node_tree.nodes["Transparency"]
            trans.outputs[0].default_value = item.colour[3]

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_item = nb_ut.active_nb_overlayitem()[0]
        self.data_path = nb_item.path_from_id()

        return self.execute(context)


class NB_OT_create_labelgroup(Operator):
    bl_idname = "nb.create_labelgroup"
    bl_label = "Label tracts"
    bl_description = "Divide an object into clusters"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    qb_points = IntProperty(
        name="Points",
        description="Resample the streamlines to N points",
        default=50,
        min=2)

    qb_threshold = FloatProperty(
        name="Threshold",
        description="Set the threshold for QuickBundles",
        default=30.,
        min=0.)

    qb_centroids = BoolProperty(
        name="Centroids",
        description="Create a QuickBundles centroids object",
        default=False)

    qb_separation = BoolProperty(
        name="Separate",
        description="Create a tract object for every QuickBundles cluster",
        default=False)

    def draw(self, context):

        row = self.layout.row()
        row.prop(self, "qb_points")

        row = self.layout.row()
        row.prop(self, "qb_threshold")

        row = self.layout.row()
        row.prop(self, "qb_centroids")

        row = self.layout.row()
        row.prop(self, "qb_separation")

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        split_path = self.data_path.split('.')
        nb_ob = scn.path_resolve('.'.join(split_path[:2]))
        obinfo = nb_ut.get_nb_objectinfo(nb_ob.name)
        name = nb_ob.name
        ob = bpy.data.objects[name]

        streamlines = self.splines_to_streamlines(ob)
        clusters = self.quickbundles(streamlines)
        nb_ob = self.qb_labelgroup(ob, nb_ob, clusters)

        if self.qb_centroids:
            cob, nb_cob = self.qb_centroids_import(context, ob, clusters)
            self.qb_labelgroup(cob, nb_cob, clusters, centroid=True)

        if self.qb_separation:
            bpy.ops.nb.separate_labels(
                data_path=nb_ob.path_from_id(),
                )

        return {"FINISHED"}

    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)

    def quickbundles(self, streamlines):
        """Segment tract with QuickBundles."""

        # TODO: implement other metrics
        try:
            from dipy.segment.clustering import QuickBundles
            from dipy.segment.metric import ResampleFeature
            from dipy.segment.metric import AveragePointwiseEuclideanMetric
        except ImportError:
            return None
        else:

            feature = ResampleFeature(nb_points=self.qb_points)
            metric = AveragePointwiseEuclideanMetric(feature=feature)
            qb = QuickBundles(threshold=self.qb_threshold, metric=metric)
            clusters = qb.cluster(streamlines)

        return clusters

    def splines_to_streamlines(self, ob):
        """Read curve object splines into list of numpy streamlines."""

        streamlines = []
        for spl in ob.data.splines:
            streamline = []
            for point in spl.points:
                slpoint = list(point.co[:3])
                slpoint.append(point.radius)
                slpoint.append(spl.material_index)
                slpoint.append(point.weight)
                streamline.append(slpoint)
            streamlines.append(np.array(streamline))

        return streamlines

    def qb_centroids_import(self, context, ob, clusters):
        """Import a tract objects for QuickBundles centroids."""

        cname = '{}.centroids'.format(ob.name)

        centroids = [cluster.centroid for cluster in clusters]

        it_class = nb_it.NB_OT_import_tracts
        create_tract_object = it_class.create_tract_object
        tract_to_nb = it_class.tract_to_nb
        add_streamlines = it_class.add_streamlines
        beautification = it_class.beautification

        cob = create_tract_object(context, cname)
        nb_cob, info = tract_to_nb(context, cob)
        add_streamlines(cob, centroids)
        nb_ma.materialise(cob, matname=cname, idx=0)
        argdict = {"mode": ob.data.fill_mode,
                   "depth": ob.data.bevel_depth,
                   "res": ob.data.bevel_resolution}
        beautification(cob, argdict)
        cob.matrix_world = ob.matrix_world

        self.report({'INFO'}, info)

        return cob, nb_cob

    def qb_labelgroup(self, ob, nb_ob,
                      clusters=None, centroid=False):
        """Create a labelgroup from QuickBundles clusters."""

        name = '{}.qb'.format(nb_ob.name)

        # TODO: remove/store previous material_slots...
        matgroup = [(cluster.id + 1,
                     '{}.cluster{:05d}'.format(name, cluster.id))
                    for cluster in clusters]
        for _ in range(1, len(ob.data.materials)):
            ob.data.materials.pop(1)
        for i, matname in matgroup:
            nb_ma.materialise(ob, matname=matname, idx=i, mode='append')

        it_class = nb_it.NB_OT_import_tracts
        labelgroup_to_nb = it_class.labelgroup_to_nb
        labelgroup = labelgroup_to_nb(name, nb_ob, matgroup)

        self.set_material_indices(ob, clusters, labelgroup, centroid)

        return labelgroup

    def set_material_indices(self, ob, clusters, lg, centroid=False):
        """Set the material indices according to cluster id's."""

        splines = ob.data.splines
        lab_idxs = np.zeros(len(splines), dtype='int')
        mat_idxs = np.zeros(len(splines))
        for i, cluster in enumerate(clusters):
            if centroid:
                mat_idxs[i] = cluster.id + 1
                lab_idxs[i] = cluster.id
            else:
                mat_idxs[cluster.indices] = cluster.id + 1
                lab_idxs[cluster.indices] = cluster.id

        it = zip(splines, mat_idxs, lab_idxs)
        for i, (spl, mat_idx, lab_idx) in enumerate(it):
            spl.material_index = mat_idx
            splidx = lg.labels[lab_idx].spline_indices.add()
            splidx.spline_index = i


class NB_OT_separate_labels(Operator):
    bl_idname = "nb.separate_labels"
    bl_label = "Separate labels"
    bl_description = "Separate the object by it's labels"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    duplicate = BoolProperty(
        name="Duplicate",
        description="Retain a copy of the original object",
        default=True)

    def draw(self, context):

        row = self.layout.row()
        row.prop(self, "duplicate")

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        split_path = self.data_path.split('.')
        nb_ob = scn.path_resolve('.'.join(split_path[:2]))
        obinfo = nb_ut.get_nb_objectinfo(nb_ob.name)
        labelgroup = scn.path_resolve(self.data_path)

        bpy.ops.object.select_all(action='DESELECT')

        ob = bpy.data.objects[nb_ob.name]
        ob.select = True
        bpy.context.scene.objects.active = ob

        # FIXME: make sure of material assignment according to labels in labelgroup

        if obinfo['type'] == 'tracts':
            obs = self.separate_labels_tracts(context, ob, nb_ob)
        elif obinfo['type'] == 'surfaces':
            bpy.ops.object.duplicate()
            obs = self.separate_labels_surfaces(context, labelgroup)

        # group under empty
        sepname = '{}.separated'.format(ob.name)
        empty = bpy.data.objects.new(sepname, None)
        scn.objects.link(empty)
        for ob in obs:
            ob.parent = empty

        if not self.duplicate:
            bpy.ops.nb.nblist_ops(action="REMOVE_L1",
                                  data_path='.'.join(split_path[:2]))

        return {"FINISHED"}

    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)

    def separate_labels_tracts(self, context, ob, nb_ob):
        """Separate tract labels according to material index."""

        it_class = nb_it.NB_OT_import_tracts
        beautification = it_class.beautification
        argdict = {"mode": ob.data.fill_mode,
                   "depth": ob.data.bevel_depth,
                   "res": ob.data.bevel_resolution}

        obs = []
        for i, ms in enumerate(ob.material_slots):

            if i == 0:
                # TODO: unassigned
                continue

            mat = ms.material
            it_class = nb_it.NB_OT_import_tracts
            create_tract_object = it_class.create_tract_object
            ms_ob = create_tract_object(context, mat.name)
            beautification(ms_ob, argdict)
            ms_ob.data.materials.append(mat)
            obs.append(ms_ob)

            for spl in ob.data.splines:
                if spl.material_index == i:
                    polyline = ms_ob.data.splines.new('POLY')
                    self.copy_spline(spl, polyline)

            tract_to_nb = nb_it.NB_OT_import_tracts.tract_to_nb
            tract_to_nb(context, ms_ob,
                        nb_ob.filepath,
                        nb_ob.sformfile,
                        nb_ob.tract_weeded,
                        nb_ob.streamlines_interpolated)

        return obs

    def copy_spline(self, spline, newspline):
        """Copy over a POLY spline."""

        newspline.points.add(len(spline.points) - 1)
        for point, newpoint in zip(spline.points, newspline.points):
            newpoint.co = point.co
            newpoint.radius = point.radius
            newpoint.weight = point.weight

    def separate_labels_surfaces(self, context, labelgroup):
        """Separate surface labels according to material."""

        # separate
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT')

        obs = bpy.context.selected_objects
        # rename new objects
        for ob in obs:
            name = ob.data.materials[0].name

            if name == ob.name:
                name = '{}.unassigned'.format(labelgroup.name)
                mat = ob.data.materials[0].copy()
                mat.name = name
                ob.data.materials[0] = mat

            ob.name = ob.data.name = name

            for vg in ob.vertex_groups:
                ob.vertex_groups.remove(vg)

            props = {"name": name}  # FIXME: check name
            surface_to_nb = nb_is.NB_OT_import_surfaces.surface_to_nb
            surface_to_nb(context, props, ob)

            obs.append(ob)

        return obs


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
            mat = bpy.data.materials[self.matname]
            nodes = mat.node_tree.nodes
            nodes["Attribute"].attribute_name = self.itemname
            for vc in ob.data.vertex_colors:
                vc.active_render = vc.name == scalar.name

        elif hasattr(group, 'labels'):
            vgs = [ob.vertex_groups[label.name] for label in group.labels]
            ob = nb_ma.assign_vc(ob, vc, vgs, group, colour=[0.5, 0.5, 0.5])

#         bpy.ops.object.mode_set(mode="VERTEX_PAINT")

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        nb_ov = nb_ut.active_nb_overlay()[0]
        nb_item = nb_ut.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels

        self.data_path = nb_item.path_from_id()

        self.itemname = nb_item.name
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
        nb_item = nb_ut.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels
        self.data_path = nb_item.path_from_id()
        self.itemname = nb_item.name
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
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    name_sphere = StringProperty(
        name="Name",
        description="Specify a name for the sphere object",
        default="sphere")
    delete_sphere = BoolProperty(
        name="Delete",
        description="Delete sphere object after unwrapping",
        default=True)
    directory = StringProperty(subtype="FILE_PATH")
    filename = StringProperty()
    filter_glob = StringProperty(
        options={"HIDDEN"},
        # NOTE: multiline comment """ """ not working here
        default="*.obj;*.stl;" +
                "*.gii;" +
                "*.white;*.pial;*.inflated;*.sphere;*.orig;" +
                "*.blend")

    def draw(self, context):

        row = self.layout.row()
        row.prop(self, "delete_sphere")

        if not self.delete_sphere:
            row = self.layout.row()
            row.prop(self, "name_sphere")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_ob = scn.path_resolve(self.data_path)
        surf = bpy.data.objects[nb_ob.name]

        if self.filename:
            bpy.ops.nb.import_surfaces(directory=self.directory,
                                       files=[{"name": self.filename}],
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

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}
