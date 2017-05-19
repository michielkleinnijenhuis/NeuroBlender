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


"""The NeuroBlender YTproj_DB module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module contains an example script for
generating a simple voxelvolume animation.
"""


import os

import bpy

from NeuroBlender import nb_ut


def import_volume(context, datadir, T1):
    """Load the T1 volume."""

    scn = context.scene
    nb = scn.nb

    # import volume <datadir>/<T1>.nii.gz with name <T1>
    # i.e. write png's to texdir
    bpy.ops.nb.import_voxelvolumes(directory=datadir,
                                   files=[{"name": "{}.nii.gz".format(T1)}],
                                   name=T1,
                                   texdir="//voltex_{}".format(T1))

    vvol = nb.voxelvolumes[0]
    vvol.sliceposition = (0, 0, 0)

    # tweak texture settings to give it a clean and smooth appearance
    tex = bpy.data.textures[T1]
    cre = tex.color_ramp.elements
    cre[0].position = 0.04
    cre[1].position = 0.5
    cre[0].color = (0.161539, 0.0307693, 0.00769232, 0)
    cre[1].color = (0.757397, 0.650142, 0.610706, 1)
    tex.voxel_data.interpolation = 'TRICUBIC_BSPLINE'

    return vvol


def create_preset(context, presetname="Preset"):
    """Create the scene."""

    scn = context.scene
    nb = scn.nb

    # add a standard scene setup
    bpy.ops.nb.add_preset(name=presetname)
    preset = nb.presets[presetname]

    cam = preset.cameras[0]
    cam.cam_distance = 3.5
    centre = bpy.data.objects.get(preset.centre)
    centre.location[2] = -12

    for light in preset.lights:
        light.type = 'HEMI'

#     # hiding rendering of lights in this volume rendering example
#     for l in ["Key", "Fill", "Back"]:
#         bpy.data.objects[l].hide_render = True

    return preset


# camera rotation animation
def animate_camera_rotation(context, preset, animname="camZ"):
    """Create a camera rotation around Z."""

    scn = context.scene
    nb = scn.nb

    bpy.ops.nb.import_animations(name=animname)
    animname = "{}.000".format(animname)  # TODO: get rid of forcefill
    anim = preset.animations[animname]
    anim.reverse = True
    anim.repetitions = 1.5
    anim.frame_end = 250
    bpy.ops.nb.add_campath(name="CP_Z")
    anim.campaths_enum = "CP_Z"

    return anim


# slice animation
def animate_volume_slicer(context, vvol, keyframes, index=2):
    """Create a slicing animation building and removing the brain along Z."""

    scn = context.scene
    nb = scn.nb

    for k, v in keyframes.items():
        scn.frame_set(k)
        vvol.slicethickness[index] = v[0]
        vvol.keyframe_insert("slicethickness", index)

    action = bpy.data.actions['SceneAction']
    dpath = '{}.slicethickness'.format(vvol.path_from_id())
    fcu = action.fcurves.find(dpath, index)
    for kfp in fcu.keyframe_points:
        kfp.interpolation = keyframes[kfp.co[0]][1]
        kfp.easing = keyframes[kfp.co[0]][2]


# def animate_volume_slicer(context, preset, T1, animname="slcZ",
#                           range, offset=0, reverse=False):
#     """Create a slicing animation building and removing the brain along Z."""
# 
#     scn = context.scene
#     nb = scn.nb
# 
#     bpy.ops.nb.import_animations(name=animname)
#     animname = "{}.000".format(animname)  # TODO: get rid of forcefill
#     anim = preset.animations[animname]
#     anim.anim_voxelvolume = T1
#     anim.animationtype = 'Slices'
#     anim.frame_end = range  # FIXME: very dependent on order
#     anim.sliceproperty = 'Thickness'
#     anim.reverse = reverse
#     action = bpy.data.actions['SceneAction']
#     fcu = action.fcurves.find('nb.voxelvolumes["nustd"].slicethickness')
#     FIXME!!?!!
#     kfp = fcu.keyframe_points[0]
#     kfp.interpolation = 'QUART'  # wrong context, needs fcurve context
#     kfp.easing = 'EASE_OUT'
# 
#     return anim

def animate_hide_switch(context, show_range):
    """Hide the 'surfaces' group for a part of the animation."""

    scn = context.scene
    nb = scn.nb

    surfs = bpy.data.groups.get('surfaces')

    # set the animation on one of the objects in the group
    anim_ob = surfs.objects[0]
    interval_head = [scn.frame_start, show_range[0] - 1]
    interval_anim = [show_range[0], show_range[1]]
    interval_tail = [show_range[1] + 1, scn.frame_end]
    ivs = [interval_head, interval_tail, interval_anim]
    vals = [True, True, False]
    for iv, val in zip(ivs, vals):
        for fr in iv:
            scn.frame_set(fr)
            anim_ob.hide = anim_ob.hide_render = val
            anim_ob.keyframe_insert("hide")
            anim_ob.keyframe_insert("hide_render")

    # select the surfaces group and make the animated object active
    for group in bpy.data.groups:
        for ob in group.objects:
            ob.select = False
    for surf in surfs.objects:
        surf.select = True
    bpy.context.scene.objects.active = anim_ob

    # link the animation to all objects in the group
    bpy.ops.object.make_links_data(type='ANIMATION')



def set_render_settings(context, datadir, qr=True):

    scn = context.scene
    nb = scn.nb

    # acts as switch between quick / full render
    qrs = {True: {'rp': 25, 'ff': 'AVI_JPEG', 'qu': 50, 'cd': '8', 'fs': 10},
           False: {'rp': 100, 'ff': 'TIFF', 'qu': 100, 'cd': '16', 'fs': 1}}

    scn.nb.settingprops.engine = 'BLENDER_RENDER'
#     scn.render.engine = 'BLENDER_RENDER'

    scn.render.resolution_x = 1920
    scn.render.resolution_y = 1080
    scn.render.resolution_percentage = qrs[qr]['rp']
    scn.frame_step = qrs[qr]['fs']

    scn.render.image_settings.file_format = qrs[qr]['ff']
    scn.render.image_settings.quality = qrs[qr]['qu']
    scn.render.image_settings.color_depth = qrs[qr]['cd']
    scn.render.image_settings.tiff_codec = 'NONE'
#     scn.render.threads_mode = 'FIXED'
#     scn.render.threads = 4
    scn.render.filepath = os.path.join(datadir, '')
    if not qr:
        tiffpath = os.path.join(datadir, 'tiffs', '')
        nb_ut.mkdir_p(tiffpath)
        scn.render.filepath = tiffpath
    # scn.render.image_settings.file_format = 'FFMPEG'
    # scn.format = 'MPEG2'
    # scn.ffmpeg_preset = 'VERYSLOW'


def import_fs_cortical(context, fssubjdir, sformfile="",
                       hemis=["lh", "rh"], surf="pial"):
    """Load freesurfer surfaces."""

    scn = context.scene
    nb = scn.nb

    for h in hemis:
        surfname = "{}.{}".format(h, surf)
        bpy.ops.nb.import_surfaces(directory=fssubjdir,
                                   files=[{"name": surfname}],
                                   name=surfname)
        if sformfile:
            nb.surfaces[surfname].sformfile = sformfile

        # make it a (bit of a lazy) glass brain
        mat = bpy.data.materials.get(surfname)
        mat.diffuse_color = (0.1, 0.1, 0.1)
        mat.alpha = 0.1


def import_fs_subcortical(context, base, surfdir, sformfile=""):
    """Load freesurfer-derived subcortical structures."""

    scn = context.scene
    nb = scn.nb

    aseg = get_lut(context)
    for seg in aseg:
        surfname = seg["name"]
        surfcolour = seg["colour"]
        surffilename = "{:s}.{:s}.stl".format(base, surfname)
        bpy.ops.nb.import_surfaces(directory=surfdir,
                                   files=[{"name": surffilename}],
                                   name=surfname,
                                   colourtype='pick',
                                   colourpicker=surfcolour[:3])
        surf = nb.surfaces[surfname]
        surf.sformfile = sformfile
        surfob = bpy.data.objects[surfname]
        surfob.modifiers["smooth"].iterations = 40


# define lut
def get_lut(context):
    """Return a lookup table for label values, names and colours.

    This derives from the FreeSurfer subcortical segmentation LUT.
    """

    scn = context.scene
    nb = scn.nb

    aseg = [
        {'value': 4,
         'name': 'DSSC_Left-Lateral-Ventricle',
         'colour': [0, 0, 1, 1]},
        {'value': 5,
         'name': 'Left-Inf-Lat-Vent',
         'colour': [0, 0, 1, 1]},
        {'value': 7,
         'name': 'DSSC_Left-Cerebellum-White-Matter',
         'colour': [1, 1, 1, 1]},
        {'value': 8,
         'name': 'DSSC_Left-Cerebellum-Cortex',
         'colour': [0.2, 0.2, 0.2, 1]},
        {'value':  10,
         'name': 'DSSC_Left-Thalamus-Proper',
         'colour': [1, 0, 0, 1]},
        {'value':  11,
         'name': 'DSSC_Left-Caudate',
         'colour': [1, 1, 0, 1]},  # [122, 186, 220, 0]
        {'value':  12,
         'name': 'Left-Putamen',
         'colour': [1, 1, 0, 1]},
        {'value':  13,
         'name': 'Left-Pallidum',
         'colour': [1, 1, 0, 1]},
        {'value':  14,
         'name': '3rd-Ventricle',
         'colour': [0, 0, 1, 1]},
        {'value':  15,
         'name': 'DSSC_4th-Ventricle',
         'colour': [0, 0, 0, 1]},  # [42, 204, 164, 0]
        {'value':  16,
         'name': 'Brain-Stem',
         'colour': [1, 1, 1, 1]},
        {'value':  17,
         'name': 'DSSC_Left-Hippocampus',
         'colour': [0, 1, 1, 1]},  # [220, 216, 20, 0]
        {'value':  18,
         'name': 'DSSC_Left-Amygdala',
         'colour': [0, 1, 1, 1]},  # [103, 255, 255, 0]
        {'value':  24,
         'name': 'CSF',
         'colour': [0, 0, 1, 1]},
        {'value':  26,
         'name': 'DSSC_Left-Accumbens-area',
         'colour': [0, 1, 1, 1]},  # [255, 165, 0, 0]
        {'value':  28,
         'name': 'DSSC_Left-VentralDC',
         'colour': [0, 1, 1, 1]},  # [165, 42, 42, 0]
        {'value':  30,
         'name': 'Left-vessel',
         'colour': [0, 0, 1, 1]},
        {'value':  31,
         'name': 'Left-choroid-plexus',
         'colour': [0, 0, 0, 1]},
        {'value':  43,
         'name': 'Right-Lateral-Ventricle',
         'colour': [0, 0, 1, 1]},
        {'value':  44,
         'name': 'Right-Inf-Lat-Vent',
         'colour': [0, 0, 1, 1]},
        {'value':  46,
         'name': 'Right-Cerebellum-White-Matter',
         'colour': [1, 1, 1, 1]},
        {'value':  47,
         'name': 'Right-Cerebellum-Cortex',
         'colour': [0.2, 0.2, 0.2, 1]},
        {'value':  49,
         'name': 'Right-Thalamus-Proper',
         'colour': [1, 0, 0, 1]},
        {'value':  50,
         'name': 'Right-Caudate',
         'colour': [1, 1, 0, 1]},
        {'value':  51,
         'name': 'Right-Putamen',
         'colour': [1, 1, 0, 1]},
        {'value':  52,
         'name': 'Right-Pallidum',
         'colour': [1, 1, 0, 1]},
        {'value':  53,
         'name': 'Right-Hippocampus',
         'colour': [0, 1, 1, 1]},
        {'value':  54,
         'name': 'Right-Amygdala',
         'colour': [0, 1, 1, 1]},
        {'value':  58,
         'name': 'Right-Accumbens-area',
         'colour': [0, 1, 1, 1]},
        {'value':  60,
         'name': 'Right-VentralDC',
         'colour': [0, 1, 1, 1]},
        {'value':  62,
         'name': 'Right-vessel',
         'colour': [0, 0, 1, 1]},
        {'value':  63,
         'name': 'Right-choroid-plexus',
         'colour': [0, 0, 0, 1]},
        {'value': 251,
         'name': 'CC_Posterior',
         'colour': [1, 1, 1, 1]},
        {'value': 252,
         'name': 'CC_Mid_Posterior',
         'colour': [1, 1, 1, 1]},
        {'value': 253,
         'name': 'CC_Central',
         'colour': [1, 1, 1, 1]},
        {'value': 254,
         'name': 'CC_Mid_Anterior',
         'colour': [1, 1, 1, 1]},
        {'value': 255,
         'name': 'CC_Anterior',
         'colour': [1, 1, 1, 1]}]

    return aseg


def create_scene(context, datadir, blendname, T1="T1"):
    """Create the blend file for the first part of the animation."""

    scn = context.scene
    nb = scn.nb

    blendpath = os.path.join(datadir, "{}.blend".format(blendname))
    bpy.ops.wm.save_as_mainfile(filepath=blendpath)

    vvol = import_volume(context, datadir, T1)
    fs_subjdir = os.path.join(datadir, "fs", "surf")
    import_fs_cortical(context, fs_subjdir,
                       "//fs/surf/transmat_fssurf.txt")
    surfdir = os.path.join(datadir, "fs/mri/dmcsurf_" + "aseg")
    import_fs_subcortical(context, "aseg", surfdir,
                          "//fs/mri/dmcsurf_aseg/transmat_aseg.txt")

    preset = create_preset(context)

    animate_camera_rotation(context, preset)
    kfps = {1: (0.1, 'QUAD', 'EASE_OUT'),
            125: (0.8, 'QUART', 'EASE_OUT'),
            250: (0.4, 'BEZIER', 'EASE_IN')}
    animate_volume_slicer(context, vvol, kfps, index=2)
    animate_hide_switch(context, [125, 250])

    bpy.ops.wm.save_mainfile()


def run_example():
    """Generate and render this example."""

    context = bpy.context
    scn = context.scene
    nb = scn.nb

    datadir = "/Users/michielk/oxdox/brainart/YTproj_DB"

    scn.frame_end = 250

    set_render_settings(context, datadir)

    create_scene(context,
                 datadir, blendname="YTproj_DB_scn_test",
                 T1="nustd")


if __name__ == "__main__":
    run_example()
