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

NeuroBlender is a Blender add-on
to create artwork from neuroscientific data.
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

    index_presets = IntProperty(
        name="preset index",
        description="Specify preset index",
        default=-1)

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = get_render_objects(nb)
        cloc = get_brainbounds(obs)[0]

        nb_preset = nb.presets[self.index_presets]

        centre = bpy.data.objects[nb_preset.centre]
        centre.location = cloc

        if nb.settingprops.verbose:
            istring = 'set location of "{}" to "{:.2f} {:.2f} {:.2f}"'
            info = [istring.format(nb_preset.name, *dims)]
            self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class ResetPresetDims(Operator):
    bl_idname = "nb.reset_presetdims"
    bl_label = "Recalculate scene dimensions"
    bl_description = "Recalculate scene dimension"
    bl_options = {"REGISTER"}

    index_presets = IntProperty(
        name="preset index",
        description="Specify preset index",
        default=-1)

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = get_render_objects(nb)
        dims = get_brainbounds(obs)[1]

        nb_preset = nb.presets[self.index_presets]
        nb_preset.dims = dims

        centre = bpy.data.objects[nb_preset.centre]
        centre.scale = 0.5 * Vector(dims)

        box = bpy.data.objects[nb_preset.box]
        box.scale = 0.5 * Vector([max(dims), max(dims), max(dims)])

        camdata = bpy.data.cameras[nb_preset.cam]
        camdata.clip_start = box.scale[0] / 5
        camdata.clip_end = box.scale[0] * 10

        if nb.settingprops.verbose:
            istring = 'set dimensions of "{}" to "{:.2f} {:.2f} {:.2f}"'
            info = [istring.format(nb_preset.name, *dims)]
            self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class AddPreset(Operator):
    bl_idname = "nb.import_presets"
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

        obs = get_render_objects(nb)
        cloc, dims, info = get_brainbounds(obs)

        # preset
        ca = [nb.presets]
        name = nb_ut.check_name(self.name, "", ca,
                                forcefill=True, firstfill=1)
        nb_preset, preset = self.add_preset(context, name)
        nb_preset.dims = dims
        nb_preset.layer = len(nb.presets) + 9

        # centre
        centre = self.add_centre(context, preset, cloc, dims)
        nb_preset.centre = centre.name

        # box
        box = self.add_box(context, preset, centre, dims)
        nb_preset.box = box.name

        # cameras
        ca = [bpy.data.objects]
        rigname = nb_ut.check_name("Cameras", "", ca,
                                   forcefill=True, firstfill=1)
        cameras = self.add_rigempty(context, name=rigname)
        cameras.parent = preset
        nb_preset.camerasempty = cameras.name
        self.add_camera_rig(context, preset, centre, box,
                            nb.settingprops.camera_rig)

        # lights  # TODO: light groups?
        ca = [bpy.data.objects]
        rigname = nb_ut.check_name("Lights", "", ca,
                                   forcefill=True, firstfill=1)
        lights = self.add_rigempty(context, name=rigname)
        lights.parent = box
        nb_preset.lightsempty = lights.name
        self.add_lighting_rig(context, preset, centre, box,
                              nb.settingprops.lighting_rig)

        # tables
        ca = [bpy.data.objects]
        rigname = nb_ut.check_name("Tables", "", ca,
                                   forcefill=True, firstfill=1)
        tables = self.add_rigempty(context, name=rigname)
        tables.parent = centre
        nb_preset.tablesempty = tables.name
        self.add_table_rig(context, preset, centre, box,
                           nb.settingprops.table_rig)

        # renderlayer
        preset_obs = [preset, centre, box,
                      cameras, lights, tables]
        for ob in preset_obs:
            nb_ut.move_to_layer(ob, nb_preset.layer)
        for layer in range(10, 20):
            scn.layers[layer] = (layer == nb_preset.layer)

        if nb.settingprops.verbose:
            info += ['added preset "{}"'.format(name)]
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
        props = [preset.lock_location,
                 preset.lock_rotation,
                 preset.lock_scale]
        for prop in props:
            for dim in prop:
                dim = True

        presetprops = {"name": name}
        nb_preset = nb_ut.add_item(nb, "presets", presetprops)

        nb_ut.move_to_layer(preset, nb_preset.layer)

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

    def add_rigempty(self, context, name="Lights"):
        """Add an empty to hold the lighting rig."""

        scn = context.scene

        rigempty = bpy.data.objects.new(name, None)
        scn.objects.link(rigempty)
        for idx in [0, 1]:
            driver = rigempty.driver_add("scale", idx).driver
            driver.type = 'SCRIPTED'
            driver.expression = "scale"
            create_var(driver, "scale",
                       'SINGLE_PROP', 'OBJECT',
                       rigempty, "scale[2]")

        return rigempty

    def add_camera_rig(self, context, preset, centre, box,
                       camera_rig, distance=5):
        """Add a camera rig to the NeuroBlender scene."""

        scn = context.scene
        nb = scn.nb

        lud = {'C': 0,
               'R': 1, 'L': -1,
               'A': 1, 'P': -1,
               'S': 1, 'I': -1}

        rigdict = {
            'single': ['RAS'],
            'double_diag': ['RAS', 'LPI'],
            'double_LR': ['RCC', 'LCC'],
            'double_AP': ['CAC', 'CPC'],
            'double_IS': ['CCI', 'CCS'],
            'quartet': ['RAS', 'LAS', 'LPS', 'RPS'],
            'sextet': ['RCC', 'LCC', 'CAC', 'CPC', 'CCI', 'CCS'],
            'octet': ['RAS', 'LAS', 'LPS', 'RPS',
                      'RAI', 'LAI', 'LPI', 'RPI']
                   }

        for RAScode in rigdict[camera_rig]:

            cv_unit = Vector([lud[RAScode[0]],
                              lud[RAScode[1]],
                              lud[RAScode[2]]]).normalized()

            bpy.ops.nb.import_cameras(
                index_presets=nb.presets.find(preset.name),
                name=RAScode,
                cam_view=list(cv_unit * distance),
                RAScode=RAScode,
                trackobject=centre.name,
                )

    def add_lighting_rig(self, context, preset, centre, box,
                         lighting_rig):
        """Add a lighting rig to the NeuroBlender scene."""

        scn = context.scene
        nb = scn.nb

        # NOTE: setting these all to SUN/HEMI,
        # because they work well in both BI and CYCLES
        ltype = ["HEMI", "HEMI", "HEMI"]
        keystrength = 1

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

        rigdict = {'single': [lp_key],
                   'triple': [lp_key, lp_fill, lp_back]}

        for lightprops in rigdict[lighting_rig]:
            bpy.ops.nb.import_lights(
                index_presets=nb.presets.find(preset.name),
                name=lightprops['name'],
                type=lightprops['type'],
                colour=lightprops['colour'],
                strength=lightprops['strength'],
                location=lightprops['location']
                )

    def add_table_rig(self, context, preset, centre, box,
                      table_rig):
        """Add a table setup to the NeuroBlender scene."""

        scn = context.scene
        nb = scn.nb

        tableprops = {'simple':
                      {'colourpicker': [0.5, 0.5, 0.5],
                       'scale': [4.0, 4.0, 1.0],
                       'location': [0.0, 0.0, -1.0]},
                      }

        rigdict = {'none': [],
                   'simple': [tableprops['simple']]}

        for tableprops in rigdict[table_rig]:
            bpy.ops.nb.import_tables(
                index_presets=nb.presets.find(preset.name),
                colourpicker=tableprops['colourpicker'],
                scale=tableprops['scale'],
                location=tableprops['location'],
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

        if nb.settingprops.verbose:
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

        # delete all preset objects
        nb_colls = [nb_preset.cameras,
                    nb_preset.lights,
                    nb_preset.tables]
        ps_obnames = [nb_ob.name for nb_coll in nb_colls
                      for nb_ob in nb_coll]
        ps_obnames += [nb_preset.camerasempty,
                       nb_preset.lightsempty,
                       nb_preset.tablesempty,
                       nb_preset.box,
                       nb_preset.centre,
                       nb_preset.name]
        for name in ps_obnames:
            self.delete_datablock(bpy.data.objects,
                                  name, info=[])

        # delete all preset data
        psdictlist = [{'nb_collection': nb_preset.cameras,
                       'data_collection': bpy.data.cameras},
                      {'nb_collection': nb_preset.lights,
                       'data_collection': bpy.data.lamps},
                      {'nb_collection': nb_preset.tables,
                       'data_collection': bpy.data.meshes}]
        for psdict in psdictlist:
            for item in psdict['nb_collection']:
                self.delete_datablock(psdict['data_collection'],
                                      item.name, info=[])

        # TODO:
        # delete animations from objects
        # delete colourbars
        # delete campaths?

        return info

    def delete_datablock(self, data_coll, name, info=[]):
        """Remove a datablock from a collection."""

        try:
            datablock = data_coll[name]
        except KeyError:
            infostring = '"{}" not found in "{}"'
            info += [infostring.format(name, data_coll.rna_type.name)]
        else:
            data_coll.remove(datablock)


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
        description="Three-letter code, one each from'LCR-ACP-ICS'",
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

        if nb_preset.cam:
            camdata = bpy.data.cameras.get(nb_preset.cam)
        else:
            cdname = preset.name + '_Camera'
            camdata = self.create_camera_data(cdname, box.scale[0])
            nb_preset.cam = camdata.name

        ca = [ps.cameras for ps in nb.presets]
        name = nb_ut.check_name(self.name, "", ca,
                                forcefill=True, firstfill=1)

        cam = self.create_camera_object(name, centre, box,
                                        cameras, camdata)
        nb_ut.move_to_layer(cam, nb_preset.layer)

        camprops = {
            "name": cam.name,
            "cam_view": self.cam_view,
            "cam_view_enum_LR": self.RAScode[0],
            "cam_view_enum_AP": self.RAScode[1],
            "cam_view_enum_SI": self.RAScode[2],
            "cam_distance": self.cam_distance,
            "trackobject": self.trackobject,
            }
        nb_cam = nb_ut.add_item(nb_preset, "cameras", camprops)
        nb_cam.name = cam.name
        nb_cam.cam_view = self.cam_view
        nb_cam.cam_view_enum_LR = self.RAScode[0]
        nb_cam.cam_view_enum_AP = self.RAScode[1]
        nb_cam.cam_view_enum_IS = self.RAScode[2]
        nb_cam.cam_distance = self.cam_distance
        nb_cam.trackobject = self.trackobject  # FIXME
        nb_cam.trackobject = self.trackobject  # FIXME

        if nb.settingprops.verbose:
            infostring = 'added camera "{}" to preset "{}"'
            info = [infostring.format(cam.name, nb_preset.name)]
            self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        self.trackobject = nb.presets[self.index_presets].centre

        return self.execute(context)

    def create_camera_object(self, name, centre, box, cameras, camdata):
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
        tables = bpy.data.objects[nb_preset.tablesempty]

        ca = [ps.tables for ps in nb.presets]
        name = nb_ut.check_name(self.name, "", ca,
                                forcefill=True, firstfill=1)

        table = self.create_table(name, tables)
        nb_ut.move_to_layer(table, nb_preset.layer)

        tableprops = {
            "name": table.name,
            "colourpicker": self.colourpicker,
            "scale": self.scale,
            "location": self.location,
            }
        nb_table = nb_ut.add_item(nb_preset, "tables", tableprops)
        nb_table.name = table.name

        if nb.settingprops.verbose:
            infostring = 'added camera "{}" to preset "{}"'
            info = [infostring.format(table.name, nb_preset.name)]
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
        table.show_transparent = True

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

        light = self.create_light(name, preset, centre, box, lights)
        nb_ut.move_to_layer(light, nb_preset.layer)

        lightprops = {
            'name': light.name,
            'type': self.type,
            'size': self.size,
            'colour': self.colour,
            'strength': self.strength,
            'location': self.location,
            }
        nb_light = nb_ut.add_item(nb_preset, "lights", lightprops)
        nb_light.name = light.name

        if nb.settingprops.verbose:
            infostring = 'added light "{}" in preset "{}"'
            info = [infostring.format(light.name, nb_preset.name)]
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


class ObjectListPS(UIList):

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
                self.draw_advanced(layout, data, item, index)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)

    def draw_advanced(self, layout, data, item, index):

        col = layout.column()
        row = col.row(align=True)
        props = [{'prop': 'location',
                  'op': "nb.reset_presetcentre",
                  'icon': 'CLIPUV_HLT',
                  'text': 'Recentre'},
                 {'prop': 'scale',
                  'op': "nb.reset_presetdims",
                  'icon': 'BBOX',
                  'text': 'Rescale'}]
        for propdict in props:
            col1 = row.column(align=True)
            col1.operator(propdict['op'],
                          icon=propdict['icon'],
                          text="").index_presets = index


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
                self.draw_advanced(layout, data, item, index)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)

    def draw_advanced(self, layout, data, item, index):

        col = layout.column()
        col.alignment = "RIGHT"
        col.active = item.is_rendered
        col.prop(item, "is_rendered", text="", emboss=False,
                 translate=False, icon='SCENE')


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
                self.draw_advanced(layout, data, item, index)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)

    def draw_advanced(self, layout, data, item, index):

        col = layout.column()
        col.alignment = "RIGHT"
        col.active = item.is_rendered
        col.prop(item, "is_rendered", text="", emboss=False,
                 translate=False, icon='SCENE')


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


class ObjectListTB(UIList):

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
                self.draw_advanced(layout, data, item, index)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)

    def draw_advanced(self, layout, data, item, index):

        col = layout.column()
        col.alignment = "RIGHT"
        col.active = item.is_rendered
        col.prop(item, "is_rendered", text="", emboss=False,
                 translate=False, icon='SCENE')


class MassIsRenderedTB(Menu):
    bl_idname = "nb.mass_is_rendered_TB"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):

        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_TB'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_TB'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_TB'


def get_render_objects(nb):
    """Gather all objects listed for render."""

    carvers = [carver for surf in nb.surfaces
               for carver in surf.carvers]
    carvers += [carver for vvol in nb.voxelvolumes
                for carver in vvol.carvers]
    obnames = [[nb_ob.name for nb_ob in nb_coll if nb_ob.is_rendered]
               for nb_coll in [nb.tracts,
                               nb.surfaces,
                               nb.voxelvolumes,
                               carvers]]

    obs = [bpy.data.objects[item]
           for sublist in obnames
           for item in sublist]

    return obs


def get_brainbounds(obs):
    """Find the boundingbox, dimensions and centre of the objects."""

    if not obs:
        info = "no objects selected for render: "
        info += "setting location and dimensions to default."
        centre_location = [0, 0, 0]
        dims = [100, 100, 100]
    else:
        info = "calculating bounds from objects"
        bb_min, bb_max = np.array(get_bbox_coordinates(obs))
        dims = np.subtract(bb_max, bb_min)
        centre_location = bb_min + dims / 2

    return centre_location, dims, info


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

