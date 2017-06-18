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


from mathutils import Vector

import bpy
import numpy as np
from bpy.types import (Operator,
                       UIList,
                       Menu)
from bpy.props import (StringProperty,
                       EnumProperty)

from . import (materials as nb_ma,
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

        # get parent info and object
        nb_ob = scn.path_resolve(self.parentpath)
        obinfo = nb_ut.get_nb_objectinfo(nb_ob.name)
        ob = bpy.data.objects.get(nb_ob.name)

        # check name
        nb_colls = [nb.surfaces, nb.voxelvolumes]
        ca = [nb_ob.carvers
              for nb_coll in nb_colls
              for nb_ob in nb_coll]
        ca += [bpy.data.groups, bpy.data.objects, bpy.data.meshes]
        name = '{}.{}'.format(nb_ob.name, self.name)
        name = nb_ut.check_name(name, "", ca)

        # add the carver to carver collection
        props = {"name": name}
        carver = nb_ut.add_item(nb_ob, "carvers", props)
        nb_ob.carvers_enum = carver.name

        # create the carver
        self.create_carvebox(context, carver.name, ob, nb_ob, obinfo['layer'])

        # hide the parent object
        nb_ob.is_rendered = False
        ob.hide = ob.hide_render = True

        infostring = 'added carver "%s" to object "%s"'
        info = [infostring % (name, nb_ob.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_ut.active_nb_object()[0]
        self.parentpath = nb_ob.path_from_id()

        return self.execute(context)

    def create_carvebox(self, context, name, ob, nb_ob, layer=2):
        """Create a box to gather carve objects in."""

        scn = context.scene

        # add carvebox
        bpy.ops.mesh.primitive_cube_add()
        box = scn.objects.active
        box.name = box.data.name = name

        # scale and move to overlap with object
        loc_ctr = 0.125 * sum((Vector(b) for b in ob.bound_box), Vector())
        glob_ctr = ob.matrix_world * loc_ctr
        pts = [v.co for v in ob.data.vertices]
        datamin = np.amin(np.array(pts), axis=0)
        datamax = np.amax(np.array(pts), axis=0)
        dims = datamax - datamin
        box.scale = dims / 2
        box.location = glob_ctr

        # attach texture mapping (vvol) or boolean (surf)
        ms = ob.material_slots.get(ob.name)
        mat = ms.material
        if isinstance(nb_ob, bpy.types.VoxelvolumeProperties):
            ts = mat.texture_slots.get(ob.name)
            ts.texture_coords = 'OBJECT'
            ts.object = ob
        elif isinstance(nb_ob, bpy.types.SurfaceProperties):
            self.add_boolmod(ob.name, box, ob, 'BMESH', 'INTERSECT')

        if isinstance(mat, bpy.types.Material):
            box.data.materials.append(mat)

        # prevent the user from controlling the carver from the viewport
        box.hide_select = True
        for i, _ in enumerate('xyz'):
            box.lock_location[i] = True
            box.lock_rotation[i] = True
            box.lock_scale[i] = True

        # let the carvebox follow the parent object
        cns = box.constraints.new(type='CHILD_OF')
        cns.target = ob
        cns.inverse_matrix = ob.matrix_world.inverted()

        # add to group and move to layer
        group = bpy.data.groups.new(name)
        group.objects.link(box)
        nb_ut.move_to_layer(box, layer)

        bpy.context.scene.objects.active = box
        nb_ut.force_object_update(context, box)

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

        bounds.hide = bounds.hide_select = bounds.hide_render = True

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
#         bpy.data.node_groups["Shader Nodetree"].nodes["Material"].inputs[0].default_value = (0.8, 0, 0, 1)
#         bpy.context.object.active_material.use_nodes = False

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
            self.create_carveobject(context, name, carver, co_group)

#         ob = bpy.data.objects.get(carver.name).parent
        ob = bpy.data.objects.get(carver.name)
        nb_ut.force_object_update(context, ob)

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

        op = 'UNION' if carver.index_carveobjects else 'INTERSECT'
        self.add_boolmod(name, carvebox, carveob, operation=op)

#         scn.objects.active = carvebox
#         cmods = carvebox.modifiers
#         while cmods.find('wire') in range(0, len(cmods) - 1):
#             bpy.ops.object.modifier_move_down(modifier="wire")

        scn.objects.active = carvebox.parent

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

        # FIXME: check against all modifier names (e.g. 'wire' is reserved)
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


class MassIsRenderedCO(Menu):
    bl_idname = "nb.mass_is_rendered_CO"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_CO'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_CO'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_CO'
