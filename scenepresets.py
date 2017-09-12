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


"""The NeuroBlender scene presets module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements the scene building system.
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
                       FloatProperty,
                       IntProperty)

from . import (materials as nb_ma,
               utils as nb_ut)


class ResetPresetCentre(Operator):
    bl_idname = "nb.reset_presetcentre"
    bl_label = "Reset preset centre"
    bl_description = "Revert location changes to preset centre"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = get_render_objects(nb)
        cloc = get_brainbounds(obs)[0]

        nb_preset = nb.presets[nb.index_presets]

        centre = bpy.data.objects[nb_preset.centre]
        centre.location = cloc

        info = ['reset location of preset "{}"'.format(nb_preset.name)]
        info += ['location is now "{:.2f} {:.2f} {:.2f}"'.format(*cloc)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class ResetPresetDims(Operator):
    bl_idname = "nb.reset_presetdims"
    bl_label = "Recalculate scene dimensions"
    bl_description = "Recalculate scene dimension"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = get_render_objects(nb)
        dims = get_brainbounds(obs)[1]

        nb_preset = nb.presets[nb.index_presets]
        nb_preset.dims = dims

        centre = bpy.data.objects[nb_preset.centre]
        centre.scale = 0.5 * Vector(dims)

        box = bpy.data.objects[nb_preset.box]
        box.scale = 0.5 * Vector([max(dims), max(dims), max(dims)])

        nb_cam = nb_preset.cameras[nb_preset.index_cameras]
        camdata = bpy.data.cameras[nb_cam.name]
        camdata.clip_start = box.scale[0] / 5
        camdata.clip_end = box.scale[0] * 10

        info = ['reset dimensions of preset "{}"'.format(nb_preset.name)]
        info += ['dimensions are now "{:.2f} {:.2f} {:.2f}"'.format(*dims)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class AddPreset(Operator):
    bl_idname = "nb.add_preset"
    bl_label = "New preset"
    bl_description = "Create a new preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="Preset")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.presets]  # TODO: preset.name + "Cam"
        name = nb_ut.check_name(self.name, "", ca,
                                forcefill=True, firstfill=1)

        obs = get_render_objects(nb)
        cloc, dims = get_brainbounds(obs)

        nb_preset, preset = self.add_preset(context, name)
        nb_preset["dims"] = dims

        centre = self.add_centre(context, preset, cloc, dims)
        nb_preset["centre"] = centre.name

        box = self.add_box(context, preset, centre, dims)
        nb_preset["box"] = box.name

        ps_idx = nb.presets.find(preset.name)

        ca = [bpy.data.objects]
        rigname = nb_ut.check_name("Cameras", "", ca,
                                   forcefill=True, firstfill=1)
        cameras = self.add_rigempty(context, name=rigname)
        cameras.parent = preset
        nb_preset["camerasempty"] = cameras.name
        rigdict = {'single': ['RAS'],
                   'double': ['RAS', 'LPI'],
                   'quartet': ['RAS', 'LAS', 'LPS', 'RPS'],
                   'octet': ['RAS', 'LAS', 'LPS', 'RPS',
                             'RAI', 'LAI', 'LPI', 'RPI']}
        self.add_camera_rig(context, preset, centre, box,
                            rigdict[nb.settingprops.camera_rig])

        # TODO: light groups
        ca = [bpy.data.objects]
        rigname = nb_ut.check_name("Lights", "", ca,
                                   forcefill=True, firstfill=1)
        lights = self.add_rigempty(context, name=rigname)
        lights.parent = box
        nb_preset["lightsempty"] = lights.name
        self.add_lighting_rig(context, preset, centre, box)

        bpy.ops.nb.import_tables(index_presets=ps_idx)
#         table.hide = table.hide_render = True

        nb.presets_enum = name
        # FIXME: trackobject set to None after adding camera
#         nb_cam = nb_preset.cameras[nb_preset.index_cameras]
#         nb_cam['trackobject'] = 'Centre'

        info = ['added preset "{}"'.format(name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def add_preset(self, context, name):
        """Add an empty to hold the preset.

        This is simply a container
        with all default blender units (all locked).
        """

        scn = context.scene
        nb = scn.nb

        preset = bpy.data.objects.new(name=name, object_data=None)
        scn.objects.link(preset)
        props = [preset.lock_location, preset.lock_rotation, preset.lock_scale]
        for prop in props:
            for dim in prop:
                dim = True

        presetprops = {"name": name}
        nb_preset = nb_ut.add_item(nb, "presets", presetprops)

        return nb_preset, preset

    def add_centre(self, context, preset, centre_location, dimensions):
        """Add an empty to with the shape of the NeuroBlender scene.

        The empty is at the scene centre location
        and has the scene's dimensions applied.
        """

        scn = context.scene

        ca = [bpy.data.objects]
        name = nb_ut.check_name("Centre", "", ca,
                                forcefill=True, firstfill=1)

        centre = bpy.data.objects.new(name, None)
        scn.objects.link(centre)
        centre.parent = preset
        centre.location = centre_location
        centre.scale = 0.5 * Vector(dimensions)

        return centre

    def add_box(self, context, preset, centre, dimensions):
        """Add an empty to with the shape of the NeuroBlender scene.

        Box is an empty with location yoked to centre
        and cuboid dimensions of max(dims).
        It is used is mainly for camera and light scaling
        in the space of the scene.
        """

        scn = context.scene

        ca = [bpy.data.objects]
        name = nb_ut.check_name("Box", "", ca,
                                forcefill=True, firstfill=1)

        box = bpy.data.objects.new(name, None)
        scn.objects.link(box)
        box.parent = preset
        box.location = (0, 0, 0)
        box.scale = 0.5 * Vector([max(dimensions)] * 3)

        props = {"use_location_x": True,
                 "use_location_y": True,
                 "use_location_z": True,
                 "use_rotation_x": True,
                 "use_rotation_y": True,
                 "use_rotation_z": True,
                 "use_scale_x": False,
                 "use_scale_y": False,
                 "use_scale_z": False}
        nb_ut.add_constraint(box, "CHILD_OF", "Child Of", centre, props)

        return box

    def add_camera_rig(self, context, preset, centre, box,
                       RAScodes, distance=2.88675):
        """Add a camera rig to the NeuroBlender scene."""

        scn = context.scene
        nb = scn.nb

        name = "Cam"
        d = distance
        RASdict = {'C': 0,
                   'R': d, 'L': -d,
                   'A': d, 'P': -d,
                   'S': d, 'I': -d}

        ps_idx = nb.presets.find(preset.name)
        for RAScode in RAScodes:
            camview = [RASdict[RAStoken] for RAStoken in RAScode]
            bpy.ops.nb.import_cameras(
                index_presets=ps_idx,
                name="{}{}".format(name, RAScode),
                cam_view=camview,
                )

    def add_rigempty(self, context, name="Lights"):
        """Add an empty to hold the lighting rig."""

        scn = context.scene

        lights = bpy.data.objects.new(name, None)
        scn.objects.link(lights)
        for idx in [0, 1]:
            driver = lights.driver_add("scale", idx).driver
            driver.type = 'SCRIPTED'
            driver.expression = "scale"
            create_var(driver, "scale",
                       'SINGLE_PROP', 'OBJECT',
                       lights, "scale[2]")

        return lights

    def add_lighting_rig(self, context, preset, centre, box):
        """Add a lighting rig to the NeuroBlender scene."""

        scn = context.scene
        nb = scn.nb

        # NOTE: setting these all to SUN/HEMI,
        # because they work well in both BI and CYCLES
        keystrength = 1
        ltype = ["HEMI", "HEMI", "HEMI"]
        lp_key = {'name': "Key",
                  'type': ltype[0],
                  'colour': (1.0, 1.0, 1.0),
                  'strength': 1.0 * keystrength,
                  'location': (1, 4, 6)}
        lp_fill = {'name': "Fill",
                   'type': ltype[1],
                   'colour': (1.0, 1.0, 1.0),
                   'strength': 0.2 * keystrength,
                   'location': (4, -1, 1)}
        lp_back = {'name': "Back",
                   'type': ltype[2],
                   'colour': (1.0, 1.0, 1.0),
                   'strength': 0.1 * keystrength,
                   'location': (-4, -4, 3)}

        ps_idx = nb.presets.find(preset.name)
        for lightprops in [lp_key, lp_fill, lp_back]:
            bpy.ops.nb.import_lights(
                index_presets=ps_idx,
                name=lightprops['name'],
                type=lightprops['type'],
                colour=lightprops['colour'],
                strength=lightprops['strength'],
                location=lightprops['location']
                )


class DelPreset(Operator):
    bl_idname = "nb.del_preset"
    bl_label = "Delete preset"
    bl_description = "Delete a preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="")
    index = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        info = []

        if self.name:  # got here through cli
            try:
                nb.presets[self.name]
            except KeyError:
                info = ['no preset with name "{}"'.format(self.name)]
                self.report({'INFO'}, info[0])
                return {"CANCELLED"}
            else:
                self.index = nb.presets.find(self.name)
        else:  # got here through invoke
            self.name = nb.presets[self.index].name

        info = self.delete_preset(nb.presets[self.index], info)
        nb.presets.remove(self.index)
        nb.index_presets -= 1
        info += ['removed preset "{}"'.format(self.name)]

        try:
            name = nb.presets[0].name
        except IndexError:
            info += ['all presets have been removed']
        else:
            nb.presets_enum = name
            info += ['preset is now "{}"'.format(name)]

        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index = nb.index_presets
        self.name = ""

        return self.execute(context)

    def delete_preset(self, nb_preset, info=[]):
        """Delete a preset."""

        # unlink all objects from the rendering scenes
        for s in ['_cycles', '_internal']:
            sname = nb_preset.name + s
            try:
                scn = bpy.data.scenes[sname]
            except KeyError:
                info += ['scene "{}" not found'.format(sname)]
            else:
                for ob in scn.objects:
                    scn.objects.unlink(ob)
                bpy.data.scenes.remove(scn)

        # delete all preset objects and data
        ps_obnames = [nb_ob.name
                      for nb_coll in [nb_preset.cameras,
                                      nb_preset.lights,
                                      nb_preset.tables]
                      for nb_ob in nb_coll]
        ps_obnames += [nb_preset.camerasempty,
                       nb_preset.lightsempty,
                       nb_preset.box,
                       nb_preset.centre,
                       nb_preset.name]
        for ps_obname in ps_obnames:
            try:
                ob = bpy.data.objects[ps_obname]
            except KeyError:
                info += ['object "{}" not found'.format(ps_obname)]
            else:
                bpy.data.objects.remove(ob)

        psdictlist = [{'nb_collection': nb_preset.cameras,
                       'data_collection': bpy.data.cameras},
                      {'nb_collection': nb_preset.lights,
                       'data_collection': bpy.data.lamps},
                      {'nb_collection': nb_preset.tables,
                       'data_collection': bpy.data.meshes}]
        for psdict in psdictlist:
            info = self.delete_presetdata(psdict, info)

        # TODO:
        # delete animations from objects
        # delete colourbars
        # delete campaths?

        return info

    def delete_presetdata(self, psdict, info=[]):

        nb_coll = psdict['nb_collection']
        data_coll = psdict['data_collection']

        for ps_item in nb_coll:
            try:
                datablock = data_coll[ps_item.name]
            except KeyError:
                info += ['"{}" not found in {}'.format(ps_item.name,
                                                       data_coll.rna_type.name)]
            else:
                data_coll.remove(datablock)

        return info


class AddCamera(Operator):
    bl_idname = "nb.import_cameras"
    bl_label = "New camera"
    bl_description = "Create a new camera"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="preset index",
        description="Specify preset index",
        default=-1)
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    name = StringProperty(
        name="Name",
        description="Specify a name for the camera",
        default="Cam")

    cam_view = FloatVectorProperty(
        name="Numeric input",
        description="The viewpoint of the camera",
        default=[2.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")

    RAScode = StringProperty(
        name="RAS code",
        description="Three-letter code, one picked from each 'LCR-ACP-ICS'",
        default="RAS")
    cam_distance = FloatProperty(
        name="Camera distance",
        description="Relative distance of the camera (to bounding box)",
        default=5,
        min=0)

    trackobject = StringProperty(
        name="Track object",
        description="Choose an object to track with the camera",
        default="Centre")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[self.index_presets]
        preset = bpy.data.objects[nb_preset.name]
        centre = bpy.data.objects[nb_preset.centre]
        box = bpy.data.objects[nb_preset.box]
        cameras = bpy.data.objects[nb_preset.camerasempty]

        ca = [ps.cameras for ps in nb.presets]
        name = nb_ut.check_name(self.name, "", ca,
                                forcefill=True, firstfill=1)

        cdname = preset.name + 'Cam'
        camdata = bpy.data.cameras.get(cdname) or \
            self.create_camera_data(cdname, box.scale[0])

        RASdict = {'C': 'Centre',
                   'L': 'Left', 'R': 'Right',
                   'A': 'Anterior', 'P': 'Posterior',
                   'I': 'Inferior', 'S': 'Superior'}
        camprops = {
            "name": name,
            "cam_view": self.cam_view,
            "cam_view_enum_LR": RASdict[self.RAScode[0]],
            "cam_view_enum_AP": RASdict[self.RAScode[1]],
            "cam_view_enum_SI": RASdict[self.RAScode[2]],
            "cam_distance": self.cam_distance,
            "trackobject": self.trackobject
            }
        nb_ut.add_item(nb_preset, "cameras", camprops)
        cam = self.create_camera_object(name, preset, centre, box, cameras, camdata)
        nb_preset.cameras[nb_preset.index_cameras].name = cam.name

        info = ['added camera "{}" to preset "{}"'.format(cam.name, nb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets

        return self.execute(context)

    def create_camera_object(self, name, preset, centre, box, cameras, camdata):
        """Add a camera to the scene."""

        scn = bpy.context.scene

        cam = bpy.data.objects.new(name, camdata)
        cam.parent = cameras
        cam.location = self.cam_view
        scn.objects.link(cam)

        nb_ut.add_constraint(cam, "CHILD_OF", "Child Of", box)
        nb_ut.add_constraint(cam, "TRACK_TO", "TrackToObject", centre)

        scn.camera = cam

        return cam

    def create_camera_data(self, name, boxscale):
        """Create a camera."""

        camdata = bpy.data.cameras.new(name=name)
        camdata.show_name = True
        camdata.draw_size = 0.2
        camdata.type = 'PERSP'
        camdata.lens = 35
        camdata.lens_unit = 'MILLIMETERS'
        camdata.shift_x = 0.0
        camdata.shift_y = 0.0
        camdata.clip_start = boxscale / 5
        camdata.clip_end = boxscale * 10

        # depth-of-field
    #     empty = bpy.data.objects.new('DofEmpty', None)
    #     empty.location = centre.location
    #     camdata.dof_object = empty
    #     scn.objects.link(empty)
        # TODO: let the empty follow the brain outline
    #     cycles = camdata.cycles
    #     cycles.aperture_type = 'FSTOP'
    #     cycles.aperture_fstop = 5.6

        return camdata


class AddTable(Operator):
    bl_idname = "nb.import_tables"
    bl_label = "New table"
    bl_description = "Create a new table"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="preset index",
        description="Specify preset index",
        default=-1)
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    name = StringProperty(
        name="Name",
        description="Specify a name for the table",
        default="Table")

    colourpicker = FloatVectorProperty(
        name="Colour",
        description="Pick a colour",
        default=[0.5, 0.5, 0.5],
        subtype="COLOR")

    scale = FloatVectorProperty(
        name="Table scale",
        description="Relative size of the table",
        default=[4.0, 4.0, 1.0],
        subtype="TRANSLATION")
    location = FloatVectorProperty(
        name="Table location",
        description="Relative location of the table",
        default=[0.0, 0.0, -1.0],
        subtype="TRANSLATION")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[self.index_presets]
        preset = bpy.data.objects[nb_preset.name]
        centre = bpy.data.objects[nb_preset.centre]
        box = bpy.data.objects[nb_preset.box]

        ca = [ps.tables for ps in nb.presets]
        name = nb_ut.check_name(self.name, "", ca,
                                forcefill=True, firstfill=1)

        tableprops = {
            "name": name,
            "colourpicker": self.colourpicker,
            "scale": self.scale,
            "location": self.location,
            }
        nb_ut.add_item(nb_preset, "tables", tableprops)
        table = self.create_table(name, centre)
        nb_preset.tables[nb_preset.index_tables].name = table.name

        info = ['added table "{}" to preset "{}"'.format(table.name,
                                                         nb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets

        return self.execute(context)

    def create_table(self, name, parent):
        """Add a table to the scene."""

        table = self.create_plane(name)
        table.scale = self.scale
        table.location = self.location

        diffcol = list(self.colourpicker) + [1.0]
        mat = nb_ma.make_cr_mat_basic(table.name, diffcol, mix=0.8)
        nb_ma.set_materials(table.data, mat)

        table.parent = parent

        return table

    def create_plane(self, name):
        """Create a plane."""

        scn = bpy.context.scene

        me = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, me)
        scn.objects.link(ob)
        scn.objects.active = ob
        ob.select = True

        verts = [(-1, -1, 0), (-1, 1, 0), (1, 1, 0), (1, -1, 0)]
        faces = [(3, 2, 1, 0)]
        me.from_pydata(verts, [], faces)
        me.update()

        return ob


class AddLight(Operator):
    bl_idname = "nb.import_lights"
    bl_label = "New light"
    bl_description = "Create a new light"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="preset index",
        description="Specify preset index",
        default=-1)
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    name = StringProperty(
        name="Name",
        description="Specify a name for the light",
        default="Light")
    type = EnumProperty(
        name="Light type",
        description="type of lighting",
        items=[("POINT", "POINT", "POINT", 0),
               ("SUN", "SUN", "SUN", 1),
               ("SPOT", "SPOT", "SPOT", 2),
               ("HEMI", "HEMI", "HEMI", 3),
               ("AREA", "AREA", "AREA", 4)],
        default="HEMI")
    colour = FloatVectorProperty(
        name="Colour",
        description="Colour of the light",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    strength = FloatProperty(
        name="Strength",
        description="Strength of the light",
        default=1,
        min=0)
    size = FloatVectorProperty(
        name="Size",
        description="Relative size of the plane light (to bounding box)",
        size=2,
        default=[1.0, 1.0])
    location = FloatVectorProperty(
        name="Location",
        description="",
        default=[3.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[self.index_presets]
        preset = bpy.data.objects[nb_preset.name]
        centre = bpy.data.objects[nb_preset.centre]
        box = bpy.data.objects[nb_preset.box]
        lights = bpy.data.objects[nb_preset.lightsempty]

        ca = [ps.lights for ps in nb.presets]
        name = nb_ut.check_name(self.name, "", ca,
                                forcefill=True, firstfill=1)

        lp = {'name': name,
              'type': self.type,
              'size': self.size,
              'colour': self.colour,
              'strength': self.strength,
              'location': self.location}
        nb_light = nb_ut.add_item(nb_preset, "lights", lp)
        light = self.create_light(name, preset, centre, box, lights)
        nb_preset.lights[nb_preset.index_lights].name = light.name

        info = ['added light "{}" in preset "{}"'.format(light.name, nb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets

        return self.execute(context)

    def create_light(self, name, preset, centre, box, lights):
        """Add a light to NeuroBlender."""

        scn = bpy.context.scene
        engine = scn.render.engine

        scale = self.size
        colour = tuple(list(self.colour) + [1.0])

        lamp = bpy.data.lamps.new(name, self.type)
        light = bpy.data.objects.new(lamp.name, object_data=lamp)
        scn.objects.link(light)
        scn.objects.active = light
        light.select = True

        if not engine == "CYCLES":
            scn.render.engine = "CYCLES"
        light.data.use_nodes = True
        if self.type != "HEMI":
            light.data.shadow_soft_size = 50
        node = light.data.node_tree.nodes["Emission"]
        node.inputs[1].default_value = self.strength

        scn.render.engine = "BLENDER_RENDER"
        light.data.energy = self.strength

        scn.render.engine = engine

        light.parent = lights
        light.location = self.location

        nb_ut.add_constraint(light, "TRACK_TO", "TrackToObject", centre)

        return light


class ObjectListCM(UIList):

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


class MassIsRenderedCM(Menu):
    bl_idname = "nb.mass_is_rendered_CM"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_CM'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_CM'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_CM'


class ObjectListPL(UIList):

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


class MassIsRenderedPL(Menu):
    bl_idname = "nb.mass_is_rendered_PL"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_PL'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_PL'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_PL'


def get_render_objects(nb):
    """Gather all objects listed for render."""

    carvers = [carver for surf in nb.surfaces
               for carver in surf.carvers]
    carvers += [carver for vvol in nb.voxelvolumes
                for carver in vvol.carvers]
    obnames = [[nb_ob.name for nb_ob in nb_coll if nb_ob.is_rendered]
               for nb_coll in [nb.tracts, nb.surfaces, nb.voxelvolumes,
                               carvers]]

    obs = [bpy.data.objects[item] for sublist in obnames for item in sublist]

    return obs


def get_brainbounds(obs):
    """Find the boundingbox, dimensions and centre of the objects."""

    if not obs:
        print("""
              no objects selected for render:
              setting location and dimensions to default.
              """)
        centre_location = [0, 0, 0]
        dims = [100, 100, 100]
    else:
        bb_min, bb_max = np.array(get_bbox_coordinates(obs))
        dims = np.subtract(bb_max, bb_min)
        centre_location = bb_min + dims / 2

    return centre_location, dims


def get_bbox_coordinates(obs):
    """Find the extreme dimensions in the geometry."""

    bb_world = [ob.matrix_world * Vector(bbco)
                for ob in obs for bbco in ob.bound_box]
    bb_min = np.amin(np.array(bb_world), 0)
    bb_max = np.amax(np.array(bb_world), 0)

    return bb_min, bb_max


def create_var(driver, name, type, id_type, id, data_path,
               transform_type="", transform_space=""):

    var = driver.variables.new()
    var.name = name
    var.type = type
    tar = var.targets[0]
    if not transform_type:
        tar.id_type = id_type
    tar.id = id
    tar.data_path = data_path
    if transform_type:
        tar.transform_type = transform_type
    if transform_space:
        tar.transform_space = transform_space
