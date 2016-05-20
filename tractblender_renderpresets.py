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

import bpy

import numpy as np
from mathutils import Vector

from . import tractblender_materials as tb_mat
from . import tractblender_utils as tb_utils

# ========================================================================== #
# function to prepare a suitable setup for rendering the scene
# ========================================================================== #


def scene_preset(name="Brain", layer=10):
    """Setup a scene for render."""

    # TODO: manage presets: e.g. put each preset in an empty, etc
    # TODO: option to save presets
    # TODO: copy colourbars to cam instead of moving them around
    # TODO: set presets up as scenes?
#     name = 'Preset'
#     new_scene = bpy.data.scenes.new(name)
#     preset = bpy.data.objects.new(name=name, object_data=None)
#     bpy.context.scene.objects.link(preset)

    scn = bpy.context.scene
    tb = scn.tb

    delete_preset(name)

    obs = [ob for ob in bpy.data.objects
           if ((ob.type not in ['CAMERA', 'LAMP', 'EMPTY']) and
               (not ob.name.startswith('BrainDissectionTable')) and
               (not ob.name.startswith('BrainLights')))]
    if not obs:
        print('no objects selected for render')
        return {'CANCELLED'}

    preset = bpy.data.objects.new(name=name, object_data=None)
    bpy.context.scene.objects.link(preset)

    centre, bbox, dims = get_brainbounds(name+"Centre", obs)
    table = create_table(name+"DissectionTable", centre, bbox, dims)
    cam = create_camera(name+"Cam", centre, bbox, dims, Vector(tb.cam_view))
    lights = create_lighting(name+"Lights", centre, bbox, dims, cam)

    add_colourbars(cam)

    lights.parent = cam
    obs = [centre] + [table] + [cam]
    for ob in obs:
        if ob is not None:
            ob.parent = preset

    obs = [preset] + obs + [lights] + list(lights.children)
    for ob in obs:
        if ob is not None:
            tb_utils.move_to_layer(ob, layer)
    scn.layers[layer] = True

    scn.cycles.caustics_refractive = False
    scn.cycles.caustics_reflective = False

    # TODO: add colourbars
    preset_obs = [preset] + [centre] + [table] + [cam] + [lights] + list(lights.children)
    tracts = [bpy.data.objects[tb_ob.name] for tb_ob in tb.tracts]
    surfaces = [bpy.data.objects[tb_ob.name] for tb_ob in tb.surfaces]
    cycles_obs = preset_obs + tracts + surfaces
    prep_scenes('cycles', 'CYCLES', 'GPU', [0, 1, 10], True, cycles_obs)

    preset_obs = [preset] + [centre] + [cam]
    voxelvolumes = [bpy.data.objects[tb_ob.name] for tb_ob in tb.voxelvolumes]
    vv_children = [vvchild for vv in voxelvolumes for vvchild in vv.children]
    internal_obs = preset_obs + voxelvolumes + vv_children
    prep_scenes('internal', 'BLENDER_RENDER', 'CPU', [2], False, internal_obs)

    prep_scene_composite(scn, 'BLENDER_RENDER')

    bpy.ops.tb.switch_to_main()
    to_camera_view()

    return {'FINISHED'}


def to_camera_view():
    """Set 3D viewports to camera perspective."""

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces[0].region_3d.view_perspective = 'CAMERA'


def get_brainbounds(name, obs):
    """Find the boundingbox, dimensions and centre of the objects."""

    bbox = np.array(find_bbox_coordinates(obs))
    dims = np.subtract(bbox[:, 1], bbox[:, 0])
    centre = bbox[:, 0] + dims / 2

    empty = bpy.data.objects.new(name=name, object_data=None)
    empty.location = centre
    bpy.context.scene.objects.link(empty)

    return empty, bbox, dims


def delete_preset(prefix):
    """"""
    # TODO: more flexibility in keeping and naming
#     for ob in scn.objects:
#         if ob.type == 'CAMERA' or ob.type == 'LAMP' or ob.type == 'EMPTY':
# #             if ob.name.startswith('Brain'):
#                 scn.objects.unlink(ob)
#     deltypes = ['CAMERA', 'LAMP', 'EMPTY']

    try:
        cbars = bpy.data.objects.get("Colourbars")
    except KeyError:
        pass
    else:
        for ob in bpy.data.objects:
            if ob.name.endswith("_colourbar"):
                ob.parent = cbars

    bpy.ops.object.mode_set(mode='OBJECT')
    for ob in bpy.data.objects:
        ob.select = ob.name.startswith(prefix)  # and ob.type in deltypes
    bpy.context.scene.objects.active = ob
    bpy.ops.object.delete()


def find_bbox_coordinates(obs):
    """Find the extreme dimensions in the geometry."""
    xyz = []
    for dim in range(3):
        xco = []
        for ob in obs:
            for b in ob.bound_box:
                xco.append(b[dim] * ob.scale[dim] + ob.location[dim])
        co_min = min(xco)
        co_max = max(xco)
        xyz.append([co_min, co_max])
    return xyz


def prep_scenes(name, engine, device, layers, use_sky, obs):
    """"""

    scns = bpy.data.scenes
    if scns.get(name) is not None:
        scn = scns.get(name)
    else:
        bpy.ops.scene.new(type='NEW')
        scn = scns[-1]
        scn.name = name

    scn.render.engine = engine
    scn.cycles.device = device
    for l in range(20):
        scn.layers[l] = l in layers
        scn.render.layers[0].layers[l] = l in layers
    scn.render.layers[0].use_sky = use_sky
    scn.tb.is_enabled = False

#     linked_obs = [ob.name for ob in scn.objects]
    for ob in scn.objects:
        scn.objects.unlink(ob)
    for ob in obs:
        if ob is not None:
            scn.objects.link(ob)

    return scn


def prep_scene_composite(scn, engine):
    """"""

#     scns = bpy.data.scenes
#     if scns.get(name) is not None:
#         return
#     bpy.ops.scene.new(type='NEW')
#     scn = bpy.data.scenes[-1]
#     scn.name = name
#     scn.tb.is_enabled = False

    scn.render.engine = engine
    scn.use_nodes = True

    nodes = scn.node_tree.nodes
    links = scn.node_tree.links

    nodes.clear()

    comp = nodes.new("CompositorNodeComposite")
    comp.location = 800, 0

    mix = nodes.new("CompositorNodeMixRGB")
    mix.inputs[0].default_value = 0.5
    mix.use_alpha = True
    mix.location = 600, 0

    rlayer1 = nodes.new("CompositorNodeRLayers")
    rlayer1.scene = bpy.data.scenes['cycles']
    rlayer1.location = 400, 200

    rlayer2 = nodes.new("CompositorNodeRLayers")
    rlayer2.scene = bpy.data.scenes['internal']
    rlayer2.location = 400, -200

    links.new(mix.outputs["Image"], comp.inputs["Image"])
    links.new(rlayer1.outputs["Image"], mix.inputs[1])
    links.new(rlayer2.outputs["Image"], mix.inputs[2])


# ========================================================================== #
# camera
# ========================================================================== #


def create_camera(name, centre, bbox, dims, camview=Vector((1, 1, 1))):
    """"""

    scn = bpy.context.scene

    cam = bpy.data.cameras.new(name=name)
    ob = bpy.data.objects.new(name, cam)
    scn.objects.link(ob)
    cam = ob.data
    cam.show_name = True

    cam.type = 'PERSP'
    cam.lens = 75
    cam.lens_unit = 'MILLIMETERS'
    cam.shift_x = 0.0
    cam.shift_y = 0.0
    cam.clip_start = min(dims) / 10
    cam.clip_end = max(dims) * 20

    add_constraint(ob, "TRACK_TO", "TrackToCentre", centre)
    add_constraint(ob, "LIMIT_DISTANCE",
                   "LimitDistInClipBox", centre, cam.clip_end)
    add_constraint(ob, "LIMIT_DISTANCE",
                   "LimitDistOutBrainBox", centre, max(dims))

    dist = max(dims) * camview
    ob.location = (centre.location[0] + dist[0],
                   centre.location[1] + dist[1],
                   centre.location[2] + dist[2])

    # depth-of-field
    empty = bpy.data.objects.new('DofEmpty', None)
    empty.location = centre.location
    cam.dof_object = empty
#     scn.objects.link(empty)
    # TODO: let the empty follow the brain outline
#     cycles = cam.cycles
#     cycles.aperture_type = 'FSTOP'
#     cycles.aperture_fstop = 5.6

    scn.camera = ob
    return ob


def add_constraint(ob, type, name, target, val=None):
    """"""
    cns = ob.constraints.new(type)
    cns.name = name
    cns.target = target
    cns.owner_space = 'WORLD'
    cns.target_space = 'WORLD'
    if name.startswith('TrackTo'):
        cns.track_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
    elif name.startswith('LimitDistOut'):
        cns.limit_mode = 'LIMITDIST_OUTSIDE'
        cns.distance = val
    elif name.startswith('LimitDistIn'):
        cns.limit_mode = 'LIMITDIST_INSIDE'
        cns.distance = val
    return


# ========================================================================== #
# lights
# ========================================================================== #


def create_lighting(name, braincentre, bbox, dims, cam, camview=(1, 1, 1)):
    """"""

    # TODO: constraints to have the light follow cam?
    # Key (strong spot), back (strong behind subj), fill(cam location)

    lights = bpy.data.objects.new(name=name, object_data=None)
    lights.location = braincentre.location
    bpy.context.scene.objects.link(lights)

    lname = name + "Key"
    dimscale = (0.5, 0.5)
#     dimlocation = [5*camview[0], 2*camview[1], 3*camview[2]]
    dimlocation = (3, 2, 1)
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 50}
    main = create_light(lname, braincentre, bbox, dims,
                        dimscale, dimlocation, emission)
    main.parent = lights

    lname = name + "Back"
    dimscale = (0.1, 0.1)
#     dimlocation = [-2*camview[0], 2*camview[1], 1*camview[2]]
    dimlocation = (2, 4, -10)
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 30}
    aux = create_light(lname, braincentre, bbox, dims,
                       dimscale, dimlocation, emission)
    aux.parent = lights

    lname = name + "Fill"
    scale = (0.1, 0.1)
    dimlocation = (0, 0, 0)
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 100}
    high = create_light(lname, braincentre, bbox, dims,
                        scale, dimlocation, emission)
    high.parent = lights

    return lights

def create_light(name, braincentre, bbox, dims, scale, loc, emission):
    """"""

    ob = create_plane(name)
    ob.scale = [dims[0]*scale[0], dims[1]*scale[1], 1]
    ob.location = (dims[0] * loc[0], dims[1] * loc[1], dims[2] * loc[2])
    add_constraint(ob, "TRACK_TO", "TrackToBrainCentre", braincentre)
    mat = tb_mat.make_material_emit_cycles(name, emission)
#     mat = tb_mat.make_material_emit_internal(name, emission, True)
    tb_mat.set_materials(ob.data, mat)

    return ob


# ========================================================================== #
# world
# ========================================================================== #

def create_plane(name):
    """"""

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


def create_table(name, centre, bbox, dims):
    """Create a table under the objects."""

    tb = bpy.context.scene.tb
    if tb.cam_view[2] < 0:
        return None

    ob = create_plane(name)
    ob.scale = (dims[0]*4, dims[1]*4, 1)
    ob.location = (centre.location[0],
                   centre.location[1],
                   bbox[2, 0])

    diffcol= [0.5, 0.5, 0.5, 1.0]
    mat = tb_mat.make_material_basic_cycles(name, diffcol, mix=0.8)
    tb_mat.set_materials(ob.data, mat)

    return ob


def create_world():
    """"""

    world = bpy.context.scene.world
    nodes = world.node_tree.nodes

    node = nodes.new("")
    node.label = "Voronoi Texture"
    node.name = "Voronoi Texture"
    node.location = 800, 0

    nodes.nodes["Voronoi Texture"].coloring = 'INTENSITY'
    nt = bpy.data.node_groups["Shader Nodetree"]
    nt.nodes["Background"].inputs[1].default_value = 0.1
    nt.nodes["Voronoi Texture"].inputs[1].default_value = 2


# ========================================================================== #
# Colourbar placement 
# ========================================================================== #
# (reuse of code from http://blender.stackexchange.com/questions/6625)


def SetupDriverVariables(driver, imageplane):
    camAngle = driver.variables.new()
    camAngle.name = 'camAngle'
    camAngle.type = 'SINGLE_PROP'
    camAngle.targets[0].id = imageplane.parent
    camAngle.targets[0].data_path ="data.angle"
    depth = driver.variables.new()
    depth.name = 'depth'
    depth.type = 'TRANSFORMS'
    depth.targets[0].id = imageplane
    depth.targets[0].data_path = 'location'
    depth.targets[0].transform_type = 'LOC_Z'
    depth.targets[0].transform_space = 'LOCAL_SPACE'


def SetupDriversForImagePlane(imageplane, scaling=[1.0, 1.0]):
    driver = imageplane.driver_add('scale', 1).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane)
    driver.expression = str(scaling[0]) + "*(-depth*tan(camAngle/2)*bpy.context.scene.render.resolution_y * bpy.context.scene.render.pixel_aspect_y/(bpy.context.scene.render.resolution_x * bpy.context.scene.render.pixel_aspect_x))"
    driver = imageplane.driver_add('scale', 0).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane)
    driver.expression = str(scaling[1]) + "*-depth*tan(camAngle/2)"


def place_colourbar(camera, colourbar, location=[0,1]):
    """Place the colourbar in front of the camera."""

    colourbar.location = (0, 0, -10)
    colourbar.parent = camera
    SetupDriversForImagePlane(colourbar, scaling=[1.0, 1.0])
    colourbar.location[0] = location[0]
    colourbar.location[1] = location[1]


def add_colourbars(cam):
    """Add colourbars of objects to the scene setup."""

    scn = bpy.context.scene
    tb = scn.tb

    try:
        cbars = bpy.data.objects.get("Colourbars")
    except KeyError:
        pass
    else:
        # TODO: limit number of cbars (5)
        # FIXME: hacky non-general approach (left like this for now because preset handling will be changed anyway)
        cbars_render = []
        for surf in tb.surfaces:
            for scalar in surf.scalars:
                if scalar.showcolourbar:
                    cbar = bpy.data.objects.get("vc_" + scalar.name + "_colourbar")
                    cbars_render.append(cbar)
#         for cbar in cbars.children:
#             cbars_render.append(cbar)
        for i, cbar in enumerate(cbars_render):
            y_offset = i * 0.2
            place_colourbar(cam, cbar, location=[0, 1-y_offset])
