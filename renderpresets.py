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


"""The NeuroBlender renderpresets module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements preparations for rendering the scene.
"""


import os
import numpy as np
from mathutils import Vector

import bpy

from . import (materials as nb_ma,
               utils as nb_ut)


# ========================================================================== #
# function to prepare a suitable setup for rendering the scene
# ========================================================================== #


def scene_preset_init(name):

    scn = bpy.context.scene
    nb = scn.nb

    """any additional settings for render"""
    scn.cycles.caustics_refractive = False
    scn.cycles.caustics_reflective = False

    obs = get_render_objects(nb)
    centre_location, dims = get_brainbounds(obs)

    """create objects in the preset"""
    # preset is simply a container with all default blender units (all locked)
    preset = bpy.data.objects.new(name=name, object_data=None)
    scn.objects.link(preset)
    props = [preset.lock_location, preset.lock_rotation, preset.lock_scale]
    for prop in props:
        for dim in prop:
            dim = True
    # centre is an empty the scene centre location and scene dimensions
    centre = bpy.data.objects.new("Centre", None)
    scn.objects.link(centre)
    centre.parent = preset
    centre.location = centre_location
    centre.scale = 0.5 * Vector(dims)

    # box is an empty with location yoked to centre and cuboid dimensions of max(dims)
    # this is mainly for camera and light scaling in the space of the scene
    box = bpy.data.objects.new("Box", None)
    scn.objects.link(box)
    box.parent = preset
    box.location = (0, 0, 0)
    box.scale = 0.5 * Vector([max(dims), max(dims), max(dims)])
    props = {"use_location_x": True,
             "use_location_y": True,
             "use_location_z": True,
             "use_rotation_x": True,
             "use_rotation_y": True,
             "use_rotation_z": True,
             "use_scale_x": False,
             "use_scale_y": False,
             "use_scale_z": False}
    add_constraint(box, "CHILD_OF", "Child Of", centre, props)

    camprops = {"name": "Cam",
                "cam_view": [2.88675, 2.88675, 2.88675],
                "cam_distance": 5,
                "trackobject": "Centre"}
    cam = create_camera(preset, centre, box, camprops)
    camprops["name"] = cam.name

    lights = bpy.data.objects.new("Lights", None)
    scn.objects.link(lights)
    lights.parent = box
    for idx in [0, 1]:
        driver = lights.driver_add("scale", idx).driver
        driver.type = 'SCRIPTED'
        driver.expression = "scale"
        create_var(driver, "scale", 'SINGLE_PROP', 'OBJECT',
                   lights, "scale[2]")
    # setting these all to SUN, because they work well in both BI and CYCLES
    if scn.render.engine == "CYCLES":
#         keystrength = 10000000
#         type = ["SPOT", "SPOT", "POINT"]
        keystrength = 1
        type = ["SUN", "SUN", "SUN"]
    else:
        keystrength = 1
        type = ["SUN", "SUN", "SUN"]
    lp_key = {'name': "Key", 'type': type[0],
              'size': [1.0, 1.0], 'colour': (1.0, 1.0, 1.0),
              'strength': keystrength, 'location': (1, 4, 6)}
    lp_fill = {'name': "Fill", 'type': type[1],
               'size': [1.0, 1.0], 'colour': (1.0, 1.0, 1.0),
               'strength': 0.2*keystrength, 'location': (4, -1, 1)}
    lp_back = {'name': "Back", 'type': type[2],
               'size': [1.0, 1.0], 'colour': (1.0, 1.0, 1.0),
               'strength': 0.1*keystrength, 'location': (-4, -4, 3)}
    for lightprops in [lp_key, lp_fill, lp_back]:
        light = create_light(preset, centre, box, lights, lightprops)
        lightprops["name"] = light.name

    tableprops = {"name": "Table",
                  "scale": (4, 4, 1),
                  "location": (0, 0, -1)}
    table = create_table(preset, centre, tableprops)
    tableprops["name"] = table.name
    table.hide = True
    table.hide_render = True

    """add newly created objects to collections"""
    presetprops = {"name": name, "centre": centre.name,
                   "dims": dims, "box": box.name, "lightsempty": lights.name}
    nb_preset = nb_ut.add_item(nb, "presets", presetprops)
    nb_ut.add_item(nb_preset, "cameras", camprops)
    nb_preset.cameras[0].trackobject = "Centre"  # force update function
    for lightprops in [lp_key, lp_fill, lp_back]:
        nb_ut.add_item(nb_preset, "lights", lightprops)
    nb_ut.add_item(nb_preset, "tables", tableprops)

    """switch to view"""
    bpy.ops.nb.switch_to_main()
    to_camera_view()


def scene_preset(name="Brain", layer=10):
    """Setup a scene for render."""

    # TODO: option to save presets
    # TODO: set presets up as scenes?
#     name = 'Preset'
#     new_scene = bpy.data.scenes.new(name)
#     preset = bpy.data.objects.new(name=name, object_data=None)
#     bpy.context.scene.objects.link(preset)

    scn = bpy.context.scene
    nb = scn.nb

    nb_preset = nb.presets[nb.index_presets]
    nb_cam = nb_preset.cameras[0]
    nb_lights = nb_preset.lights
    nb_tab = nb_preset.tables[0]
    nb_anims = nb.animations

    name = nb_preset.name

    preset = bpy.data.objects[nb_preset.name]
    centre = bpy.data.objects[nb_preset.centre]
    dims = nb_preset.dims
    cam = bpy.data.objects[nb_preset.cameras[0].name]
    table = bpy.data.objects[nb_preset.tables[0].name]
    lights = bpy.data.objects[nb_preset.lightsempty]

    preset_obs = [preset, centre, cam, table, lights] + list(lights.children)

#     # remove the preset if it exists
#     delete_preset(name)

    # call animation setup here

    cbars = create_colourbars(name+"Colourbars", cam)
#     cbars.parent = cam  # already made it parent
    preset_obs = preset_obs + [cbars]
    preset_obs = preset_obs + list(cbars.children)
    preset_obs = preset_obs + [label for cbar in list(cbars.children)
                               for label in list(cbar.children)]
#     cbarlabels = [l for cbar in cbars for l in list(cbar.children)]
#     preset_obs = preset_obs + [cbars]
#     preset_obs = preset_obs + list(cbars.children)

    for ob in preset_obs:
        nb_ut.move_to_layer(ob, layer)
    scn.layers[layer] = True

    switch_mode_preset(list(lights.children), [table],
                       nb.settingprops.mode, nb_cam.cam_view)

    # get object lists
    obs = bpy.data.objects
    tracts = [obs[t.name] for t in nb.tracts]
    surfaces = [obs[s.name] for s in nb.surfaces]
    borders = [obs[b.name] for s in nb.surfaces
               for bg in s.bordergroups
               for b in bg.borders]
    bordergroups = [obs[bg.name] for s in nb.surfaces
                    for bg in s.bordergroups]
    voxelvolumes = [obs[v.name] for v in nb.voxelvolumes]
    vv_children = [vc for v in voxelvolumes for vc in v.children]

    """select the right material(s) for each polygon"""
    renderselections_tracts(nb.tracts)
    renderselections_surfaces(nb.surfaces)
    renderselections_voxelvolumes(nb.voxelvolumes)

    validate_voxelvolume_textures(nb)

    """split into scenes to render surfaces (cycles) and volume (bi)"""
    # Cycles Render
    cycles_obs = preset_obs + tracts + surfaces + bordergroups + borders
    prep_scenes(name + '_cycles', 'CYCLES', 'GPU',
                [0, 1, 10], True, cycles_obs, nb_preset)
    # Blender Render
    internal_obs = [preset] + [centre] + [cam] + voxelvolumes + vv_children
    prep_scenes(name + '_internal', 'BLENDER_RENDER', 'CPU',
                [2], False, internal_obs, nb_preset)
    # Composited
    prep_scene_composite(scn, name, 'BLENDER_RENDER')

    """go to the appropriate window views"""
    bpy.ops.nb.switch_to_main()
    to_camera_view()

    return {'FINISHED'}


def renderselections_tracts(nb_obs):
    """"""

    for nb_ob in nb_obs:
        ob = bpy.data.objects[nb_ob.name]
        ob.hide_render = not nb_ob.is_rendered

        for nb_ov in nb_ob.scalars:
            if nb_ov.is_rendered:
                prefix = nb_ov.name + '_spl'
                for i, spline in enumerate(ob.data.splines):
                    ms = ob.material_slots
                    splname = prefix + str(i).zfill(8)
                    spline.material_index = ms.find(splname)
        # TODO: tract labels


def renderselections_surfaces(nb_obs):
    """"""

    for nb_ob in nb_obs:
        ob = bpy.data.objects[nb_ob.name]
        ob.hide_render = not nb_ob.is_rendered

        vgs = []
        mat_idxs = []
        for lg in nb_ob.labelgroups:
            if lg.is_rendered:
                vgs, mat_idxs = renderselections_overlays(ob, lg.labels,
                                                          vgs, mat_idxs)
        for sg in nb_ob.scalargroups:
            if sg.is_rendered:
                vgs, mat_idxs = renderselections_overlays(ob, sg.scalars,
                                                          vgs, mat_idxs)
        vgs, mat_idxs = renderselections_overlays(ob, nb_ob.scalars,
                                                  vgs, mat_idxs)

        vgs_idxs = [g.index for g in vgs]
        nb_ma.reset_materialslots(ob)  # TODO: also for tracts?
        if vgs is not None:
            nb_ma.assign_materialslots_to_faces(ob, vgs, mat_idxs)

        for bg in nb_ob.bordergroups:
            for b in bg.borders:
                ob = bpy.data.objects[b.name]
                ob.hide_render = not (bg.is_rendered & b.is_rendered)


def renderselections_voxelvolumes(nb_obs):
    """"""

    for nb_ob in nb_obs:
        ob = bpy.data.objects[nb_ob.name]
        ob.hide_render = not nb_ob.is_rendered

        for nb_ov in nb_ob.scalars:
            overlay = bpy.data.objects[nb_ov.name]
            overlay.hide_render = not nb_ov.is_rendered
        for nb_ov in nb_ob.labelgroups:
            overlay = bpy.data.objects[nb_ov.name]
            overlay.hide_render = not nb_ov.is_rendered
            tex = bpy.data.textures[nb_ov.name]
            for idx, l in enumerate(nb_ov.labels):
                tex.color_ramp.elements[idx + 1].color[3] = l.is_rendered


def renderselections_overlays(ob, nb_ovs, vgs=[], mat_idxs=[]):
    """"""

    for nb_ov in nb_ovs:
        if nb_ov.is_rendered:
            vgs.append(ob.vertex_groups[nb_ov.name])
            mat_idxs.append(ob.material_slots.find(nb_ov.name))

    return vgs, mat_idxs


def prep_scenes(name, engine, device, layers, use_sky, obs, nb_preset):
    """"""

    scns = bpy.data.scenes
    if scns.get(name) is not None:
        scn = scns.get(name)
    else:
        bpy.ops.scene.new(type='NEW')
        scn = scns[-1]
        scn.name = name

    scn.frame_start = nb_preset.frame_start
    scn.frame_end = nb_preset.frame_end

#     scn.render.engine = engine
    scn.cycles.device = device
    for l in range(20):
        scn.layers[l] = l in layers
        scn.render.layers[0].layers[l] = l in layers
    scn.render.layers[0].use_sky = use_sky
    scn.nb.is_enabled = False

#     linked_obs = [ob.name for ob in scn.objects]
    for ob in scn.objects:
        scn.objects.unlink(ob)
    for ob in obs:
        if ob is not None:
            scn.objects.link(ob)

#     scn.update()

    return scn


def prep_scene_composite(scn, name, engine):
    """"""

#     scns = bpy.data.scenes
#     if scns.get(name) is not None:
#         return
#     bpy.ops.scene.new(type='NEW')
#     scn = bpy.data.scenes[-1]
#     scn.name = name
#     scn.nb.is_enabled = False

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
    rlayer1.scene = bpy.data.scenes[name + '_cycles']
    rlayer1.location = 400, 200

    rlayer2 = nodes.new("CompositorNodeRLayers")
    rlayer2.scene = bpy.data.scenes[name + '_internal']
    rlayer2.location = 400, -200

    links.new(mix.outputs["Image"], comp.inputs["Image"])
    links.new(rlayer1.outputs["Image"], mix.inputs[1])
    links.new(rlayer2.outputs["Image"], mix.inputs[2])


def switch_mode_preset(lights, tables, newmode, cam_view):
    """Toggle rendering of lights and table."""

    for light in lights:
        light.hide = newmode == "scientific"
        light.hide_render = newmode == "scientific"
    for table in tables:
        state = (cam_view[2] < 0) | (newmode == "scientific")
        table.hide = state
        table.hide_render = state


def validate_voxelvolume_textures(nb):
    """"Validate or update the texture files for voxelvolumes."""

    ivv = bpy.types.NB_OT_import_voxelvolumes
    for vv in nb.voxelvolumes:
        fp = bpy.data.textures[vv.name].voxel_data.filepath
        if not os.path.isfile(fp):
            fp = ivv.prep_nifti(vv.filepath, vv.name, False)[0]
        for vs in vv.scalars:
            fp = bpy.data.textures[vs.name].voxel_data.filepath
            if not os.path.isfile(fp):
                fp = ivv.prep_nifti(vs.filepath, vs.name, False)[0]
        for vl in vv.labelgroups:
            fp = bpy.data.textures[vl.name].voxel_data.filepath
            if not os.path.isfile(fp):
                fp = ivv.prep_nifti(vl.filepath, vl.name, True)[0]


def get_render_objects(nb):
    """Gather all objects listed for render."""

    obnames = [[nb_ob.name for nb_ob in nb_coll if nb_ob.is_rendered]
               for nb_coll in [nb.tracts, nb.surfaces, nb.voxelvolumes]]

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
        bb_min, bb_max = np.array(find_bbox_coordinates(obs))
        dims = np.subtract(bb_max, bb_min)
        centre_location = bb_min + dims / 2

    return centre_location, dims


def find_bbox_coordinates(obs):
    """Find the extreme dimensions in the geometry."""

    bb_world = [ob.matrix_world * Vector(bbco)
                for ob in obs for bbco in ob.bound_box]
    bb_min = np.amin(np.array(bb_world), 0)
    bb_max = np.amax(np.array(bb_world), 0)

    return bb_min, bb_max


# ========================================================================== #
# camera
# ========================================================================== #


def create_camera(preset, centre, box, camprops):
    """Add a camera to the scene."""

    scn = bpy.context.scene

    camdata = bpy.data.cameras.new(name=camprops["name"])
    camdata.show_name = True
    camdata.draw_size = 0.2
    camdata.type = 'PERSP'
    camdata.lens = 35
    camdata.lens_unit = 'MILLIMETERS'
    camdata.shift_x = 0.0
    camdata.shift_y = 0.0
    camdata.clip_start = box.scale[0] / 5
    camdata.clip_end = box.scale[0] * 10

    cam = bpy.data.objects.new(camprops["name"], camdata)
    cam.parent = preset
    cam.location = camprops["cam_view"]
    scn.objects.link(cam)

    add_constraint(cam, "CHILD_OF", "Child Of", box)
    add_constraint(cam, "TRACK_TO", "TrackToObject", centre)
#     add_cam_constraints(cam)

    # depth-of-field
#     empty = bpy.data.objects.new('DofEmpty', None)
#     empty.location = centre.location
#     camdata.dof_object = empty
#     scn.objects.link(empty)
    # TODO: let the empty follow the brain outline
#     cycles = camdata.cycles
#     cycles.aperture_type = 'FSTOP'
#     cycles.aperture_fstop = 5.6

    scn.camera = cam

    return cam


def to_camera_view():
    """Set 3D viewports to camera perspective."""

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces[0].region_3d.view_perspective = 'CAMERA'


def add_constraint(ob, type, name, target, val=None):
    """Add a constraint to the camera."""

    cns = ob.constraints.new(type)
    cns.name = name
    cns.target = target
    cns.owner_space = 'WORLD'
    cns.target_space = 'WORLD'
    if name.startswith('TrackTo'):
        cns.track_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
#         cns.owner_space = 'LOCAL'
#         cns.target_space = 'LOCAL'
    elif name.startswith('LockedTrack'):
        pass
#         cns.track_axis = 'TRACK_NEGATIVE_Z'
#         cns.lock_axis = 'UP_Y'
    elif name.startswith('LimitDistOut'):
        cns.limit_mode = 'LIMITDIST_OUTSIDE'
        cns.distance = val
    elif name.startswith('LimitDistIn'):
        cns.limit_mode = 'LIMITDIST_INSIDE'
        cns.distance = val
    elif name.startswith('FollowPath'):
        cns.forward_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
        cns.use_curve_follow = val == "TrackPath"
#         if val == 'TrackPath':
#             cns.forward_axis = 'TRACK_NEGATIVE_Z'
#             cns.up_axis = 'UP_Y'
    elif name.startswith('Child Of'):
        if val is not None:
            for k, v in val.items():
                exec("cns.%s = v" % k)

    return cns


# ========================================================================== #
# lights
# ========================================================================== #


def create_lighting_old(name, braincentre, dims, cam, camview=(1, 1, 1)):
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
    main = create_light(lname, braincentre, dims,
                        dimscale, dimlocation, emission)
    main.parent = lights

    lname = name + "Back"
    dimscale = (0.1, 0.1)
#     dimlocation = [-2*camview[0], 2*camview[1], 1*camview[2]]
    dimlocation = (2, 4, -10)
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 30}
    aux = create_light(lname, braincentre, dims,
                       dimscale, dimlocation, emission)
    aux.parent = lights

    lname = name + "Fill"
    scale = (0.1, 0.1)
    dimlocation = (0, 0, 0)
    emission = {'colour': (1.0, 1.0, 1.0, 1.0), 'strength': 100}
    high = create_light(lname, braincentre, dims,
                        scale, dimlocation, emission)
    high.parent = lights

    return lights


def create_light(preset, centre, box, lights, lightprops):
    """"""

    scn = bpy.context.scene
    engine = scn.render.engine

    name = lightprops['name']
    type = lightprops['type']
    scale = lightprops['size']
    colour = tuple(list(lightprops['colour']) + [1.0])
    strength = lightprops['strength']

    if type == "PLANE":
        light = create_plane(name)
        light.scale = [scale[0]*2, scale[1]*2, 1]
        emission = {'colour': colour, 'strength': strength}
        mat = nb_ma.make_material_emit_cycles(light.name, emission)
        nb_ma.set_materials(light.data, mat)
    else:
        lamp = bpy.data.lamps.new(name, type)
        light = bpy.data.objects.new(lamp.name, object_data=lamp)
        scn.objects.link(light)
        scn.objects.active = light
        light.select = True

        if not engine == "CYCLES":
            scn.render.engine = "CYCLES"
        light.data.use_nodes = True
        if type != "HEMI":
            light.data.shadow_soft_size = 50
        node = light.data.node_tree.nodes["Emission"]
        node.inputs[1].default_value = strength

        scn.render.engine = "BLENDER_RENDER"
        light.data.energy = strength

    scn.render.engine = engine

    light.parent = lights
    light.location = lightprops['location']

#     add_constraint(light, "CHILD_OF", "Child Of", box)
    add_constraint(light, "TRACK_TO", "TrackToObject", centre)

    return light


def create_light_old(name, braincentre, dims, scale, loc, emission):
    """"""

    ob = create_plane(name)
    ob.scale = [dims[0]*scale[0], dims[1]*scale[1], 1]
    ob.location = (dims[0] * loc[0], dims[1] * loc[1], dims[2] * loc[2])
    add_constraint(ob, "TRACK_TO", "TrackToBrainCentre", braincentre)
    mat = nb_ma.make_material_emit_cycles(name, emission)
#     mat = make_material_emit_internal(name, emission, True)
    nb_ma.set_materials(ob.data, mat)

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


def create_table(preset, centre, tableprops):
    """Create a table under the objects."""

    ob = create_plane(tableprops["name"])
    ob.scale = tableprops["scale"]
    ob.location = tableprops["location"]

    diffcol = [0.5, 0.5, 0.5, 1.0]
    mat = nb_ma.make_cr_mat_basic(ob.name, diffcol, mix=0.8)
    nb_ma.set_materials(ob.data, mat)

    ob.parent = centre
#     add_constraint(ob, "CHILD_OF", "Child Of", centre)

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


def create_colourbars(name, cam):
    """Add colourbars of objects to the scene setup."""

    scn = bpy.context.scene
    nb = scn.nb

    cbars = bpy.data.objects.new(name, None)
    cbars.parent = cam
    bpy.context.scene.objects.link(cbars)

    for tract in nb.tracts:
        for scalargroup in tract.scalargroups:
            if scalargroup.showcolourbar:
                create_colourbar(cbars, scalargroup, 'tracts_scalargroups')
    for surf in nb.surfaces:
        for scalargroup in surf.scalargroups:
            if scalargroup.showcolourbar:
                create_colourbar(cbars, scalargroup, 'surfaces_scalargroups')

    for vvol in nb.voxelvolumes:
        if vvol.showcolourbar:
            create_colourbar(cbars, vvol, 'voxelvolumes')
        for scalargroup in vvol.scalargroups:
            if scalargroup.showcolourbar:
                create_colourbar(cbars, scalargroup, 'voxelvolumes_scalargroups')

    return cbars


def create_colourbar(cbars, cr_ob, type):

    scn = bpy.context.scene
    nb = scn.nb

    cbar_name = nb.presetname + '_' + cr_ob.name + "_colourbar"  # TODO

    cbar_empty = bpy.data.objects.new(cbar_name, None)
    bpy.context.scene.objects.link(cbar_empty)
    cbar_empty.parent = cbars

    cbar, vg = create_imageplane(cbar_name+"_bar")
    cbar.parent = cbar_empty

    cbar.location = [0, 0, -10]
    SetupDriversForImagePlane(cbar, cr_ob)

    if type.startswith('tracts_scalars'):
        pass
        # mat = make_cr_mat_surface_sg(cr_ob)
        # cr = bpy.data.node_groups["TractOvGroup"].nodes["ColorRamp"]
        # cr.color_ramp.elements[0].position = 0.2
    elif type.startswith('surfaces_scalars'):
        mat = bpy.data.materials[cr_ob.name]
        vcs = cbar.data.vertex_colors
        vc = vcs.new(cr_ob.name)
        cbar.data.vertex_colors.active = vc
        cbar = nb_ma.assign_vc(cbar, vc, [vg])
    elif type.startswith('voxelvolumes'):
        mat = bpy.data.materials[cr_ob.name].copy()
        tex = bpy.data.textures[cr_ob.name].copy()
        mat.name = tex.name = cr_ob.name + '_colourbar'
        tex.type = 'BLEND'
        mat.texture_slots[0].texture = tex
        # this does not show the original colorramp

    nb_ma.set_materials(cbar.data, mat)

    # colour = list(cr_ob.textlabel_colour) + [1.]
    # emission = {'colour': colour, 'strength': 1}
    # labmat = nb_ma.make_material_emit_cycles(cr_ob.name + "cbartext", emission)
    # add_colourbar_labels(cbar_name+"_label", cr_ob, cbar, labmat)  # FIXME


def create_imageplane(name="Colourbar"):

    bpy.ops.mesh.primitive_plane_add()
    imageplane = bpy.context.active_object
    imageplane.name = name
    bpy.ops.object.parent_set(type='OBJECT', keep_transform=False)
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='TOGGLE')
    bpy.ops.transform.resize(value=(0.5, 0.5, 0.5))
    bpy.ops.uv.smart_project(angle_limit=66,
                             island_margin=0,
                             user_area_weight=0)
    bpy.ops.uv.select_all(action='TOGGLE')
    bpy.ops.transform.rotate(value=1.5708, axis=(0, 0, 1))
    bpy.ops.object.editmode_toggle()

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=100)
    bpy.ops.object.mode_set(mode='OBJECT')

    # TODO: vertical option
    vg = imageplane.vertex_groups.new(name)
    for i, v in enumerate(imageplane.data.vertices):
        vg.add([i], v.co.x, "REPLACE")
    vg.lock_weight = True

    return imageplane, vg


def SetupDriversForImagePlane(imageplane, cr_ob):
    """"""

    driver = imageplane.driver_add('scale', 1).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane, cr_ob)
    driver.expression = "rel_height" + \
        " * (-depth * tan(camAngle/2)" + \
        " * res_y * pa_y / (res_x * pa_x))"

    driver = imageplane.driver_add('scale', 0).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane, cr_ob)
    driver.expression = "rel_width * -depth * tan(camAngle / 2)"

    driver = imageplane.driver_add('location', 1).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane, cr_ob)
    driver.expression = "rel_pos1" + \
        " * ( (-depth * tan(camAngle / 2)" + \
        " * res_y * pa_y / (res_x * pa_x))" + \
        " - rel_height * ( -depth * tan(camAngle / 2)" + \
        " * res_y * pa_y / (res_x * pa_x) ) )"

    driver = imageplane.driver_add('location', 0).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane, cr_ob)
    driver.expression = "rel_pos0 * ( -depth * tan(camAngle / 2)" + \
                        " - rel_width * -depth * tan(camAngle / 2) )"


def SetupDriverVariables(driver, imageplane, cr_ob):
    """"""

    scn = bpy.context.scene

    create_var(driver, 'camAngle', 'SINGLE_PROP', 'OBJECT',
               imageplane.parent.parent.parent, "data.angle")

    # create_var(driver, 'depth', 'TRANSFORMS', 'OBJECT',
    #            imageplane, 'location', 'LOC_Z', 'LOCAL_SPACE')
    depth = driver.variables.new()
    depth.name = 'depth'
    depth.type = 'TRANSFORMS'
    depth.targets[0].id = imageplane
    depth.targets[0].data_path = 'location'
    depth.targets[0].transform_type = 'LOC_Z'
    depth.targets[0].transform_space = 'LOCAL_SPACE'

    create_var(driver, 'res_x', 'SINGLE_PROP', 'SCENE',
               scn, "render.resolution_x")
    create_var(driver, 'res_y', 'SINGLE_PROP', 'SCENE',
               scn, "render.resolution_y")
    create_var(driver, 'pa_x', 'SINGLE_PROP', 'SCENE',
               scn, "render.pixel_aspect_x")
    create_var(driver, 'pa_y', 'SINGLE_PROP', 'SCENE',
               scn, "render.pixel_aspect_y")

    create_var(driver, 'rel_width', 'SINGLE_PROP', 'SCENE',
               scn, cr_ob.path_from_id() + ".colourbar_size[0]")
    create_var(driver, 'rel_height', 'SINGLE_PROP', 'SCENE',
               scn, cr_ob.path_from_id() + ".colourbar_size[1]")
    create_var(driver, 'rel_pos0', 'SINGLE_PROP', 'SCENE',
               scn, cr_ob.path_from_id() + ".colourbar_position[0]")
    create_var(driver, 'rel_pos1', 'SINGLE_PROP', 'SCENE',
               scn, cr_ob.path_from_id() + ".colourbar_position[1]")


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


def add_colourbar_labels(presetname, cr_ob, parent_ob, labmat,
                         width=1, height=1):
    """Add labels to colourbar."""

    nt = bpy.data.materials[cr_ob.name].node_tree
    ramp = nt.nodes["ColorRamp"]

    els = ramp.color_ramp.elements
    nnels = cr_ob.nn_elements
    for el, nnel in zip(els, nnels):
        nnelpos = nnel.nn_position
        elpos = el.position

        labtext = "%4.2f" % nnelpos  # TODO: adaptive formatting

        bpy.ops.object.text_add()
        text = bpy.context.scene.objects.active
        text.name = presetname + ":" + labtext
        text.parent = parent_ob
        text.data.body = labtext
        print(text.dimensions)
        bpy.context.scene.update()
        print(text.dimensions)

        text.scale[0] = height * cr_ob.textlabel_size
        text.scale[1] = height * cr_ob.textlabel_size
        print(text.dimensions)
        bpy.context.scene.update()
        print(text.dimensions)
        text.location[0] = elpos * width  # - text.dimensions[0] / 2  # FIXME
        if cr_ob.textlabel_placement == "out":
            text.location[1] = -text.scale[0]
        nb_ma.set_materials(text.data, labmat)


# def create_colourbar_old(name="Colourbar", width=0.5, height=0.1):
#     """Create a plane of dimension width x height."""
#
#     scn = bpy.context.scene
#
#     me = bpy.data.meshes.new(name)
#     ob = bpy.data.objects.new(name, me)
#     scn.objects.link(ob)
#     scn.objects.active = ob
#     ob.select = True
#
#     verts = [(0, 0, 0), (0, height, 0), (width, height, 0), (width, 0, 0)]
#     faces = [(3, 2, 1, 0)]
#     me.from_pydata(verts, [], faces)
#     me.update()
#
#     saved_location = scn.cursor_location.copy()
#     scn.cursor_location = (0.0,0.0,0.0)
#     bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
#     scn.cursor_location = saved_location
#
#     return ob
