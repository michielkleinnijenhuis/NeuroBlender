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

from . import tractblender_materials as tb_mat
from . import tractblender_utils as tb_utils

# ========================================================================== #
# function to prepare a suitable setup for rendering the scene
# ========================================================================== #


def scene_preset():
    """"""

    # TODO: manage presets: e.g. put each preset in an empty, etc
    # TODO: option to save presets
    # TODO: copy colourbars to cam instead of moving them around

    scn = bpy.context.scene
    tb = scn.tb

#     for ob in scn.objects:
#         if ob.type == 'CAMERA' or ob.type == 'LAMP' or ob.type == 'EMPTY':
# #             if ob.name.startswith('Brain'):
#                 scn.objects.unlink(ob)
#     deltypes = ['CAMERA', 'LAMP', 'EMPTY']
    prefix = 'Brain'
    delete_preset(prefix)

    obs = [ob for ob in bpy.data.objects
           if ((ob.type not in ['CAMERA', 'LAMP', 'EMPTY']) and
               (not ob.name.startswith('BrainDissectionTable')))]
    if not obs:
        print('no objects were found')
        return {'FINISHED'}

    bbox = np.array(find_bbox_coordinates(obs))
    dims = np.subtract(bbox[:, 1], bbox[:, 0])
    midpoint = bbox[:, 0] + dims / 2
    bc = bpy.data.objects.new(name='BrainCentre', object_data=None)
    bc.location = midpoint
    bpy.context.scene.objects.link(bc)

    # TODO: LEFT RIGHT ANT SUP INF SUP
    camview = tb.camview
    quadrants = {'RightAntSup': (1, 1, 1),
                 'RightAntInf': (1, 1, -1),
                 'RightPostSup': (1, -1, 1),
                 'RightPostInf': (1, -1, -1),
                 'LeftAntSup': (-1, 1, 1),
                 'LeftAntInf': (-1, 1, -1),
                 'LeftPostSup': (-1, -1, 1),
                 'LeftPostInf':  (-1, -1, -1)}
    quadrant = quadrants[camview]
    cam = create_camera(bc, bbox, dims, quadrant)
    if not camview.endswith('Inf'):
        table = create_table(bc, bbox, dims)
    else:
        table = None

    lights = create_lighting(bc, bbox, dims, quadrant)

    layer = 10
    obs = [bc] + [cam] + [table] + lights
    for ob in obs:
        if ob is not None:
            tb_utils.move_to_layer(ob, layer)
    scn.layers[layer] = True

    scn.cycles.caustics_refractive = False
    scn.cycles.caustics_reflective = False

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
            place_colourbar(cam, cbar, location=[0,1-y_offset])

    # TODO: go to camera view?
    # TODO: different camviews to layers?

    return {'FINISHED'}


def delete_preset(prefix):
    """"""
    # TODO: more flexibility in keeping and naming

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


def delete_cube():
    """Delete the default Blender Cube."""
    try:
        bpy.data.objects['Cube'].select = True
        bpy.ops.object.delete()
        print(" --- Cube deleted. Let's go!")
    except:
        print(" --- Cube not found. Let's go!")


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


# ========================================================================== #
# camera
# ========================================================================== #


def create_camera(braincentre, bbox, dims, quadrant=(1, 1, 1)):
    """"""

    scn = bpy.context.scene

    cam = bpy.data.cameras.new(name="BrainCam")
    ob = bpy.data.objects.new("BrainCam", cam)
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

    add_cam_constraint(ob, "TRACK_TO",
                       "TrackToBrainCentre", braincentre)
    add_cam_constraint(ob, "LIMIT_DISTANCE",
                       "LimitDistInClipBox", braincentre, cam.clip_end)
    add_cam_constraint(ob, "LIMIT_DISTANCE",
                       "LimitDistOutBrainBox", braincentre, max(dims))

    # TODO: tie in with orientation matrix (RAS layout assumed for now)
    dimlocation = [4*quadrant[0], 3*quadrant[1], 2*quadrant[2]]
    ob.location = (braincentre.location[0] + dims[0] * dimlocation[0],
                   braincentre.location[1] + dims[1] * dimlocation[1],
                   braincentre.location[2] + dims[2] * dimlocation[2])

    # depth-of-field
    empty = bpy.data.objects.new('DofEmpty', None)
    empty.location = braincentre.location
    cam.dof_object = empty
    # TODO: let the empty follow the brain outline
#     cycles = cam.cycles
#     cycles.aperture_type = 'FSTOP'
#     cycles.aperture_fstop = 5.6

    scn.camera = ob
    return ob


def add_cam_constraint(ob, type, name, target, val=None):
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


def create_lighting(braincentre, bbox, dims, quadrant=(1, 1, 1)):
    """"""

#     view = (1, 1, 1)
    # TODO: constraints to have the light follow cam?

    name = "BrainLightMain"
    dimscale = (0.5, 0.5)
    dimlocation = [5*quadrant[0], 2*quadrant[1], 3*quadrant[2]]
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 50}
    main = create_light(name, braincentre, bbox, dims,
                        dimscale, dimlocation, emission)

    name = "BrainLightAux"
    dimscale = (0.1, 0.1)
    dimlocation = [-2*quadrant[0], 2*quadrant[1], 1*quadrant[2]]
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 30}
    aux = create_light(name, braincentre, bbox, dims,
                       dimscale, dimlocation, emission)

    name = "BrainLightHigh"
    dimscale = (0.1, 0.1)
    dimlocation = (10, -10, 5)
    dimlocation = [10*quadrant[0], -10*quadrant[1], 5*quadrant[2]]
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 100}
    high = create_light(name, braincentre, bbox, dims,
                        dimscale, dimlocation, emission)

    return [main, aux, high]

def create_light(name, braincentre, bbox, dims, scale, loc, emission):
    """"""

    ob = create_plane(name)
    ob.scale = [dims[0]*scale[0], dims[1]*scale[1], 1]
    ob.location = (braincentre.location[0] + dims[0] * loc[0],
                   braincentre.location[1] + dims[1] * loc[1],
                   braincentre.location[2] + dims[2] * loc[2])
    add_cam_constraint(ob, "TRACK_TO", "TrackToBrainCentre", braincentre)
    mat = tb_mat.make_material_emit_cycles(name, emission)
    tb_mat.set_material(ob.data, mat)

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


def create_table(braincentre, bbox, dims):
    """"""

    name = "BrainDissectionTable"
    ob = create_plane(name)
    ob.scale = (5000, 5000, 1)  # TODO: use dims
    ob.location = (braincentre.location[0],
                   braincentre.location[1],
                   bbox[2, 0])

    diffuse = {'colour': (0.5, 0.5, 0.5, 1.0), 'roughness': 0.1}
    glossy = {'colour': (1.0, 1.0, 1.0, 1.0), 'roughness': 0.1}
    mat = tb_mat.make_material_basic_cycles(name, diffuse, glossy, mix=0.8)
    tb_mat.set_material(ob.data, mat)

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
