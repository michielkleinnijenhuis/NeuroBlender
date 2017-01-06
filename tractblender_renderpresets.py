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

import os
import numpy as np
from mathutils import Vector

from . import tractblender_import as tb_imp
from . import tractblender_materials as tb_mat
from . import tractblender_utils as tb_utils


# ========================================================================== #
# function to prepare a suitable setup for rendering the scene
# ========================================================================== #


def scene_preset(name="Brain", layer=10):
    """Setup a scene for render."""

    # TODO: manage presets: e.g. put each preset in an empty, etc
    # TODO: option to save presets
    # TODO: set presets up as scenes?
    # TODO: check against all names before preset name is accepted 
    #       and check all import names against preset names 
#     name = 'Preset'
#     new_scene = bpy.data.scenes.new(name)
#     preset = bpy.data.objects.new(name=name, object_data=None)
#     bpy.context.scene.objects.link(preset)

    scn = bpy.context.scene
    tb = scn.tb

    tb_preset = tb.presets[tb.index_presets]
    tb_cam = tb_preset.cameras[0]
    tb_lights = tb_preset.lights
    tb_tab = tb_preset.tables[0]

    name = tb_preset.name

    # check if there are objects to render
    obnames = [[tb_ob.name for tb_ob in tb_coll if tb_ob.is_rendered] 
               for tb_coll in [tb.tracts, tb.surfaces, tb.voxelvolumes]]
    obs = [bpy.data.objects[item] for sublist in obnames for item in sublist]
    if not obs:
        print('no TractBlender objects selected for render')
        return {'CANCELLED'}

    ### create the preset
    # remove the preset if it exists
    delete_preset(name)

    # create objects in the preset
    preset = bpy.data.objects.new(name=name, object_data=None)
    bpy.context.scene.objects.link(preset)
    preset_obs = [preset]

    centre, dims = get_brainbounds(name+"Centre", obs)
    centre.parent = preset
    preset_obs = preset_obs + [centre]

    cam = create_camera(name+"Cam", centre, dims, Vector(tb_cam.cam_view))
    cam.parent = preset
    preset_obs = preset_obs + [cam]

    table = create_table(name+"DissectionTable", centre, dims)
    table.parent = preset
    preset_obs = preset_obs + [table]

    lights = create_lighting(name+"Lights", centre, dims, cam)
    lights.parent = cam
    preset_obs = preset_obs + [lights]
    preset_obs = preset_obs + list(lights.children)

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
        tb_utils.move_to_layer(ob, layer)
    scn.layers[layer] = True

    switch_mode_preset(list(lights.children), [table], tb.mode, tb_cam.cam_view)

    # get object lists
    obs = bpy.data.objects
    tracts     = [obs[t.name] for t in tb.tracts]
    surfaces   = [obs[s.name] for s in tb.surfaces]
    borders    = [obs[b.name] for s in tb.surfaces 
                  for bg in s.bordergroups 
                  for b in bg.borders]
    bordergroups = [obs[bg.name] for s in tb.surfaces 
                    for bg in s.bordergroups] 
    voxelvolumes = [obs[v.name] for v in tb.voxelvolumes]
    vv_children  = [vc for v in voxelvolumes for vc in v.children]

    ### select the right material(s) for each polygon
    renderselections_tracts(tb.tracts)
    renderselections_surfaces(tb.surfaces)
    renderselections_voxelvolumes(tb.voxelvolumes)

    validate_voxelvolume_textures(tb)

    ### split into scenes to render surfaces (cycles) and volume (bi)
    # Cycles Render
    cycles_obs = preset_obs + tracts + surfaces + bordergroups + borders
    prep_scenes(name + '_cycles', 'CYCLES', 'GPU', [0, 1, 10], True, cycles_obs)
    # Blender Render
    internal_obs = [preset] + [centre] + [cam] + voxelvolumes + vv_children
    prep_scenes(name + '_internal', 'BLENDER_RENDER', 'CPU', [2], False, internal_obs)
    # Composited
    prep_scene_composite(scn, name, 'BLENDER_RENDER')

    ### go to the appropriate window views
    bpy.ops.tb.switch_to_main()
    to_camera_view()

    ### any additional settings for render
    scn.cycles.caustics_refractive = False
    scn.cycles.caustics_reflective = False

    return {'FINISHED'}


def delete_preset(name):
    """"""
    # TODO: more flexibility in keeping and naming
#     for ob in scn.objects:
#         if ob.type == 'CAMERA' or ob.type == 'LAMP' or ob.type == 'EMPTY':
# #             if ob.name.startswith('Brain'):
#                 scn.objects.unlink(ob)
#     deltypes = ['CAMERA', 'LAMP', 'EMPTY']

    # unlink all objects from the rendering scenes
    for s in ['_cycles', '_internal']:
        try:
            scn = bpy.data.scenes[name + s]
        except KeyError:
            pass
        else:
            for ob in scn.objects:
                scn.objects.unlink(ob)

    # TODO: delete cameras and lamps
    bpy.ops.object.mode_set(mode='OBJECT')
    for ob in bpy.data.objects:
        ob.select = ob.name.startswith(name)
    bpy.context.scene.objects.active = ob
    bpy.ops.object.delete()


def renderselections_tracts(tb_obs):
    """"""

    for tb_ob in tb_obs:
        ob = bpy.data.objects[tb_ob.name]
        ob.hide_render = not tb_ob.is_rendered

        for tb_ov in tb_ob.scalars:
            if tb_ov.is_rendered:
                prefix = tb_ov.name + '_spl'
                for i, spline in enumerate(ob.data.splines):
                    ms = ob.material_slots
                    splname = prefix + str(i).zfill(8)
                    spline.material_index = ms.find(splname)
        # TODO: tract labels


def renderselections_surfaces(tb_obs):
    """"""

    for tb_ob in tb_obs:
        ob = bpy.data.objects[tb_ob.name]
        ob.hide_render = not tb_ob.is_rendered

        vgs = []
        mat_idxs = []
        for lg in tb_ob.labelgroups:
            if lg.is_rendered:
                vgs, mat_idxs = renderselections_overlays(ob, lg.labels, vgs, mat_idxs)
        vgs, mat_idxs = renderselections_overlays(ob, tb_ob.scalars, vgs, mat_idxs)

        vgs_idxs = [g.index for g in vgs]
        tb_mat.reset_materialslots(ob)  # TODO: also for tracts?
        if vgs is not None:
            tb_mat.assign_materialslots_to_faces(ob, vgs, mat_idxs)

        for bg in tb_ob.bordergroups:
            for b in bg.borders:
                ob = bpy.data.objects[b.name]
                ob.hide_render =  not (bg.is_rendered & b.is_rendered)


def renderselections_voxelvolumes(tb_obs):
    """"""

    for tb_ob in tb_obs:
        ob = bpy.data.objects[tb_ob.name]
        ob.hide_render = not tb_ob.is_rendered

        for tb_ov in tb_ob.scalars:
            overlay = bpy.data.objects[tb_ov.name]
            overlay.hide_render = not tb_ov.is_rendered
        for tb_ov in tb_ob.labelgroups:
            overlay = bpy.data.objects[tb_ov.name]
            overlay.hide_render = not tb_ov.is_rendered
            tex = bpy.data.textures[tb_ov.name]
            for idx, l in enumerate(tb_ov.labels):
                tex.color_ramp.elements[idx + 1].color[3] = l.is_rendered


def renderselections_overlays(ob, tb_ovs, vgs=[], mat_idxs=[]):
    """"""

    for tb_ov in tb_ovs:
        if tb_ov.is_rendered:
            vgs.append(ob.vertex_groups[tb_ov.name])
            mat_idxs.append(ob.material_slots.find(tb_ov.name))

    return vgs, mat_idxs


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


def to_camera_view():
    """Set 3D viewports to camera perspective."""

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces[0].region_3d.view_perspective = 'CAMERA'


def validate_voxelvolume_textures(tb):
    """"Validate or update the texture files for voxelvolumes."""

    for vv in tb.voxelvolumes:
        fp = bpy.data.textures[vv.name].voxel_data.filepath
        if not os.path.isfile(fp):
            fp = tb_imp.prep_nifti(vv.filepath, vv.name, False)[0]
        for vs in vv.scalars:
            fp = bpy.data.textures[vs.name].voxel_data.filepath
            if not os.path.isfile(fp):
                fp = tb_imp.prep_nifti(vs.filepath, vs.name, False)[0]
        for vl in vv.labelgroups:
            fp = bpy.data.textures[vl.name].voxel_data.filepath
            if not os.path.isfile(fp):
                fp = tb_imp.prep_nifti(vl.filepath, vl.name, True)[0]


def get_brainbounds(name, obs):
    """Find the boundingbox, dimensions and centre of the objects."""

    bb_min, bb_max = np.array(find_bbox_coordinates(obs))
    dims = np.subtract(bb_max, bb_min)
    centre_co = bb_min + dims / 2

    centre = bpy.data.objects.new(name=name, object_data=None)
    centre.location = centre_co
    bpy.context.scene.objects.link(centre)

    return centre, dims


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


def create_camera(name, centre=np.array([0,0,0]), dims=np.array([100,100,100]), camview=Vector((1, 1, 1))):
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
                   "LimitDistInClipSphere", centre, cam.clip_end)
    add_constraint(ob, "LIMIT_DISTANCE",
                   "LimitDistOutBrainSphere", centre, max(dims))

    dist = max(dims) * camview
    ob.location = (centre.location[0] + dist[0],
                   centre.location[1] + dist[1],
                   centre.location[2] + dist[2])

    # depth-of-field
#     empty = bpy.data.objects.new('DofEmpty', None)
#     empty.location = centre.location
#     cam.dof_object = empty
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


def create_lighting(name, braincentre, dims, cam, camview=(1, 1, 1)):
    """"""

    scn = bpy.context.scene
    tb = scn.tb
    preset = tb.presets[tb.index_presets]
    tb_lights = preset.lights

    lights = bpy.data.objects.new(name=name, object_data=None)
    lights.location = braincentre.location
    bpy.context.scene.objects.link(lights)

    if preset.lights_enum.startswith("Key"):  # only first
        tb_light = tb_lights[0]
        dimlocation = (3, 2, 1)
        light = create_light(tb_light, braincentre, dims, dimlocation)
        light.parent = lights

    if preset.lights_enum.startswith("Key-"):
        tb_light = tb_lights[1]
        dimlocation = (2, 4, -10)
        light = create_light(tb_light, braincentre, dims, dimlocation)
        light.parent = lights

        tb_light = tb_lights[2]
        dimlocation = (0, 0, 0)
        light = create_light(tb_light, braincentre, dims, dimlocation)
        light.parent = lights

    return lights


def create_light(tb_light, braincentre, dims, loc):
    """"""

    scn = bpy.context.scene

    name = tb_light.name
    type = tb_light.type
    scale = tb_light.size
    colour = tuple(list(tb_light.colour) + [1.0])
    strength = tb_light.strength

    if type == "PLANE":
        light = create_plane(name)
        light.scale = [dims[0]*scale[0], dims[1]*scale[1], 1]
        emission = {'colour': colour, 'strength': strength}
        mat = tb_mat.make_material_emit_cycles(name, emission)
        tb_mat.set_materials(light.data, mat)
    else:
        lamp = bpy.data.lamps.new(name, type)
        light = bpy.data.objects.new(name, object_data=lamp)
        scn.objects.link(light)
        scn.objects.active = light
        light.select = True
        light.data.use_nodes = True
        light.data.node_tree.nodes["Emission"].inputs[1].default_value = 1e+07

    light.location = (dims[0] * loc[0], dims[1] * loc[1], dims[2] * loc[2])
    add_constraint(light, "TRACK_TO", "TrackToBrainCentre", braincentre)

#     bpy.ops.object.constraint_add(type='LIMIT_DISTANCE')
#     bpy.context.object.constraints["Limit Distance"].target = bpy.data.objects["PresetCentre"]

    return light


def create_light_old(name, braincentre, dims, scale, loc, emission):
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


def create_table(name, centre=np.array([0,0,0]), dims=np.array([100,100,100])):
    """Create a table under the objects."""

    tb = bpy.context.scene.tb

    ob = create_plane(name)
    ob.scale = (dims[0]*4, dims[1]*4, 1)
    ob.location = (centre.location[0],
                   centre.location[1],
                   centre.location[2] - dims[2] / 2)

    diffcol = [0.5, 0.5, 0.5, 1.0]
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


def create_colourbars(name, cam):
    """Add colourbars of objects to the scene setup."""

    scn = bpy.context.scene
    tb = scn.tb

    cbars = bpy.data.objects.new(name, None)
    cbars.parent = cam
    bpy.context.scene.objects.link(cbars)

    for tract in tb.tracts:
        for scalar in tract.scalars:
            if scalar.showcolourbar:
                create_colourbar(cbars, scalar, 'tracts_scalars')
    for surf in tb.surfaces:
        for scalar in surf.scalars:
            if scalar.showcolourbar:
                create_colourbar(cbars, scalar, 'surfaces_scalars')

    for vvol in tb.voxelvolumes:
        if vvol.showcolourbar:
            create_colourbar(cbars, vvol, 'voxelvolumes')
        for scalar in vvol.scalars:
            if scalar.showcolourbar:
                create_colourbar(cbars, scalar, 'voxelvolumes_scalars')

    return cbars


def create_colourbar(cbars, cr_ob, type):

    scn = bpy.context.scene
    tb = scn.tb

    cbar_name = tb.presetname + '_' + cr_ob.name + "_colourbar"  # TODO

    cbar_empty = bpy.data.objects.new(cbar_name, None)
    bpy.context.scene.objects.link(cbar_empty)
    cbar_empty.parent = cbars

    cbar, vg = create_imageplane(cbar_name+"_bar")
    cbar.parent = cbar_empty

    cbar.location = [0, 0, -10]
    SetupDriversForImagePlane(cbar, cr_ob)

    if type.startswith('tracts_scalars'):
        pass
#         mat = make_material_overlay_cycles(cbar_name, cbar_name, cbar, cr_ob)
#                 bpy.data.node_groups["TractOvGroup"].nodes["ColorRamp"].color_ramp.elements[0].position = 0.2
    elif type.startswith('surfaces_scalars'):
        mat = bpy.data.materials[cr_ob.name]
        vcs = cbar.data.vertex_colors
        vc = vcs.new(cr_ob.name)
        cbar.data.vertex_colors.active = vc
        cbar = tb_mat.assign_vc(cbar, vc, [vg])
    elif type.startswith('voxelvolumes'):
        mat = bpy.data.materials[cr_ob.name].copy()
        tex = bpy.data.textures[cr_ob.name].copy()
        mat.name = tex.name = cr_ob.name + '_colourbar'
        tex.type = 'BLEND'
        mat.texture_slots[0].texture = tex
        # this does not show the original colorramp

    tb_mat.set_materials(cbar.data, mat)

#     colour = list(cr_ob.textlabel_colour) + [1.]
#     emission = {'colour': colour, 'strength': 1}
#     labmat = tb_mat.make_material_emit_cycles(cr_ob.name + "cbartext", emission)
#     add_colourbar_labels(cbar_name+"_label", cr_ob, cbar, labmat)  # FIXME


def create_imageplane(name="Colourbar"):

    bpy.ops.mesh.primitive_plane_add()
    imageplane = bpy.context.active_object
    imageplane.name = name
    bpy.ops.object.parent_set(type='OBJECT', keep_transform=False)
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='TOGGLE')
    bpy.ops.transform.resize( value=(0.5,0.5,0.5))
    bpy.ops.uv.smart_project(angle_limit=66,island_margin=0, user_area_weight=0)
    bpy.ops.uv.select_all(action='TOGGLE')
    bpy.ops.transform.rotate(value=1.5708, axis=(0,0,1) )
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
    driver.expression = "rel_height"  + \
        " * (-depth * tan(camAngle/2)" + \
        " * res_y * pa_y / (res_x * pa_x))"

    driver = imageplane.driver_add('scale', 0).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane, cr_ob)
    driver.expression = "rel_width * -depth * tan(camAngle / 2)"

    driver = imageplane.driver_add('location', 1).driver
    driver.type = 'SCRIPTED'
    SetupDriverVariables(driver, imageplane, cr_ob)
    driver.expression = "rel_pos1"  + \
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

#     create_var(driver, 'depth', 'TRANSFORMS', 'OBJECT', 
#                imageplane, 'location', 'LOC_Z', 'LOCAL_SPACE')
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


def add_colourbar_labels(presetname, cr_ob, parent_ob, labmat, width=1, height=1):
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
        text.location[0] = elpos * width # - text.dimensions[0] / 2  # FIXME
        if cr_ob.textlabel_placement == "out":
            text.location[1] = -text.scale[0]
        tb_mat.set_materials(text.data, labmat)


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

