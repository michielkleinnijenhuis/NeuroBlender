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


import sys
import os
from subprocess import call
import pickle
from argparse import ArgumentParser

import bpy
from mathutils import Vector

from NeuroBlender import utils as nb_ut
from NeuroBlender import colourmaps as nb_cm
# FIXME
# from NeuroBlender.examples.example1 import (read_labelimage_nii,
#                                              labels2meshes_vtk)
# from . import read_labelimage_nii, labels2meshes_vtk


def import_volume(context, datadir, vol, cmdict, ext=".nii.gz"):
    """Load the volume.

    import volume <datadir>/<vol>.nii.gz with name <vol>
    i.e. write png's to '//voltex_<vol>',
    where '//' is short for the path where the .blend file has been saved
    """

    scn = context.scene
    nb = scn.nb

    # import volume
    bpy.ops.nb.import_voxelvolumes(
        directory=datadir,
        files=[{"name": vol + ext}],
        name=vol,
        texdir="//voltex_{}".format(vol)
        )
    vvol = nb.voxelvolumes[nb.index_voxelvolumes]

    # give the volume a smooth and clean appearance
    tex = bpy.data.textures[vvol.texname]
    tex.voxel_data.interpolation = 'TRICUBIC_BSPLINE'  # custom interpolation
    nb.cr_path = 'bpy.data.textures["{}"].color_ramp'.format(tex.name)
    bpy.ops.nb.colourmap_presets(name=cmdict['name'])  # custom colourmap
    vvol.colourmap_enum = cmdict['name'].lower()
    nb_cm.replace_colourmap(tex.color_ramp, cmdict)

    return vvol


def create_preset(context, presetname="Preset",
                  cam_distance=3.5, centre_shift=[0, 0, 0]): # z-12
    """Create the scene."""

    scn = context.scene
    nb = scn.nb

    # add a standard scene setup
    bpy.ops.nb.add_preset(name=presetname)
    preset = nb.presets[presetname]

    # move the camera position and tracking object to get max view
    cam = preset.cameras[preset.index_cameras]
    cam.cam_distance = cam_distance
    centre = bpy.data.objects.get(preset.centre)
    centre.location = centre.location + Vector(centre_shift)

    # FIXME: make this default?
    for light in preset.lights:
        light.type = 'HEMI'
#     # hiding rendering of lights in this volume rendering example
#     for l in ["Key", "Fill", "Back"]:
#         bpy.data.objects[l].hide_render = True

    return preset


def animate_camera_rotation(context, preset, animname="camZ"):
    """Create a camera rotation around Z."""

    scn = context.scene
    nb = scn.nb

    bpy.ops.nb.animate_camerapath(name=animname)
    anim = nb.animations[nb.index_animations]

    return anim


def animate_volume_carver(context, vvol, keyframes, index=2):
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


def animate_hide_switch(context, show_range):
    """Hide the 'surfaces' group for a part of the animation."""

    scn = context.scene
    nb = scn.nb

    surfs = bpy.data.groups.get('surfaces')

    # set the animation on one of the objects in the 'surfaces' group
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

    # select the 'surfaces' group and make the animated object active
    for group in bpy.data.groups:
        for ob in group.objects:
            ob.select = False
    for surf in surfs.objects:
        surf.select = True
    bpy.context.scene.objects.active = anim_ob

    # link the animation to all objects in the group
    bpy.ops.object.make_links_data(type='ANIMATION')


def set_render_settings(context, datadir, qr=True):
    """Pick a set of render settings."""

    scn = context.scene
    nb = scn.nb

    # acts as switch between quick / full render
    qrs = {True: {'rp': 25, 'ff': 'AVI_JPEG', 'qu': 50, 'cd': '8', 'fs': 10},
           False: {'rp': 100, 'ff': 'TIFF', 'qu': 100, 'cd': '16', 'fs': 1}}

    scn.nb.settingprops.engine = 'BLENDER_RENDER'

    scn.render.resolution_x = 1920
    scn.render.resolution_y = 1080
    scn.render.resolution_percentage = qrs[qr]['rp']
    scn.frame_step = qrs[qr]['fs']

    scn.render.image_settings.file_format = qrs[qr]['ff']
    scn.render.image_settings.quality = qrs[qr]['qu']
    scn.render.image_settings.color_depth = qrs[qr]['cd']
    scn.render.image_settings.tiff_codec = 'NONE'
    scn.render.filepath = os.path.join(datadir, '')
    if not qr:
        tiffpath = os.path.join(datadir, 'tiffs', '')
        nb_ut.mkdir_p(tiffpath)
        scn.render.filepath = tiffpath


def import_fs_cortical(context, fs_surf_dir, sformfile="",
                       hemis=["lh", "rh"], surftype="pial"):
    """Load freesurfer surfaces."""

    scn = context.scene
    nb = scn.nb

    for h in hemis:
        surfname = "{}.{}".format(h, surftype)
        bpy.ops.nb.import_surfaces(directory=fs_surf_dir,
                                   files=[{"name": surfname}],
                                   name=surfname,
                                   sformfile=sformfile)
        surf = nb.surfaces[nb.index_surfaces]
# os.path.join(fs_surf_dir, "affine.npy")
#         if sformfile:  # FIXME: why necessary?
#             surf.sformfile = sformfile

        # make it a (bit of a lazy) glass brain
        mat = bpy.data.materials.get(surf.name)
        mat.diffuse_color = (0.1, 0.1, 0.1)
        mat.alpha = 0.1


def import_fs_subcortical(context, fs_subc_dir, fs_subc_lut, sformfile=""):
    """Load freesurfer-derived subcortical structures."""

    scn = context.scene
    nb = scn.nb

    for _, seg in fs_subc_lut.items():
        surffilename = "{:s}.stl".format(seg["name"])
        bpy.ops.nb.import_surfaces(directory=fs_subc_dir,
                                   files=[{"name": surffilename}],
                                   name=seg["name"],
                                   sformfile=sformfile,
                                   colourtype='pick',
                                   colourpicker=seg["colour"][:3],
                                   beautify=True)
        surf = nb.surfaces[nb.index_surfaces]
#         if sformfile:
#             surf.sformfile = sformfile

        # more aggressive smoothing on subcortical structures
        surfob = bpy.data.objects[surf.name]
        surfob.modifiers["smooth"].iterations = 40


def generate_fs_subcortical_meshes(context, fs_mri_dir, fs_subc_dir,
                                   fs_subc_lut, fs_subc_seg):
    """Generate meshes from a freesurfer segmentation image (e.g. aseg.mgz)."""

    basepath = os.path.join(fs_mri_dir, fs_subc_seg)
    cmd = 'mri_convert {0}.mgz {0}.nii.gz'.format(basepath)
    exit_code = call(cmd, shell=True)
    if exit_code:
        return exit_code

    nii_image = '{}.nii.gz'.format(basepath)
    labels2meshes_via_p2(fs_mri_dir, fs_subc_seg, fs_subc_lut, nii_image)
    if exit_code:
        return exit_code
#     try:
#         import vtk
#     except ImportError:  # likely that vtk is not importable from blender
#         labels2meshes_via_p2(fs_mri_dir, fs_subc_seg, fs_subc_lut, nii_image)
#         if exit_code:
#             return exit_code
#     else:
#         labeldata, spacing, offset = read_labelimage_nii(nii_image)
#         labels2meshes_vtk(fs_subc_dir, fs_subc_lut,
#                           labeldata, spacing=spacing, offset=offset)
#         # TODO: offset from header

    return 0


def labels2meshes_via_p2(fs_mri_dir, fs_subc_seg, fs_subc_lut, nii_image):
    """Generate meshes in python2."""

    # dump the lookuptable in a python2 pickle
    lutpickle = os.path.join(fs_mri_dir, '{}.pickle'.format(fs_subc_seg))
    with open(lutpickle, "wb") as f:
        pickle.dump(fs_subc_lut, f, protocol=2)

    # call labels2meshes_vtk.py from python2 with <nii_image> and <lut>
    l2mfun = os.path.join(os.path.dirname(__file__), "labels2meshes_vtk.py")
    cmd = "python2 {} {} -l {}".format(l2mfun, nii_image, lutpickle)
    exit_code = call(cmd, shell=True)

    return exit_code


def get_lut(context, fs_subc_seg):
    """Return a lookup table for label values, names and colours.

    This derives from the FreeSurfer subcortical segmentation LUT.
    # FIXME: switch aseg/aparc
    """

    scn = context.scene
    nb = scn.nb

    aseg = {4: {'name': 'DSSC_Left-Lateral-Ventricle',
                'colour': [0, 0, 1, 1]},
            5: {'name': 'Left-Inf-Lat-Vent',
                'colour': [0, 0, 1, 1]},
            7: {'name': 'DSSC_Left-Cerebellum-White-Matter',
                'colour': [1, 1, 1, 1]},
            8: {'name': 'DSSC_Left-Cerebellum-Cortex',
                'colour': [0.2, 0.2, 0.2, 1]},
            10: {'name': 'DSSC_Left-Thalamus-Proper',
                 'colour': [1, 0, 0, 1]},
            11: {'name': 'DSSC_Left-Caudate',
                 'colour': [1, 1, 0, 1]},  # [122, 186, 220, 0]
            12: {'name': 'Left-Putamen',
                 'colour': [1, 1, 0, 1]},
            13: {'name': 'Left-Pallidum',
                 'colour': [1, 1, 0, 1]},
            14: {'name': '3rd-Ventricle',
                 'colour': [0, 0, 1, 1]},
            15: {'name': 'DSSC_4th-Ventricle',
                 'colour': [0, 0, 0, 1]},  # [42, 204, 164, 0]
            16: {'name': 'Brain-Stem',
                 'colour': [1, 1, 1, 1]},
            17: {'name': 'DSSC_Left-Hippocampus',
                 'colour': [0, 1, 1, 1]},  # [220, 216, 20, 0]
            18: {'name': 'DSSC_Left-Amygdala',
                 'colour': [0, 1, 1, 1]},  # [103, 255, 255, 0]
            24: {'name': 'CSF',
                 'colour': [0, 0, 1, 1]},
            26: {'name': 'DSSC_Left-Accumbens-area',
                 'colour': [0, 1, 1, 1]},  # [255, 165, 0, 0]
            28: {'name': 'DSSC_Left-VentralDC',
                 'colour': [0, 1, 1, 1]},  # [165, 42, 42, 0]
            30: {'name': 'Left-vessel',
                 'colour': [0, 0, 1, 1]},
            31: {'name': 'Left-choroid-plexus',
                 'colour': [0, 0, 0, 1]},
            43: {'name': 'Right-Lateral-Ventricle',
                 'colour': [0, 0, 1, 1]},
            44: {'name': 'Right-Inf-Lat-Vent',
                 'colour': [0, 0, 1, 1]},
            46: {'name': 'Right-Cerebellum-White-Matter',
                 'colour': [1, 1, 1, 1]},
            47: {'name': 'Right-Cerebellum-Cortex',
                 'colour': [0.2, 0.2, 0.2, 1]},
            49: {'name': 'Right-Thalamus-Proper',
                 'colour': [1, 0, 0, 1]},
            50: {'name': 'Right-Caudate',
                 'colour': [1, 1, 0, 1]},
            51: {'name': 'Right-Putamen',
                 'colour': [1, 1, 0, 1]},
            52: {'name': 'Right-Pallidum',
                 'colour': [1, 1, 0, 1]},
            53: {'name': 'Right-Hippocampus',
                 'colour': [0, 1, 1, 1]},
            54: {'name': 'Right-Amygdala',
                 'colour': [0, 1, 1, 1]},
            58: {'name': 'Right-Accumbens-area',
                 'colour': [0, 1, 1, 1]},
            60: {'name': 'Right-VentralDC',
                 'colour': [0, 1, 1, 1]},
            62: {'name': 'Right-vessel',
                 'colour': [0, 0, 1, 1]},
            63: {'name': 'Right-choroid-plexus',
                 'colour': [0, 0, 0, 1]},
            251: {'name': 'CC_Posterior',
                  'colour': [1, 1, 1, 1]},
            252: {'name': 'CC_Mid_Posterior',
                  'colour': [1, 1, 1, 1]},
            253: {'name': 'CC_Central',
                  'colour': [1, 1, 1, 1]},
            254: {'name': 'CC_Mid_Anterior',
                  'colour': [1, 1, 1, 1]},
            255: {'name': 'CC_Anterior',
                  'colour': [1, 1, 1, 1]}
            }

    return aseg


def create_scene(context, blendpath, datadir,
                 T1="T1", T1cmap=None,
                 fs_cort=True, fs_subc=True,
                 fs_subjdir="", fs_subc_seg="aseg"):
    """Create the blend file for the animation."""

    scn = context.scene
    nb = scn.nb

    # save the (yet empty) blendfile
    bpy.ops.wm.save_as_mainfile(filepath=blendpath)

    # load the voxelvolume
    basepath = os.path.join(os.path.join(fs_subjdir, "mri"), T1)
    cmd = 'mri_convert {0}.mgz {0}.nii.gz'.format(basepath)
    exit_code = call(cmd, shell=True)
    if exit_code:
        return exit_code
    vvol = import_volume(context, os.path.join(fs_subjdir, "mri"), T1, T1cmap)

    # load the (pial) surfaces (of both hemispheres)
    if fs_cort:
        fs_surf_dir = os.path.join(fs_subjdir, "surf")
        # FIXME: get affine matrix from fs/nibabel
        tmat = os.path.join(fs_surf_dir, "transmat.txt")
        import_fs_cortical(context, fs_surf_dir,
                           sformfile=tmat,
                           hemis=["lh", "rh"],
                           surftype="pial")

    # load (and generate) the subcortical structure meshes
    if fs_subc:
        fs_mri_dir = os.path.join(fs_subjdir, "mri")
        fs_subc_dir = os.path.join(fs_mri_dir, fs_subc_seg)

        lut = get_lut(context, fs_subc_seg)

        # create the subcortical structure meshes from volume segmentation
        nb_ut.mkdir_p(fs_subc_dir)
        generate_fs_subcortical_meshes(context, fs_mri_dir, fs_subc_dir,
                                       lut, fs_subc_seg)

        tmat = os.path.join(fs_subc_dir, "affine.npy")
        import_fs_subcortical(context, fs_subc_dir, lut, tmat)

    # create the camera, lights, etc
    preset = create_preset(context)

    # set a carver on the voxelvolume
    bpy.ops.nb.import_carvers(parentpath=vvol.path_from_id())
    carver = vvol.carvers[vvol.index_carvers]
    bpy.ops.nb.import_carveobjects(
        parentpath=carver.path_from_id(),
        name="slice",
        carveobject_type_enum='slice'
        )
    carveobject = carver.carveobjects[carver.index_carveobjects]
    carveobject.slicethickness = [0.99, 0.99, 0.05]
    carveobject.sliceposition = [0, 0, 0]
    carveobject.sliceangle = [0, 0, 0]

    # generate the animation elements
    keyframes = [scn.frame_start,
                 int((scn.frame_end - scn.frame_start) / 2),
                 scn.frame_end]

    animate_camera_rotation(context, preset)

    # FIXME: 
    kfps = {keyframes[0]: (0.1, 'QUAD', 'EASE_OUT'),
            keyframes[1]: (0.8, 'QUART', 'EASE_OUT'),
            keyframes[2]: (0.4, 'BEZIER', 'EASE_IN')}
    animate_volume_carver(context, carveobject, kfps, index=2)

    if fs_cort | fs_subc:
        animate_hide_switch(context, [keyframes[1], keyframes[2]])

    # save the final blendfile
    bpy.ops.wm.save_mainfile()


def run_example(argv):
    """Generate and render this example."""

    # FIXME: too much to pack into NeuroBlender.zip: provide download option

    if "--" not in argv:
        argv = []  # as if no args are passed
    else:
        argv = argv[argv.index("--") + 1:]  # get all args after "--"

    parser = ArgumentParser(description='NeuroBlender example script.')
    parser.add_argument('datadir', help='the input data directory')
    args = parser.parse_args(argv)
    datadir = args.datadir

    context = bpy.context
    scn = context.scene
    nb = scn.nb

    # the path to this example's directory and it's name
    example_name = os.path.splitext(os.path.basename(__file__))[0]

    # <datadir> contains the T1 volume <T1name>.nii.gz;
    # <cmap> is a custom colourmap for the voxelvolume in this example
    T1name = "nu"
    cmap = {"name": example_name,
            "color_mode": "RGB",
            "interpolation": "LINEAR",
            "hue_interpolation": "FAR",
            "elements": [{"position": 0.04,
                          "color": (0.161539, 0.030769, 0.007692, 0)},
                         {"position": 0.50,
                          "color": (0.757397, 0.650142, 0.610706, 1)}]}

    # <datadir>/<fs_subjdir> is the directory with freesurfer output
    # it should contain the subdirectories 'surf' and 'mri'
    fs_cort = True
    fs_subc = True
    fs_subjdir = os.path.join(datadir, "fs")
    fs_subc_seg = "aseg"

    # the 10-s animation is going to range from frame 1 to 250
    scn.frame_start = 1
    scn.frame_end = 250

    # this function loads settings for rendering the scene
    # qr is a switch between quick-render (.avi) and full-render (tif-stack)
    set_render_settings(context, datadir, qr=True)

    # build the blend file
    blendpath = os.path.join(datadir, "{}.blend".format(example_name))
    create_scene(context, blendpath, datadir,
                 T1=T1name, T1cmap=cmap,
                 fs_cort=fs_cort, fs_subc=fs_subc,
                 fs_subjdir=fs_subjdir, fs_subc_seg=fs_subc_seg)

    # render the scene
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    run_example(sys.argv)
