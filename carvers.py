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


"""The NeuroBlender carvers module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements carvers that slice through NeuroBlender objects.
"""


import numpy as np
from mathutils import Vector

import bpy
from bpy.types import (Operator,
                       UIList,
                       Menu)
from bpy.props import (StringProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       IntProperty)

from . import (materials as nb_ma,
               renderpresets as nb_rp,
               utils as nb_ut)


class ImportCarver(Operator):
    bl_idname = "nb.import_carvers"
    bl_label = "New carver"
    bl_description = "Create a new carver"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the carver",
        default="Carver")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_colls = [nb.surfaces, nb.voxelvolumes]
        ca = [nb_ob.carvers
              for nb_coll in nb_colls
              for nb_ob in nb_coll]
        ca += [bpy.data.groups]
        name = nb_ut.check_name(self.name, "", ca)

        nb_ob = scn.path_resolve(self.parentpath)
        obinfo = nb_ut.get_nb_objectinfo(nb_ob.name)
        ob = bpy.data.objects.get(nb_ob.name)

        props = {"name": name}
        carver = nb_ut.add_item(nb_ob, "carvers", props)
        nb_ob.carvers_enum = carver.name

        mat = bpy.data.materials.get('wire') or \
            self.get_wire_material('wire')

        box = self.create_carvebox(context, carver.name, ob,
                                   mat, obinfo['layer'])

        if obinfo['type'] == 'voxelvolumes':
            self.mappingbounds(context, ob, box, mat=mat)

        scn.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

        infostring = 'added carver "%s" to object "%s"'
        info = [infostring % (name, nb_ob.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        self.parentpath = nb_ob.path_from_id()

        return self.execute(context)

    def create_carvebox(self, context, name, ob, mat=None, layer=2):
        """Create a box to gather carve objects in."""

        bpy.ops.mesh.primitive_cube_add()
        box = context.scene.objects.active

        box.name = box.data.name = name
        box.parent = ob
        loc_ctr = 0.125 * sum((Vector(b) for b in ob.bound_box), Vector())
#         glob_ctr = ob.matrix_world * loc_ctr
        box.location = loc_ctr
        box.scale = ob.dimensions / 2

        if isinstance(mat, bpy.types.Material):
            box.data.materials.append(mat)

        box.data.show_faces = False
        box.hide = True
        box.hide_select = False
        box.hide_render = True

        group = bpy.data.groups.new(name)
        group.objects.link(box)

        self.add_boolmod(box.name, ob, box, 'BMESH', 'INTERSECT')

        nb_ut.move_to_layer(box, layer)

        return box

    def mappingbounds(self, context, ob, box, dims=[256, 256, 256],
                      mat=None, layer=5):
        """Create an array of cubes at the voxelvolume's corners."""

        name = "{}.bounds".format(box.name)
        scale = [1./dim for dim in dims]
        location = [-1 + sc for sc in scale]

        bpy.ops.mesh.primitive_cube_add(location=location)
        bounds = context.scene.objects.active

        bounds.name = bounds.data.name = name
        bounds.scale = scale
        bounds.parent = box

        if isinstance(mat, bpy.types.Material):
            bounds.data.materials.append(mat)

        bounds.hide = bounds.hide_select = False
        bounds.hide_render = True

        for i, direc in enumerate('xyz'):
            bounds.lock_location[i] = True
            bounds.lock_rotation[i] = True
            bounds.lock_scale[i] = True
            mod = bounds.modifiers.new("array_{}".format(direc), type='ARRAY')
            mod.use_relative_offset = True
            mod.relative_offset_displace[0] = 0
            mod.relative_offset_displace[i] = dims[i] - 1

        self.add_boolmod(name, ob, bounds, 'BMESH', 'UNION')

        nb_ut.move_to_layer(bounds, layer)

        return bounds

    @staticmethod
    def get_wire_material(name='wire'):
        """Create a wire material.

        (BR for now: TODO)
        """

        mat = bpy.data.materials.new(name)
        mat.type = "WIRE"
        mat.diffuse_color = (0.8, 0, 0)
        mat.emit = 1
        mat.use_transparency = True
        mat.alpha = 0.5

        return mat

    @staticmethod
    def add_boolmod(name, par, ob, solver='BMESH', operation='INTERSECT'):
        """Add a boolean modifier."""

        boolmod = par.modifiers.new(name, 'BOOLEAN')
        boolmod.solver = solver
        boolmod.operation = operation
        boolmod.object = ob

        return boolmod


# class OBJECT_MT_colourmap_presets(Menu):
#     bl_label = "Colourmap Presets"
#     bl_description = "Choose a NeuroBlender Colourmap Preset"
#     preset_subdir = "neuroblender_colourmaps"
#     preset_operator = "script.execute_preset_cr"
#     draw = Menu.draw_preset


class ImportCarveObjects(Operator):
    bl_idname = "nb.import_carveobjects"
    bl_label = "New carveobject"
    bl_description = "Create a new carveobject"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the carveobject",
        default="slice")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    carveobject_type_enum = EnumProperty(
        name="Type",
        description="Type of carve object",
        default="slice",
        items=[("slice", "Slice", "Slice", 0),
               ("orthoslices", "Orthogonal slices", "Orthogonal slices", 1),
               ("cube", "Cube", "Cube", 2),
               ("cylinder", "Cylinder", "Cylinder", 3),
               ("sphere", "Sphere", "Sphere", 4),
               ("suzanne", "Suzanne", "Suzanne", 5),
               ("activeob", "Active object", "Active object", 6)])

    def execute(self, context):

        scn = context.scene

        carver = scn.path_resolve(self.parentpath)

        groupname, names = self.get_names(context, carver)
        co_group = bpy.data.groups.get(groupname) or \
            bpy.data.groups.new(groupname)

        for name in names:
            carveob = self.create_carveobject(context, name, carver, co_group)

        # update
        if self.carveobject_type_enum == 'activeob':
            scn.objects.active = bpy.data.objects.get(carver.name).parent
        else:
            scn.objects.active = carveob.parent.parent
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

        infostring = 'added carveobject "%s" in carver "%s"'
        info = [infostring % (name, carver.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        carver = nb_ob.carvers[nb_ob.index_carvers]
        self.parentpath = carver.path_from_id()
        self.carveobject_type_enum = carver.carveobject_type_enum
        self.name = self.carveobject_type_enum

        return self.execute(context)

    def create_carveobject(self, context, name, carver, slicegroup, layer=5):
        """Create a carve object."""

        scn = context.scene

        carveobtype = self.carveobject_type_enum

        carvergroup = bpy.data.groups.get(carver.name)
        carvebox = carvergroup.objects.get(carver.name)

        carveob = self.add_carveobject(context)

        if carveobtype != "activeob":
            carveob.name = carveob.data.name = name
            carveob.parent = carvebox
            nb_ut.move_to_layer(carveob, layer)

        carvergroup.objects.link(carveob)
        slicegroup.objects.link(carveob)

        props = {"name": name, "type": carveobtype}
        if carveobtype == "slice":
            props['slicethickness'] = [0.99, 0.99, 0.05]
        elif carveobtype == "orthoslices":
            props['slicethickness'] = [0.99, 0.99, 0.99]
            props['slicethickness']['xyz'.find(name[-1])] = 0.05
        elif carveobtype == "cylinder":
            props['slicethickness'] = [0.50, 0.50, 1.0]
        elif carveobtype in ("cube", "sphere"):
            props['slicethickness'] = [0.50, 0.50, 0.50]
        elif carveobtype == "activeob":
            props['slicethickness'] = carveob.scale
            props['sliceposition'] = carveob.location
            props['sliceangle'] = carveob.rotation_euler
        co = nb_ut.add_item(carver, "carveobjects", props)
        co.slicethickness = co.slicethickness

        mat = bpy.data.materials.get('wire')
        nb_ma.set_materials(carveob.data, mat)

        carveob.hide = carveob.hide_select = False
        carveob.hide_render = True

        self.add_boolmod(name, carvebox, carveob)

        return carveob

    def add_carveobject(self, context):

        carveobtype = self.carveobject_type_enum

        if carveobtype in ("slice", "orthoslices", "cube"):
            bpy.ops.mesh.primitive_cube_add()
        elif carveobtype == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(vertices=64)
        elif carveobtype == "sphere":
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5)
        elif carveobtype == "suzanne":
            bpy.ops.mesh.primitive_monkey_add(calc_uvs=True)
        elif carveobtype == "activeob":
            pass
        else:
            return

        return context.scene.objects.active

    def get_names(self, context, carver):

        scn = context.scene
        nb = scn.nb

        cotype = self.carveobject_type_enum

        gdict = {"orthoslices": "orthoslices",
                 "activeob": "non-normalized",
                 "slice": "normalized",
                 "cube": "normalized",
                 "cylinder": "normalized",
                 "sphere": "normalized",
                 "suzanne": "normalized"}
        gname = '{}.{}'.format(carver.name, gdict[cotype])

        nb_colls = [nb.surfaces, nb.voxelvolumes]
        item_ca = [carver.carveobjects
                   for nb_coll in nb_colls
                   for nb_ob in nb_coll
                   for carver in nb_ob.carvers]
        group_ca = [bpy.data.groups] if cotype == 'orthoslices' else []
        ca = [group_ca, item_ca]

        funs = [self.fun_groupname, self.fun_itemnames]

        name = '{}.{}'.format(carver.name, self.name)
        gnames, names = nb_ut.compare_names(name, ca, funs,
                                            {'groupname': gname})

        return gnames[0], names

    def fun_groupname(self, name, argdict):
        """Generate overlay group names."""

        names = [argdict['groupname']]

        return names

    def fun_itemnames(self, name, argdict):
        """Generate names."""

        carveobtype = self.carveobject_type_enum

        if carveobtype == "orthoslices":
            names = ['{}.{}'.format(name, direc) for direc in 'xyz']
        elif carveobtype == "activeob":
            names = [bpy.context.scene.objects.active.name]
        else:
            names = [name]

        return names

    @staticmethod
    def add_boolmod(name, par, ob, solver='BMESH', operation='INTERSECT'):
        """Add a boolean modifier."""

        boolmod = par.modifiers.new(name, 'BOOLEAN')
        boolmod.solver = solver
        boolmod.operation = operation
        boolmod.object = ob

        return boolmod


class ObjectListCV(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.settingprops.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListCO(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.settingprops.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


# @deprecated
class DelCarver(Operator):
    bl_idname = "nb.del_carver"
    bl_label = "Delete carver"
    bl_description = "Delete a carver"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify the name of the carver",
        default="")
    index = IntProperty(
        name="index",
        description="Specify carver index",
        default=-1)
    index_presets = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        info = []

        preset = nb.presets[self.index_presets]

        if self.name:  # got here through cli
            try:
                preset.carvers[self.name]
            except KeyError:
                infostring = 'no carvers with name "%s"'
                info = [infostring % self.name]
                self.report({'INFO'}, info[0])
                return {"CANCELLED"}
            else:
                self.index = preset.carvers.find(self.name)
        else:  # got here through invoke
            self.name = preset.carvers[self.index].name

        info = self.delete_carver(preset.carvers[self.index], info)
        preset.carvers.remove(self.index)
        preset.index_carvers -= 1
        infostring = 'removed carver "%s"'
        info = [infostring % self.name] + info

        try:
            name = preset.carvers[0].name
        except IndexError:
            infostring = 'all carvers have been removed'
            info += [infostring]
        else:
            pass
            nb.carvers_enum = name
            infostring = 'carver is now "%s"'
            info += [infostring % name]

        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]
        self.index = preset.index_carvers
        self.name = ""

        return self.execute(context)

    def delete_carver(self, carver, info=[]):
        """Delete a preset."""

        pass
        # delete all carveobjects and data
#         for ps_obname in ps_obnames:
#             try:
#                 ob = bpy.data.objects[ps_obname]
#             except KeyError:
#                 infostring = 'object "%s" not found'
#                 info += [infostring % ps_obname]
#             else:
#                 bpy.data.objects.remove(ob)

        return info


# @deprecated
class DelCarveObject(Operator):
    bl_idname = "nb.del_carveobject"
    bl_label = "Delete carve object"
    bl_description = "Delete a carve object"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index = IntProperty(
        name="index",
        description="Specify carver index",
        default=-1)
    parentpath = StringProperty(
        name="Data path",
        description="The path to the carve object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        info = []

        carver = scn.path_resolve(self.parentpath)
        carverob = bpy.data.objects[carver.name]

        carveob = carver.carveobjects[self.index]

        # FIXME: make sure modifier has the right name
        mod = carverob.modifiers.get(carveob.name)
        carverob.modifiers.remove(mod)

        ob = bpy.data.objects.get(carveob.name)
        bpy.data.objects.remove(ob)

        carver.carveobjects.remove(self.index)
        carver.index_carveobjects -= 1
        infostring = 'removed carve object "%s"'
        info = [infostring % carveob.name] + info

        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        carver = nb_ob.carvers[nb_ob.index_carvers]
        self.parentpath = carver.path_from_id()
        self.index = carver.carveobjects.find(carver.carveobjects_enum)

        return self.execute(context)


# @deprecated
class CopyCarver(Operator):
    bl_idname = "nb.copy_carver"
    bl_label = "Add carver"
    bl_description = "Add a carver to an object"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="index presets",
        description="Specify preset index",
        default=-1)
    name = StringProperty(
        name="Name",
        description="Specify a name for the carver",
        default="Carver")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        preset = nb.presets[nb.index_presets]

        nb_ob = scn.path_resolve(self.parentpath)
        obinfo = nb_ut.get_nb_objectinfo(nb_ob.name)
        ob = bpy.data.objects[nb_ob.name]

        if nb_ob.carvers_enum == 'NEW':
            bpy.ops.nb.import_carvers(index_presets=self.index_presets,
                                      name=self.name)
            carver = preset.carvers[preset.index_carvers]
        else:
            carver = preset.carvers.get(nb_ob.carvers_enum)

        group = bpy.data.groups.get(carver.name)
        box = group.objects.get(carver.name)

        name_new = ob.name + '.{}'
        group_new = bpy.data.groups.new(name_new.format(group.name))

        box_new = box.copy()
        box_new.data = box.data.copy()
        group_new.objects.link(box_new)
        scn.objects.link(box_new)
        box_new.name = box_new.data.name = name_new.format(box.name)
        box_new.parent = ob
        box_new.location = ob.dimensions / 2
        box_new.scale = ob.dimensions / 2

        layerdict = {'tracts': 0, 'surfaces': 1, 'voxelvolumes': 2}
        nb_ut.move_to_layer(box_new, layerdict[obinfo['type']])

        for cob in group.objects:
            if cob.parent == box:
                cob_new = cob.copy()
                cob_new.data = cob.data.copy()
                group_new.objects.link(cob_new)
                scn.objects.link(cob_new)

                cob_new.name = cob_new.data.name = name_new.format(cob.name)
                cob_new.parent = box_new
                box_new.modifiers[cob.name].object = cob_new

#                 cob_new.constraints.new(type='COPY_SCALE')
#                 cns = cob_new.constraints["Copy Scale"]
#                 cns.target = cob
#                 cns.owner_space = 'LOCAL'

                nb_ut.move_to_layer(cob_new, 5)

        if obinfo['type'] == 'voxelvolumes':
            bounds = self.get_mappingbounds(context, box_new, ob.dimensions)
            bounds.name = bounds.data.name = name_new.format("bounds")
            self.add_boolmod('bounds', box_new, bounds, 'BMESH', 'UNION')
            nb_ut.move_to_layer(bounds, 5)

        self.add_boolmod('carver', ob, box_new, 'BMESH', 'INTERSECT')

#         # create an instance ()
#         bpy.ops.mesh.primitive_cube_add()
#         instance = scn.objects.active
#         instance.dupli_type = 'GROUP'
#         instance.dupli_group = group
#         scn.objects.link(instance)
#         instance.parent = ob
#         instance.location = ob.dimensions / 2
#         instance.scale = ob.dimensions / 2

#         carvebox_ob = carvebox.copy()
#         carvebox_ob.data = carvebox.data.copy()
#         carvebox_ob.data.name = carvebox_ob.name = ob.name + carver.name
#         scn.objects.link(carvebox_ob)
#
#         carvebox_ob.parent = ob
#         carvebox_ob.location = ob.dimensions / 2
#         carvebox_ob.scale = ob.dimensions / 2


        # attach to object
        # FIXME: do parenting / scaling / location on attaching it to object
#         carvebox.parent = ob
#         carvebox.location = dims[:3] / 2
#         carvebox.scale = dims[:3] / 2
#         if obinfo['type'] == "voxelvolumes":
#             vvol_bounds = self.get_mappingbounds(context, mat, carvebox)
#             self.carvebox_boolmod("vvol_bounds", carvebox,
#                                   vvol_bounds, 'BMESH', 'UNION')
#         self.carvebox_boolmod("carvebox", ob,
#                               carvebox, 'BMESH', 'INTERSECT')

        infostring = 'added carver "%s" to object "%s"'
        info = [infostring % (carver.name, nb_ob.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets

        nb_ob = nb_ut.active_nb_object()[0]
        self.parentpath = nb_ob.path_from_id()

        return self.execute(context)

    @staticmethod
    def add_boolmod(name, par, ob, solver='BMESH', operation='INTERSECT'):
        """Add a boolean modifier."""

        boolmod = par.modifiers.new(name, 'BOOLEAN')
        boolmod.solver = solver
        boolmod.operation = operation
        boolmod.object = ob

        return boolmod

    @staticmethod
    def get_mappingbounds(context, box, dims=[256, 256, 256]):
        """Create a cube array to form a voxelvolume's fixed mapping bounds."""

        scale = [1./dim for dim in dims]
        location = [-1 + sc for sc in scale]

        bpy.ops.mesh.primitive_cube_add(location=location)
        bounds = context.scene.objects.active

        bounds.parent = box
        bounds.scale = scale

        mat = bpy.data.materials.get('wire')
        bounds.data.materials.append(mat)

        bounds.hide = bounds.hide_select = False
        bounds.hide_render = True

        for i, direc in enumerate('xyz'):
            bounds.lock_location[i] = True
            bounds.lock_rotation[i] = True
            bounds.lock_scale[i] = True
            mod = bounds.modifiers.new("array_{}".format(direc), type='ARRAY')
            mod.use_relative_offset = True
            mod.relative_offset_displace[0] = 0
            mod.relative_offset_displace[i] = dims[i] - 1

        return bounds
