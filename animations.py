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


"""The NeuroBlender animations module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements simple animations.
"""


import numpy as np
import mathutils

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


class SetAnimations(Operator):
    bl_idname = "nb.set_animations"
    bl_label = "Set animations"
    bl_description = "(Re)set all animations in the preset"""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[nb.index_presets]
        nb_anims = nb.animations

        # camera path animations
        cam = bpy.data.objects[nb_preset.cameras[nb_preset.index_cameras].name]
        del_indices, cam_anims = [], []
        for i, anim in enumerate(nb_anims):
            if ((anim.animationtype == "CameraPath") & (anim.is_rendered)):
                del_indices.append(i)
                cam_anims.append(anim)
        self.clear_camera_path_animations(cam, nb_anims, del_indices)
        self.create_camera_path_animations(cam, cam_anims)

        # slice fly-throughs
        slice_anims = [anim for anim in nb_anims
                       if ((anim.animationtype == "Carver") &
                           (anim.is_rendered))]
        # delete previous animation on slicebox
        for anim in slice_anims:
    #         vvol = nb.voxelvolumes[anim.anim_voxelvolume]
            vvol = bpy.data.objects[anim.anim_voxelvolume]
            vvol.animation_data_clear()

        for anim in slice_anims:
            vvol = nb.voxelvolumes[anim.anim_voxelvolume]
            self.animate_slicebox(vvol, anim, anim.axis,
                                  anim.frame_start, anim.frame_end,
                                  anim.repetitions, anim.offset)

        # time series
        time_anims = [anim for anim in nb_anims
                      if ((anim.animationtype == "TimeSeries") &
                          (anim.is_rendered))]
        for anim in time_anims:
            self.animate_timeseries(anim)

        return {"FINISHED"}


class AnimateCameraPath(Operator):
    bl_idname = "nb.animate_camerapath"
    bl_label = "Set animations"
    bl_description = "(Re)set all animations in the preset"""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[nb.index_presets]
        nb_anims = nb.animations

        # camera path animations
        preset = nb_preset.cameras[nb_preset.index_cameras]
        cam = bpy.data.objects[preset.name]

        del_indices, cam_anims = [], []
        for i, anim in enumerate(nb_anims):
            if ((anim.animationtype == "CameraPath") & (anim.is_rendered)):
                del_indices.append(i)
                cam_anims.append(anim)

        self.clear_camera_path_animations(cam, nb_anims, del_indices)

        self.create_camera_path_animations(cam, cam_anims)

        return {"FINISHED"}

    def clear_camera_path_animations(self, cam, anims, delete_indices):
        """Remove all camera trajectory animations."""

        del_anims = [anim for i, anim in enumerate(anims)
                     if i in delete_indices]
        cam_anims = [anim for i, anim in enumerate(anims)
                     if ((anim.animationtype == "CameraPath") &
                         (anim.is_rendered) &
                         (i not in delete_indices))]

        for anim in del_anims:
            self.clear_camera_path_animation(cam, anim)

        self.update_cam_constraints(cam, cam_anims)

    def clear_camera_path_animation(self, cam, anim):
        """Remove a camera trajectory animation."""

        self.clear_CP_evaltime(anim)
        self.clear_CP_followpath(anim)
        self.remove_CP_followpath(cam, anim)

    def clear_CP_evaltime(self, anim):
        """Remove modifiers on campath evaluation time."""

        actname = '{}Action'.format(anim.campaths_enum)
        try:
            action = bpy.data.actions[actname]
            fcu = action.fcurves.find("eval_time")
        except:
            pass
        else:
            """ FIXME: get rid of hacky mod removal:
                it fails when anim.frame_start/end is changed
            """
            for mod in fcu.modifiers:
                if ((mod.frame_start == anim.frame_start) &
                    (mod.frame_end == anim.frame_end)):
                    fcu.modifiers.remove(mod)

    def clear_CP_followpath(self, anim):
        """Remove the keyframes on the FollowPath constraint."""

    #     action = bpy.data.actions['CamAction']
        props = ['use_fixed_location', 'offset_factor',
                 'forward_axis', 'influence']
        for prop in props:
            dpath = 'constraints["{}"].{}'.format(anim.cnsname, prop)
            try:
                fcu = bpy.data.actions['CamAction'].fcurves.find(dpath)
            except:
                pass
            else:
                bpy.data.actions['CamAction'].fcurves.remove(fcu)

    def remove_CP_followpath(self, cam, anim):
        """Delete a FollowPath constraint from the camera."""

        try:
            cns = cam.constraints[anim.cnsname]
        except:
            pass
        else:
            cam.constraints.remove(cns)

    def add_cam_constraints(self, cam):
        """Add defaults constraints to the camera."""

        scn = bpy.context.scene
        nb = scn.nb
        nb_preset = nb.presets[nb.index_presets]
        centre = bpy.data.objects[nb_preset.name+'Centre']

        cnsTT = nb_rp.add_constraint(
            cam, "TRACK_TO", "TrackToObject", centre)
        cnsLDi = nb_rp.add_constraint(
            cam, "LIMIT_DISTANCE", "LimitDistInClipSphere", centre, cam.data.clip_end)
        cnsLDo = nb_rp.add_constraint(
            cam, "LIMIT_DISTANCE", "LimitDistOutBrainSphere", centre, max(centre.scale) * 2)

        return cnsTT, cnsLDi, cnsLDo

    def update_cam_constraints(self, cam, cam_anims):
        """Update the basic constraints of the camera."""

        scn = bpy.context.scene

        try:
            action = bpy.data.actions['CamAction']
        except:
            pass
        else:
            props = ["use_location_x", "use_location_y", "use_location_z",
                     "use_rotation_x", "use_rotation_y", "use_rotation_z"]
            for prop in props:
                dpath = 'constraints["Child Of"].{}'.format(prop)
                fcu = action.fcurves.find(dpath)
                action.fcurves.remove(fcu)
            # add the constraint keyframes back again
            cns = cam.constraints["Child Of"]
            timeline = self.generate_timeline(scn, cam_anims)
            self.restrict_trans_timeline(scn, cns, timeline, group="ChildOf")

            dpath = 'constraints["TrackToObject"].influence'
            fcu = action.fcurves.find(dpath)
            action.fcurves.remove(fcu)
            # add the constraint keyframes back again
            cns = cam.constraints["TrackToObject"]
            timeline = self.generate_timeline(scn, cam_anims, trackcentre=True)
            self.restrict_incluence_timeline(scn, cns, timeline, group="TrackTo")

    def create_camera_path_animations(self, cam, anims):
        """Keyframe a set of camera animations."""

        if not anims:
            return

        scn = bpy.context.scene
        nb = scn.nb

        nb_preset = nb.presets[nb.index_presets]
        centre = bpy.data.objects[nb_preset.centre]
        box = bpy.data.objects[nb_preset.box]

        # NOTE: there is no way to reorder constraints without ops
        # workaround: remove all constraints and add them again later
        # alternative: add this in somewhere
#         override = bpy.context.copy()
#         override['constraint'] = cns
#         for _ in range(0, n_cns):
#             bpy.ops.constraint.move_up(override, constraint=cns.name)
        override = bpy.context.copy()
        for cns in cam.constraints:
            override['constraint'] = cns
            bpy.ops.constraint.delete(override)

        for anim in anims:
            try:
                campath = bpy.data.objects[anim.campaths_enum]
            except:
                pass
            else:
                self.animate_campath(campath, anim)
                self.animate_camera(cam, anim, campath)

        timeline = self.generate_timeline(scn, anims)
        self.restrict_trans_timeline(scn, cnsCO, timeline, group="ChildOf")

        cnsTT = nb_ut.add_constraint(cam, "TRACK_TO", "TrackToObject", centre)
        timeline = self.generate_timeline(scn, anims, trackcentre=True)
        self.restrict_incluence_timeline(scn, cnsTT, timeline, group="TrackTo")

    def animate_campath(self, campath=None, anim=None):
        """Set up camera path animation."""

        scn = bpy.context.scene

        campath.data.use_path = True
        actname = "{}Action".format(campath.data.name)
        try:
            fcu = bpy.data.actions[actname].fcurves.find("eval_time")
        except:
            animdata = campath.data.animation_data_create()
            animdata.action = bpy.data.actions.new(actname)
            fcu = animdata.action.fcurves.new("eval_time")

        mod = fcu.modifiers.new('GENERATOR')
        intercept, slope, _ = self.calculate_coefficients(campath, anim)
        mod.coefficients = (intercept, slope)
        mod.use_additive = True
        mod.use_restricted_range = True
        mod.frame_start = anim.frame_start
        mod.frame_end = anim.frame_end

    def calculate_coefficients(self, campath, anim):
        """Calculate the coefficients for a campath modifier."""

        max_val = anim.repetitions * campath.data.path_duration
        slope = max_val / (anim.frame_end - anim.frame_start)
        intercept = -(anim.frame_start) * slope

        if anim.reverse:
            intercept = -intercept + 100  # TODO: check correctness of value 100
            slope = -slope
            max_val = -max_val

        return intercept, slope, max_val

    def animate_camera(self, cam, anim, campath):
        """Set up camera animation."""

        scn = bpy.context.scene

        frame_current = scn.frame_current

        cnsname = "FollowPath{}".format(anim.campaths_enum)
        cns = nb_rp.add_constraint(cam, "FOLLOW_PATH", cnsname, campath, anim.tracktype)
        anim.cnsname = cns.name
        self.restrict_incluence(cns, anim)

        cns.offset = anim.offset * -100

        interval_head = [scn.frame_start, anim.frame_start - 1]
        interval_anim = [anim.frame_start, anim.frame_end]
        interval_tail = [anim.frame_end + 1, scn.frame_end]
        ivs = [interval_head, interval_tail, interval_anim]
        vals = [(1, 0, 'TRACK_NEGATIVE_Z'),
                (1, 0, 'TRACK_NEGATIVE_Z'),
                (0, anim.offset,
                 'FORWARD_Z' if anim.reverse else 'TRACK_NEGATIVE_Z')]
        for iv, val in zip(ivs, vals):
            for fr in iv:
                scn.frame_set(fr)
                cns.use_fixed_location = val[0]
                cns.offset_factor = val[1]
                cns.forward_axis = val[2]
                cns.keyframe_insert("use_fixed_location")
                cns.keyframe_insert("offset_factor")
                cns.keyframe_insert("forward_axis")

        scn.frame_set(frame_current)

    def generate_timeline(self, scn, anims, trackcentre=False):
        """Generate a timeline for a set of animations."""

        timeline = np.zeros(scn.frame_end + 1)
        if trackcentre:
            timeline += 1

        for anim in anims:
            for i in range(anim.frame_start, anim.frame_end + 1):
                if trackcentre:
                    timeline[i] = anim.tracktype == 'TrackObject'
                else:
                    timeline[i] = 1

        return timeline

    def restrict_trans_timeline(self, scn, cns, timeline, group=""):
        """Restrict the loc/rot in a constraint according to timeline."""

        frame_current = scn.frame_current

        for prop in ["use_location_x", "use_location_y", "use_location_z",
                     "use_rotation_x", "use_rotation_y", "use_rotation_z"]:
            scn.frame_set(0)
            exec("cns.%s = True" % prop)
            cns.keyframe_insert(prop, group=group)
            scn.frame_set(scn.frame_end + 1)
            exec("cns.%s = True" % prop)
            cns.keyframe_insert(prop, group=group)

            scn.frame_set(scn.frame_start)
            exec("cns.%s = not timeline[scn.frame_start]" % prop)
            cns.keyframe_insert(prop, group=group)

            for fr in range(scn.frame_start+1, scn.frame_end):
                scn.frame_set(fr)
                exec("cns.%s = not timeline[fr]" % prop)
                if ((timeline[fr] != timeline[fr-1]) or
                    timeline[fr] != timeline[fr+1]):
                    cns.keyframe_insert(prop, group=group)

            scn.frame_set(scn.frame_end)
            exec("cns.%s = not timeline[scn.frame_end]" % prop)
            cns.keyframe_insert(prop, group=group)

        scn.frame_set(frame_current)

    def restrict_incluence_timeline(self, scn, cns, timeline, group=""):
        """Restrict the influence of a constraint according to timeline."""

        frame_current = scn.frame_current

        scn.frame_set(scn.frame_start)
        cns.influence = timeline[scn.frame_start]
        cns.keyframe_insert("influence", group=group)

        for fr in range(scn.frame_start+1, scn.frame_end):
            scn.frame_set(fr)
            cns.influence = timeline[fr]
            if ((timeline[fr] != timeline[fr-1]) or
                timeline[fr] != timeline[fr+1]):
                cns.keyframe_insert("influence", group=group)

        scn.frame_set(scn.frame_end)
        cns.influence = timeline[scn.frame_end]
        cns.keyframe_insert("influence", group=group)

        scn.frame_set(frame_current)

    def restrict_incluence(self, cns, anim):
        """Restrict the influence of a constraint to the animation interval."""

        scn = bpy.context.scene

        frame_current = scn.frame_current

        interval_head = [scn.frame_start, anim.frame_start - 1]
        interval_anim = [anim.frame_start, anim.frame_end]
        interval_tail = [anim.frame_end + 1, scn.frame_end]
        ivs = [interval_head, interval_tail, interval_anim]
        vals = [0, 0, 1]
        for iv, val in zip(ivs, vals):
            for fr in iv:
                scn.frame_set(fr)
                cns.influence = val
                cns.keyframe_insert(data_path="influence", index=-1)

        scn.frame_set(frame_current)

    def setup_animation_rendering(self, filepath="render/anim",
                                  file_format="AVI_JPEG",
                                  blendpath=""):
        """Set rendering properties for animations."""

        scn = bpy.context.scene

        scn.render.filepath = filepath
        scn.render.image_settings.file_format = file_format
        bpy.ops.render.render(animation=True)

        bpy.ops.wm.save_as_mainfile(filepath=blendpath)


class AnimateCarver(Operator):
    bl_idname = "nb.animate_carver"
    bl_label = "Set carver animations"
    bl_description = """..."""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        # slice fly-throughs
        slice_anims = [
            anim for anim in nb.animations
            if ((anim.animationtype == "Carver") & (anim.is_rendered))
            ]

        # delete previous animation on carveobject
        for anim in slice_anims:
            carveobject = bpy.data.objects[anim.anim_voxelvolume]
            carveobject.animation_data_clear()

        for anim in slice_anims:
            vvol = nb.voxelvolumes[anim.anim_voxelvolume]
            self.animate_carver(vvol, anim, anim.axis,
                                anim.frame_start, anim.frame_end,
                                anim.repetitions, anim.offset)

        return {"FINISHED"}

    def animate_carver(self, vvol, anim=None, axis="Z",
                       frame_start=1, frame_end=100,
                       repetitions=1.0, offset=0.0, frame_step=10):
        """Set up a carver animation."""

        # TODO: set fcu.interpolation = 'LINEAR'

        scn = bpy.context.scene

        frame_current = scn.frame_current

        idx = 'XYZ'.index(axis)
        kf1 = offset
        kf2 = 1 * repetitions

        if anim.reverse:
            kfs = {anim.frame_start: 1 - offset,
                   anim.frame_end: 1 - repetitions}
        else:
            kfs = {anim.frame_start: offset,
                   anim.frame_end: repetitions % 1}

    #     if anim.sliceproperty == "Thickness":
    #         kfdefault = kf2
    #     elif anim.sliceproperty == "Position":
    #         kfdefault = kf1
    #     elif anim.sliceproperty == "Angle":
    #         kfdefault = kf1

        # set all frames to default value // fcu.extrapolation
        prop = "slice%s" % anim.sliceproperty
        attr = "%s.%s" % (prop, axis.lower())

    #     print(has_keyframe(vvol, attr))
    #     if not has_keyframe(vvol, attr):
    #     for k in range(scn.frame_start, scn.frame_end):
    #         scn.frame_set(k)
    #         exec('vvol.%s[idx] = kfdefault' % prop.lower())
    #         vvol.keyframe_insert(data_path=prop.lower(), index=idx)

        # remove all keyframes in animation range
    #     for k in range(anim.frame_start, anim.frame_end):
    #         scn.frame_set(k)
    #         vvol.keyframe_delete(data_path=prop.lower(), index=idx)

        # insert the animation
        for k, v in kfs.items():
            scn.frame_set(k)
            exec('vvol.%s[idx] = v' % prop.lower())
            vvol.keyframe_insert(data_path=prop.lower(), index=idx)

        scn.frame_set(frame_current)

    def has_keyframe(self, ob, attr):
        """Check if a property has keyframes set."""

        anim = ob.animation_data
        if anim is not None and anim.action is not None:
            for fcu in anim.action.fcurves:
                fcu.update()
                if attr.startswith(fcu.data_path):
                    path_has_keyframe = len(fcu.keyframe_points) > 0
                    # FIXME: fcu.array_index is always at the first value (fcurves[0])
                    if attr.endswith('.x'):
                        return ((path_has_keyframe) & (fcu.array_index == 0))
                    elif attr.endswith('.y'):
                        return ((path_has_keyframe) & (fcu.array_index == 1))
                    elif attr.endswith('.z'):
                        return ((path_has_keyframe) & (fcu.array_index == 2))
                    else:
                        return path_has_keyframe

        return False


class AnimateTimeSeries(Operator):
    bl_idname = "nb.animate_timeseries"
    bl_label = "Set time series animation"
    bl_description = """Set time series animation"""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_animations = IntProperty(
        name="animation index",
        description="index of the animations collection",
        default=0)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[nb.index_presets]
        nb_anims = nb.animations

#         # time series
#         time_anims = [
#             anim for anim in nb_anims
#             if ((anim.animationtype == "TimeSeries") & (anim.is_rendered))
#                       ]
#         for anim in time_anims:
        anim 
        self.animate_timeseries(context, anim)

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

#         self.index = nb.index_animations

        return self.execute(context)

    def animate_timeseries(self, context, anim):
        """Set up animation of a texture time series."""

        scn = context.scene
        nb = scn.nb

        frame_current = scn.frame_current

        sgs = self.find_ts_scalargroups(context, anim)
        ts_name = anim.anim_timeseries
        sg = sgs[ts_name]

        nframes = anim.frame_end - anim.frame_start
        nscalars = len(sg.scalars)

        if anim.timeseries_object.startswith("S: "):

            # TODO: this is for per-frame jumps of texture
            nb_ma.load_surface_textures(ts_name, sg.texdir, nscalars)

        elif anim.timeseries_object.startswith("V: "):

            # TODO: stepwise fcurve interpolation is not accurate in this way
            nframes = anim.frame_end - anim.frame_start
            fptp = np.floor(nframes/nscalars)

            kfs = {anim.frame_start-1: 0,
                   anim.frame_start: 0,
                   anim.frame_end: nscalars - 1,
                   anim.frame_end+1: nscalars - 1}
            for k, v in kfs.items():
                scn.frame_set(k)
                sg.index_scalars = v
                sg.keyframe_insert("index_scalars")

        scn.frame_set(frame_current)

    def find_ts_scalargroups(self, context, anim):
        """Get the scalargroup to animate."""

        scn = context.scene
        nb = scn.nb

        aliases = {'T': 'tracts', 'S': 'surfaces', 'V': 'voxelvolumes'}

        collkey = anim.timeseries_object[0]
        ts_obname = anim.timeseries_object[3:]

        coll = eval('nb.%s' % aliases[collkey])
        sgs = coll[ts_obname].scalargroups

        return sgs

    def animate_ts_vvol(self):  # scratch

        scn = bpy.context.scene

        frame_current = scn.frame_current

        mat = bpy.data.materials[scalargroup.name]

        tss = [(i, ts) for i, ts in enumerate(mat.texture_slots)
               if ts is not None]

        ntss = len(tss)
        nframes = anim.frame_end - anim.frame_start
        fptp = np.floor(nframes/ntss)

        interpolation = 'CONSTANT'  # 'CONSTANT' TODO: 'LINEAR' 'BEZIER'
        fade_interval = np.floor(fptp / 3)

        props = {"density_factor": 'CONSTANT',
                 "emission_factor": interpolation,
                 "emission_color_factor": 'CONSTANT',
                 "emit_factor": interpolation,
                 "diffuse_color_factor": 'CONSTANT',
                 "alpha_factor": 'CONSTANT'}

    #         # TODO
    #         interval_head = [scn.frame_start, anim.frame_start - 1]
    #         interval_anim = [anim.frame_start, anim.frame_end]
    #         interval_tail = [anim.frame_end + 1, scn.frame_end]

        # can I just keyframe the time index? and let the update function do the work?
        # yes, but this is only for on/off?
        for i, ts in tss:

            tp_start = i*fptp + 1
            tp_end = tp_start + fptp
            tp_in_start = tp_start - fade_interval
            tp_in_end = tp_start + fade_interval
            tp_out_start = tp_end - fade_interval
            tp_out_end = tp_end + fade_interval

            kfs_constant = {tp_start-1: 0, tp_start: 1,
                            tp_end: 1, tp_end+1: 0}
            kfs_linear = {tp_in_start: 0, tp_in_end: 1,
                          tp_out_start: 1, tp_out_end: 0}
            kfs_bezier = {tp_in_start: 0, tp_in_end: 1,
                          tp_out_start: 1, tp_out_end: 0}

            # insert the animation
            for prop, interp in props.items():
                kfs = eval("kfs_%s" % interp.lower())
                for k, v in kfs.items():
                    scn.frame_set(k)
                    exec('ts.%s = v' % prop)
                    ts.keyframe_insert(data_path=prop)

        anim = mat.animation_data
        for fcu in anim.action.fcurves:
            fcu.color_mode = 'AUTO_RAINBOW'
            propname = fcu.data_path.split('.')[-1]
            for kf in fcu.keyframe_points:
                kf.interpolation = props[propname]

        scn.frame_set(frame_current)


class AddAnimation(Operator):
    bl_idname = "nb.import_animations"
    bl_label = "New animation"
    bl_description = "Create a new animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="Anim")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.animations]
        name = nb_ut.check_name(self.name, "", ca)
        animprops = {"name": name}
        nb_ut.add_item(nb, "animations", animprops)

        infostring = 'added animation "%s"'
        info = [infostring % (name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class AddCamPoint(Operator):
    bl_idname = "nb.add_campoint"
    bl_label = "New camera position"
    bl_description = "Create a new camera position in campath"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)
    co = FloatVectorProperty(
        name="camera coordinates",
        description="Specify camera coordinates",
        default=[0.0, 0.0, 0.0])

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        anim = nb.animations[self.index_animations]
        campath = bpy.data.objects[anim.campaths_enum]

        try:
            spline = campath.data.splines[0]
            if spline.type == 'POLY':
                pts = spline.points
            else:
                pts = spline.bezier_points
            pts.add()
        except:
            spline = campath.data.splines.new('POLY')

        if spline.type == 'POLY':
            spline.points[-1].co = tuple(self.co) + (1,)
        else:
            spline.bezier_points[-1].co = tuple(self.co)
            # TODO: handles
        spline.order_u = len(spline.points) - 1
        spline.use_endpoint_u = True

        infostring = 'added campoint "%02f, %02f, %02f"'
        info = [infostring % tuple(self.co)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]

        self.index_animations = nb.index_animations

        cam = bpy.data.objects[preset.cameras[preset.index_cameras].name]
        centre = bpy.data.objects[preset.centre]

        self.co[0] = cam.location[0] * preset.dims[0] / 2 + centre.location[0]
        self.co[1] = cam.location[1] * preset.dims[1] / 2 + centre.location[1]
        self.co[2] = cam.location[2] * preset.dims[2] / 2 + centre.location[2]

        return self.execute(context)


class AddCamPath(Operator):
    bl_idname = "nb.add_campath"
    bl_label = "New camera path"
    bl_description = "Create a new path for the camera"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        default="")
    datapath_camera = StringProperty(
        name="Camera data path",
        description="Specify a the path to the camera",
        default="nb.presets[0].cameras[0]")
    index_presets = IntProperty(
        name="index presets",
        description="Specify preset index",
        default=-1)
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)
    pathtype = EnumProperty(
        name="Pathtype",
        description="Trajectory types for the camera animation",
        items=[("Circular", "Circular",
                "Circular trajectory from camera position", 0),
               ("Streamline", "Streamline",
                "Curvilinear trajectory from a streamline", 1),
               ("Select", "Select",
                "Curvilinear trajectory from curve", 2),
               ("Create", "Create",
                "Create a path from camera positions", 3)],
        default="Circular")
    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="Z")
    anim_tract = StringProperty(
        name="Animation streamline",
        description="Tract to animate",
        default="")
    spline_index = IntProperty(
        name="streamline index",
        description="index of the streamline to animate",
        min=0,
        default=0)
    anim_curve = StringProperty(
        name="Animation curves",
        description="Curve to animate",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        anim = nb.animations[self.index_animations]

        if self.pathtype == "Circular":
            name = "CP_%s" % (self.axis)
        elif self.pathtype == "Streamline":
            name = "CP_%s_%05d" % (self.anim_tract, self.spline_index)
        elif self.pathtype == "Select":
            name = "CP_%s" % (anim.anim_curve)
        elif self.pathtype == "Create":
            name = "CP_%s" % ("fromCam")

        ca = [nb.campaths]
        name = self.name or name
        name = nb_ut.check_name(name, "", ca)
        fun = eval("self.campath_%s" % self.pathtype.lower())
        campath, info = fun(name)

        if campath is not None:
            campath.hide_render = True
#             campath.parent = bpy.data.objects[preset.name]  # TODO: test
            cpprops = {"name": name}
            nb_ut.add_item(nb, "campaths", cpprops)
            infostring = 'added camera path "%s"'
            info = [infostring % (name)] + info

            infostring = 'switched "%s" camera path to "%s"'
            info += [infostring % (anim.name, campath.name)]
            anim.campaths_enum = campath.name
            status = "FINISHED"
        else:
            status = "CANCELLED"

        self.report({'INFO'}, '; '.join(info))

        return {status}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
#         preset = nb.presets[nb.index_presets]
#         self.datapath_camera = preset.cameras[preset.index_cameras]
        self.index_animations = nb.index_animations
        anim = nb.animations[self.index_animations]
        self.pathtype = anim.pathtype
        self.axis = anim.axis
        self.anim_tract = anim.anim_tract
        self.spline_index = anim.spline_index
        self.anim_curve = anim.anim_curve

        return self.execute(context)

    def campath_circular(self, name):
        """Generate a circular trajectory from the camera position."""

        scn = bpy.context.scene
        nb = scn.nb

        preset = nb.presets[self.index_presets]
        nb_cam = preset.cameras[preset.index_cameras]
#         nb_cam = scn.path_resolve(self.datapath_camera)
        cam = bpy.data.objects[nb_cam.name]
        centre = bpy.data.objects[preset.centre]
        box = bpy.data.objects[preset.box]

        camview = cam.location * box.matrix_world

        if 'X' in self.axis:
            idx = 0
            rotation_offset = np.arctan2(camview[2], camview[1])
            r = np.sqrt(camview[1]**2 + camview[2]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, 0, r), (0, h, r), (0, -h, r)),
                      ((0, -r, 0), (0, -r, h), (0, -r, -h)),
                      ((0, 0, -r), (0, -h, -r), (0, h, -r)),
                      ((0, r, 0), (0, r, -h), (0, r, h))]
        elif 'Y' in self.axis:
            idx = 1
            rotation_offset = np.arctan2(camview[0], camview[2])
            r = np.sqrt(camview[0]**2 + camview[2]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, 0, r), (h, 0, r), (-h, 0, r)),
                      ((-r, 0, 0), (-r, 0, h), (-r, 0, -h)),
                      ((0, 0, -r), (-h, 0, -r), (h, 0, -r)),
                      ((r, 0, 0), (r, 0, -h), (r, 0, h))]
        elif 'Z' in self.axis:
            idx = 2
            rotation_offset = np.arctan2(camview[1], camview[0])
            r = np.sqrt(camview[0]**2 + camview[1]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, r, 0), (h, r, 0), (-h, r, 0)),
                      ((-r, 0, 0), (-r, h, 0), (-r, -h, 0)),
                      ((0, -r, 0), (-h, -r, 0), (h, -r, 0)),
                      ((r, 0, 0), (r, -h, 0), (r, h, 0))]

        ob = self.create_circle(name, coords=coords)

        ob.rotation_euler[idx] = rotation_offset
        ob.location = centre.location
        ob.location[idx] = camview[idx] + centre.location[idx]

        origin = mathutils.Vector(coords[0][0]) + centre.location
        o = "%s" % ', '.join('%.2f' % co for co in origin)
        infostring = 'created path around %s with radius %.2f starting at [%s]'
        info = [infostring % (self.axis, r, o)]

        return ob, info

    def campath_streamline(self, name):
        """Generate a curvilinear trajectory from a streamline."""

        scn = bpy.context.scene

        try:
            nb_ob = bpy.data.objects[self.anim_tract]
            spline = nb_ob.data.splines[self.spline_index]
        except KeyError:
            ob = None
            infostring = 'tract "%s:spline[%s]" not found'
        except IndexError:
            ob = None
            infostring = 'streamline "%s:spline[%s]" not found'
        else:
            curve = bpy.data.curves.new(name=name, type='CURVE')
            curve.dimensions = '3D'
            ob = bpy.data.objects.new(name, curve)
            scn.objects.link(ob)

            streamline = [point.co[0:3] for point in spline.points]
            nb_ut.make_polyline(curve, streamline)
            ob.matrix_world = nb_ob.matrix_world
            ob.select = True
            bpy.context.scene.objects.active = ob
            bpy.ops.object.transform_apply(location=False,
                                           rotation=False,
                                           scale=True)

            infostring = 'copied path from tract "%s:spline[%s]"'

        info = [infostring % (self.anim_tract, self.spline_index)]

        return ob, info

    def campath_select(self, name):
        """Generate a campath by copying it from a curve object."""

        scn = bpy.context.scene

        try:
            cubase = bpy.data.objects[self.anim_curve]
        except KeyError:
            ob = None
            infostring = 'curve "%s" not found'
        else:
            cu = cubase.data.copy()
            cu.name = name
            ob = bpy.data.objects.new(name, cu)
            scn.objects.link(ob)
            scn.update()
            ob.matrix_world = cubase.matrix_world
            ob.select = True
            bpy.context.scene.objects.active = ob
            bpy.ops.object.transform_apply(location=False,
                                           rotation=False,
                                           scale=True)
            infostring = 'copied camera path from "%s"'

        info = [infostring % self.anim_curve]

        return ob, info

    def campath_create(self, name):
        """Generate an empty trajectory."""

        scn = bpy.context.scene

        curve = bpy.data.curves.new(name=name, type='CURVE')
        curve.dimensions = '3D'
        ob = bpy.data.objects.new(name, curve)
        scn.objects.link(ob)

        infostring = 'created empty path'

        info = [infostring]

        return ob, info

    def create_circle(self, name, coords):
        """Create a bezier circle from a list of coordinates."""

        scn = bpy.context.scene

        cu = bpy.data.curves.new(name, type='CURVE')
        cu.dimensions = '3D'
        ob = bpy.data.objects.new(name, cu)
        scn.objects.link(ob)
        scn.objects.active = ob
        ob.select = True

        polyline = cu.splines.new('BEZIER')
        polyline.bezier_points.add(len(coords) - 1)
        for i, coord in enumerate(coords):
            polyline.bezier_points[i].co = coord[0]
            polyline.bezier_points[i].handle_left = coord[1]
            polyline.bezier_points[i].handle_right = coord[2]

        polyline.use_cyclic_u = True

        return ob


class DelCamPath(Operator):
    bl_idname = "nb.del_campath"
    bl_label = "Delete camera path"
    bl_description = "Delete a camera path"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        default="")
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        try:
            campath = bpy.data.objects[self.name]
            cu = bpy.data.curves[self.name]
        except KeyError:
            infostring = 'camera path curve "%s" not found'
        else:
            bpy.data.curves.remove(cu)
            bpy.data.objects.remove(campath)
            nb.campaths.remove(nb.campaths.find(self.name))
            nb.index_campaths = 0
            # TODO: find and reset all animations that use campath
            infostring = 'removed camera path curve "%s"'

        info = [infostring % self.name]

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_animations = nb.index_animations
        anim = nb.animations[self.index_animations]
        self.name = anim.campaths_enum

        return self.execute(context)


class ObjectListAN(UIList):

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


class ObjectListCP(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        item_icon = "CANCEL"
        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            row = layout.row()
            row.prop(item, "co", text="cp", emboss=True, icon=item_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class MassIsRenderedAN(Menu):
    bl_idname = "nb.mass_is_rendered_AN"
    bl_label = "Animation Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_AN'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_AN'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_AN'


class MassIsRenderedCP(Menu):
    bl_idname = "nb.mass_is_rendered_CP"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_CP'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_CP'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_CP'
