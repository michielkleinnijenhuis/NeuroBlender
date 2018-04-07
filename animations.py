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
from bpy.types import PropertyGroup as pg
from bpy.types import (Operator,
                       UIList,
                       Menu)
from bpy.props import (StringProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       IntProperty,
                       FloatProperty)

from . import (materials as nb_ma,
               properties as nb_pr,
               utils as nb_ut)


class NB_OT_set_animations(Operator):
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
            if ((anim.animationtype == "camerapath") & (anim.is_rendered)):
                del_indices.append(i)
                cam_anims.append(anim)
        self.clear_camera_path_animations(cam, nb_anims, del_indices)
        self.create_camera_path_animations(cam, cam_anims)

        # slice fly-throughs
        slice_anims = [anim for anim in nb_anims
                       if ((anim.animationtype == "carver") &
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
                      if ((anim.animationtype == "timeseries") &
                          (anim.is_rendered))]
        for anim in time_anims:
            self.animate_timeseries(anim)

        return {"FINISHED"}


class NB_OT_animate_camerapath(Operator):
    bl_idname = "nb.animate_camerapath"
    bl_label = "Set animations"
    bl_description = "Add a camera trajectory animation"""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="CameraPathAnimation")
    camera = StringProperty(
        name="Cam",
        description="Specify a name for the animation",
        default="Cam")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        # TODO: validate preset
        nb_preset = nb.presets[nb.index_presets]

        if ((bpy.data.objects.get(self.camera) is None) or
                (nb_preset.cameras.get(self.camera) is None)):
            return {"CANCELLED"}

        ca = [nb.animations]
        name = nb_ut.check_name(self.name, "", ca)

        animprops = {"name": name,
                     "animationtype": 'camerapath',
                     "icon": "ANIM"}
        anim = nb_ut.add_item(nb, "animations", animprops)
        anim.animationtype = 'camerapath'
        anim.camera = self.camera

        self.animate(anim)

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[nb.index_presets]
        nb_cam = nb_preset.cameras[nb_preset.index_cameras]
        self.camera = nb_cam.name

        return self.execute(context)

    def animate(self, anim):
        """Set up a camera trajectory animation."""

        scn = bpy.context.scene
        nb = scn.nb

        cam = bpy.data.objects.get(self.camera)

        anims = self.select_animations(nb.animations, self.camera)
        self.clear_camera_path_animations(cam, anims)
        self.create_camera_path_animations(cam, anims)
        nb_ut.validate_anims_campath(anims)

    def clear_camera_path_animations(self, cam, anims):
        """Remove all camera trajectory animations."""

        for anim in anims:
            self.clear_camera_path_animation(cam, anim)

        self.update_cam_constraints(cam, anims)

    def clear_camera_path_animation(self, cam, anim):
        """Remove a camera trajectory animation."""

        self.clear_CP_evaltime(anim)
        self.clear_CP_followpath(anim)
        self.remove_CP_followpath(cam, anim)

    @staticmethod
    def clear_CP_evaltime(anim):
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

    @staticmethod
    def clear_CP_followpath(anim):
        """Remove the keyframes on the FollowPath constraint."""

        actname = '{}Action'.format(anim.camera)
        props = ['use_fixed_location', 'offset_factor',
                 'forward_axis', 'influence']
        for prop in props:
            dpath = 'constraints["{}"].{}'.format(anim.cnsname, prop)
            try:
                act = bpy.data.actions[actname]
            except:
                pass
            else:
                fcu = act.fcurves.find(dpath)
                if fcu is not None:
                    bpy.data.actions[actname].fcurves.remove(fcu)

    @staticmethod
    def remove_CP_followpath(cam, anim):
        """Delete a FollowPath constraint from the camera."""

        try:
            cns = cam.constraints[anim.cnsname]
        except KeyError:
            pass
        else:
            cam.constraints.remove(cns)

    @staticmethod
    def update_cam_constraints(cam, cam_anims):
        """Update the basic constraints of the camera."""

        scn = bpy.context.scene

        try:
            action = bpy.data.actions['{}Action'.format(cam.name)]
        except KeyError:
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
            timeline = generate_timeline(scn, cam_anims)
            restrict_trans_timeline(scn, cns, timeline, group="ChildOf")

            dpath = 'constraints["TrackToObject"].influence'
            fcu = action.fcurves.find(dpath)
            action.fcurves.remove(fcu)
            # add the constraint keyframes back again
            cns = cam.constraints["TrackToObject"]
            timeline = generate_timeline(scn, cam_anims, trackcentre=True)
            restrict_incluence_timeline(scn, cns, timeline, group="TrackTo")

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
            self.animate_campath(anim)
            self.animate_camera(anim)

        cnsCO = nb_ut.add_constraint(cam, "CHILD_OF", "Child Of", box)
        timeline = generate_timeline(scn, anims)
        restrict_trans_timeline(scn, cnsCO, timeline, group="ChildOf")

        cnsTT = nb_ut.add_constraint(cam, "TRACK_TO", "TrackToObject", centre)
        timeline = generate_timeline(scn, anims, trackcentre=True)
        restrict_incluence_timeline(scn, cnsTT, timeline, group="TrackTo")

    @staticmethod
    def animate_campath(anim=None):
        """Set up camera path animation."""

        scn = bpy.context.scene

        try:
            campath = bpy.data.objects[anim.campaths_enum]
        except KeyError:
            return

        campath.data.use_path = True
        actname = "{}Action".format(campath.data.name)
        try:
            fcu = bpy.data.actions[actname].fcurves.find("eval_time")
        except:
            animdata = campath.data.animation_data_create()
            animdata.action = bpy.data.actions.new(actname)
            fcu = animdata.action.fcurves.new("eval_time")

        mod = fcu.modifiers.new('GENERATOR')
        intercept, slope, _ = calculate_coefficients(campath, anim)
        mod.coefficients = (intercept, slope)
        mod.use_additive = True
        mod.use_restricted_range = True
        mod.frame_start = anim.frame_start
        mod.frame_end = anim.frame_end

    @staticmethod
    def animate_camera(anim, cns=None):
        """Set up camera animation."""

        scn = bpy.context.scene

        try:
            cam = bpy.data.objects[anim.camera]
        except KeyError:
            return

        frame_current = scn.frame_current

        if cns is None:
            cnsname = "FollowPath_{}".format(anim.name)
            campath = bpy.data.objects.get(anim.campaths_enum)
            cns = nb_ut.add_constraint(cam, "FOLLOW_PATH", cnsname,
                                       campath, anim.tracktype)
            anim.cnsname = cns.name
        else:
            cnsname = anim.cnsname

        restrict_incluence(cns, anim, group=cnsname)
        cns.offset = anim.offset * -100

#         TODO: build fcurve instead of keyframing
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
                cns.keyframe_insert("use_fixed_location", group=cnsname)
                cns.keyframe_insert("offset_factor", group=cnsname)
                cns.keyframe_insert("forward_axis", group=cnsname)

        scn.frame_set(frame_current)

    @staticmethod
    def select_animations(anims, camname=""):

        cam_anims = [anim for anim in anims
                     if anim.animationtype == "camerapath"]
        ren_anims = [anim for anim in cam_anims
                     if anim.is_rendered]
        if camname:
            return [anim for anim in ren_anims
                    if anim.camera == camname]
        else:
            return ren_anims


class NB_OT_animate_carver(Operator):
    bl_idname = "nb.animate_carver"
    bl_label = "Set carver animation"
    bl_description = "Add a carver animation"""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="CarverAnimation")

    nb_object_data_path = StringProperty(
        name="Carveobject data path",
        description="Specify a the path to the carveobject")
    sliceproperty = EnumProperty(
        name="Property to animate",
        description="Select property to animate",
        items=[("Thickness", "Thickness", "Thickness", 0),
               ("Position", "Position", "Position", 1),
               ("Angle", "Angle", "Angle", 2)],
        default="Position")
    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="Z")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.animations]
        name = nb_ut.check_name(self.name, "", ca)

        animprops = {"name": name,
                     "animationtype": 'carver',
                     "icon": "MOD_BOOLEAN",
                     "nb_object_data_path": self.nb_object_data_path,
                     "sliceproperty": self.sliceproperty,
                     "axis": self.axis}
        anim = nb_ut.add_item(nb, "animations", animprops)
        anim.animationtype = 'carver'

        if anim.nb_object_data_path != 'no_carveobjects':
            self.animate(anim)

        return {"FINISHED"}

    @staticmethod
    def animate(anim):
        """Set up a carver animation."""

        scn = bpy.context.scene
        nb = scn.nb

        nb_ob = scn.path_resolve(anim.nb_object_data_path)

        try:
            pg_sc1 = bpy.types.TractProperties
        except AttributeError:
            pg_sc1 = pg.bl_rna_get_subclass_py("TractProperties")

        aca = bpy.types.NB_OT_animate_carver
        if isinstance(nb_ob, pg_sc1):
            aca.animate_carver_tracts(anim)
        else:
            aca.animate_carver_voxelvolumes(anim)

        # update
        bpy.context.scene.frame_current = scn.frame_current

    @staticmethod
    def animate_carver_tracts(anim):
        """Animate a tract carver."""

        scn = bpy.context.scene

        nb_ob = scn.path_resolve(anim.nb_object_data_path)
        tractob = bpy.data.objects[nb_ob.name]

        rangedict = {'bevel_factor_start': [0, 1],
                     'bevel_depth': [0, tractob.data.bevel_depth]}

        prop = anim.sliceproperty
        prop_path = '{}'.format(prop)
        idx = 0
        actionname = '{}Action'.format(anim.name)

        if anim.rna_data_path:
            prev_rna = eval(anim.rna_data_path)
            if anim.rna_data_path == 'bpy.context.scene':
                curve = None
                ad = tractob.data.animation_data_create()
                prev_rna.animation_data_clear()
            elif prev_rna != tractob.data:
                curve = prev_rna
                ad = copy_animation_data(prev_rna, tractob.data)
                prev_rna.animation_data_clear()
            else:
                curve = tractob.data
                ad = tractob.data.animation_data_create()
            restore_state_carver(anim, curve)
        else:
            ad = tractob.data.animation_data_create()

        fcu = get_animation_fcurve(anim, ad, data_path=prop_path,
                                   idx=idx, actionname=actionname)
        fcu.data_path = anim.fcurve_data_path = prop_path
        fcu.array_index = anim.fcurve_array_index = idx
        anim.rna_data_path = 'bpy.data.objects["{}"].data'.format(tractob.name)
        anim.default_value = eval('{}.{}'.format(anim.rna_data_path, prop_path))
        build_fcurve(rangedict[prop], fcu, anim)

    @staticmethod
    def animate_carver_voxelvolumes(anim):
        """Animate a voxelvolume carver."""

        scn = bpy.context.scene

        rangedict = {'slicethickness': [0, 1],
                     'sliceposition': [-1, 1],
                     'sliceangle': [-1.5708, 1.5708]}

        prop = "slice{}".format(anim.sliceproperty.lower())
        prop_path = '{}.{}'.format(anim.nb_object_data_path, prop)
        idx = 'XYZ'.index(anim.axis)
        actionname = 'SceneAction'

        if anim.rna_data_path:
            if anim.rna_data_path != 'bpy.context.scene':
                prev_rna = eval(anim.rna_data_path)
                prev_rna.animation_data_clear()
                restore_state_carver(anim, prev_rna)
            else:
                restore_state_carver(anim)
        else:
            restore_state_carver(anim)

        ad = scn.animation_data_create()
        fcu = get_animation_fcurve(anim, ad, data_path=prop_path,
                                   idx=idx, actionname=actionname)
        fcu.data_path = anim.fcurve_data_path = prop_path
        fcu.array_index = anim.fcurve_array_index = idx
        anim.rna_data_path = 'bpy.context.scene'
        anim.default_value = scn.path_resolve('{}[{}]'.format(prop_path, idx))
        build_fcurve(rangedict[prop], fcu, anim)


class NB_OT_animate_timeseries(Operator):
    bl_idname = "nb.animate_timeseries"
    bl_label = "Set time series animation"
    bl_description = "Add a time series animation"""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="TimeSeriesAnimation")

    nb_object_data_path = StringProperty(
        name="Scalargroup data path",
        description="Specify a the path to the scalargroup")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.animations]
        name = nb_ut.check_name(self.name, "", ca)

        animprops = {"name": name,
                     "animationtype": 'timeseries',
                     "icon": "TIME",
                     "nb_object_data_path": self.nb_object_data_path}
        anim = nb_ut.add_item(nb, "animations", animprops)
        anim.animationtype = 'timeseries'

        self.animate(anim)

        return {"FINISHED"}

    @staticmethod
    def animate(anim):
        """Set up a texture time series animation."""

        scn = bpy.context.scene
        nb = scn.nb

        # FIXME: the path might change on deleting objects
        prop = 'index_scalars'
        prop_path = '{}.{}'.format(anim.nb_object_data_path, prop)
        # get or create the fcurve for this animation
        ad = scn.animation_data_create()
        fcu = get_animation_fcurve(anim, ad, data_path=prop_path)
        # update the data_path and index
        fcu.data_path = anim.fcurve_data_path = prop_path
        # reset the state of the previous prop to the frame-0 value
        restore_state_timeseries(anim)
        anim.default_value = scn.path_resolve(prop_path)

        # Calculate the coordinates of the points in the fcurve
        sg = scn.path_resolve(anim.nb_object_data_path)
        build_fcurve([0, len(sg.scalars)], fcu, anim)

        # update
        bpy.context.scene.frame_current = scn.frame_current

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


class NB_OT_animate_morph(Operator):
    bl_idname = "nb.animate_morph"
    bl_label = "Set morph animation"
    bl_description = "Add a morph animation"""
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="MorphAnimation")

    animationtype = StringProperty(
        name="Animation type",
        description="dummy",
        default="morph")
    nb_object_data_path = EnumProperty(
        name="Animation object",
        description="Specify path to object to animate",
        items=nb_pr.anim_nb_object_enum_callback)
#     nb_object_data_path = StringProperty(
#         name="Morphobject data path",
#         description="Specify a the path to the morphobject")

    nb_target_data_path = StringProperty(
        name="Morphobject data path",
        description="Specify a the path to the morphobject")

    def draw(self, context):

        row = self.layout.row()
        row.prop(self, "nb_object_data_path")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.animations]
        name = nb_ut.check_name(self.name, "", ca)

        animprops = {"name": name,
                     "animationtype": 'morph',
                     "icon": "MOD_BOOLEAN",
                     "nb_object_data_path": self.nb_object_data_path,
                     "nb_target_data_path": self.nb_target_data_path}
        anim = nb_ut.add_item(nb, "animations", animprops)
        anim.animationtype = 'morph'

        if anim.nb_object_data_path != 'no_objects':
            self.animate(anim)
            # TODO: carved objects?

        return {"FINISHED"}

    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)

    @staticmethod
    def animate(anim):
        """Set up a carver animation."""

        scn = bpy.context.scene
        nb = scn.nb

        amo = bpy.types.NB_OT_animate_morph
        amo.animate_morph_surfaces(anim)

        # update
        scn.frame_current = scn.frame_current

    @staticmethod
    def animate_morph_surfaces(anim):
        """Animate a surface morph."""

        scn = bpy.context.scene

        nb_ob = scn.path_resolve(anim.nb_object_data_path)
        ob = bpy.data.objects[nb_ob.name]

        amo = bpy.types.NB_OT_animate_morph
        amo.add_shape_key(anim, ob)
        amo.update_fcurve(anim)

    @staticmethod
    def update_fcurve(anim):

        scn = bpy.context.scene

        nb_ob = scn.path_resolve(anim.nb_object_data_path)
        ob = bpy.data.objects[nb_ob.name]

        nblocks = len(ob.data.shape_keys.key_blocks)
        rangedict = {'eval_time': [10, nblocks * 10]}

        ad_rna = ob.data.shape_keys
        prop = 'eval_time'
        prop_path = '{}'.format(prop)
        idx = 0
        actionname = '{}Action'.format(anim.name)

        if anim.rna_data_path:
            prev_rna = eval(anim.rna_data_path)
            if anim.rna_data_path == 'bpy.context.scene':
                ad = ad_rna.animation_data_create()
                prev_rna.animation_data_clear()
            elif prev_rna != ad_rna:
                ad = copy_animation_data(prev_rna, ad_rna)
                prev_rna.animation_data_clear()
            else:
                ad = ad_rna.animation_data_create()
#             restore_state_morph(anim)
        else:
            ad = ad_rna.animation_data_create()

        fcu = get_animation_fcurve(anim, ad, data_path=prop_path,
                                   idx=idx, actionname=actionname)
        fcu.data_path = anim.fcurve_data_path = prop_path
        fcu.array_index = anim.fcurve_array_index = idx
        anim.rna_data_path = 'bpy.data.shape_keys["{}"]'.format(ad_rna.name)
        anim.default_value = eval('{}.{}'.format(anim.rna_data_path, prop_path))
        build_fcurve(rangedict[prop], fcu, anim)

    @staticmethod
    def add_shape_key(anim, ob):

        from_point = anim.nb_target_data_path == 'from_point'

        # get target shape object
        scn = bpy.context.scene
        if from_point:
            shape = None
        else:
            nb_tg = scn.path_resolve(anim.nb_target_data_path)
            shape = bpy.data.objects[nb_tg.name]
            # hide the target object
            shape.hide = shape.hide_render = shape != ob

        # add shape key
        amo = bpy.types.NB_OT_animate_morph
        key_block = amo.add_key_block(ob, shape, from_point=from_point)

        # turn into absolute shape key
        shape_keys = ob.data.shape_keys
        shape_keys.use_relative = False
        ob.active_shape_key_index = len(ob.data.shape_keys.key_blocks) - 1  # TODO: always add at end
        override = bpy.context.copy()
        override['object'] = ob
        bpy.ops.object.shape_key_retime(override)

        return shape_keys

    @staticmethod
    def add_key_block(ob, shape, from_point=False):

        if from_point:
            shape_key = ob.shape_key_add(name='from_point', from_mix=False)
            for vert in ob.data.vertices:
                shape_key.data[vert.index].co = [0, 0, 0]
        else:
            shape_key = ob.shape_key_add(name=shape.name, from_mix=False)
            for vert in shape.data.vertices:
                shape_key.data[vert.index].co = vert.co

        return shape_key


class NB_OT_import_animation(Operator):
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

    animationtype = EnumProperty(
        name="Animation type",
        description="Switch between animation types",
        items=[("camerapath", "Camera trajectory",
                "Let the camera follow a trajectory", 0),
               ("carver", "Carver",
                "Animate a carver", 1),
               ("timeseries", "Time series",
                "Play a time series", 2)],
        default='camerapath')

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.animations]
        name = nb_ut.check_name(self.name, "", ca)

        icondict = {"CameraPath": "ANIM",
                    "Carver": "MOD_BOOLEAN",
                    "TimeSeries": "TIME"}
        animprops = {"name": name,
                     "animationtype": self.animationtype,  # FIXME!! reverts back to default in properties (CameraPath) for some reason
                     "icon": icondict[self.animationtype]}
        nb_ut.add_item(nb, "animations", animprops)
#         op = 'bpy.ops.nb.animate_{}'.format(self.animationtype)
#         op('INVOKE_DEFAULT')

        infostring = 'added animation "%s"'
        info = [infostring % (name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.animationtype = nb.animationtype

        return self.execute(context)


class NB_OT_campoint_add(Operator):
    bl_idname = "nb.campoint_add"
    bl_label = "New camera position"
    bl_description = "Create a new camera position in campath"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    campathname = StringProperty(
        name="Camera trajectory",
        description="Specify the curve for the camera trajectory",
        default="")
    co = FloatVectorProperty(
        name="camera coordinates",
        description="Specify camera coordinates",
        default=[0.0, 0.0, 0.0])

    def execute(self, context):

        scn = context.scene

        campath = bpy.data.objects[self.campathname]

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

        cam = scn.camera
        presetname = cam.data.name[:-7]  # TODO
        preset = scn.path_resolve('nb.presets["{}"]'.format(presetname))
        centre = bpy.data.objects[preset.centre]

        for dim in [0, 1, 2]:
            print(cam.location[dim], preset.dims[dim] / 2, centre.location[dim])
            self.co[dim] = cam.location[dim] * preset.dims[dim] / 2 + centre.location[dim]

        anim = nb.animations[nb.index_animations]
        self.campathname = anim.campaths_enum

        return self.execute(context)


class NB_OT_campath_add(Operator):
    bl_idname = "nb.campath_add"
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

        nb_preset = nb.presets[self.index_presets]
        cpsname = nb_preset.name + 'Campaths'
        # TODO: homogenize naming system with Box/Centre
        nb_preset["campathsempty"] = cpsname
        campathsempty = bpy.data.objects.get(cpsname)
        if not campathsempty:
            campathsempty = bpy.data.objects.new(cpsname, None)
            scn.objects.link(campathsempty)
            campathsempty.parent = bpy.data.objects[nb_preset.camerasempty]

        ca = [nb.campaths]
        name = self.name or name
        name = nb_ut.check_name(name, "", ca)
        fun = eval("self.campath_%s" % self.pathtype.lower())
        campath, info = fun(name)

        if campath is not None:
            campath.hide_render = True
            campath.parent = campathsempty
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


class NB_OT_campath_remove(Operator):
    bl_idname = "nb.campath_remove"
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


def get_animation_fcurve(anim, ad, data_path='', idx=-1,
                         remove=False, npoints=2,
                         actionname='SceneAction'):
    """Get or remove an fcurve for an animation."""

    scn = bpy.context.scene
    nb = scn.nb

    try:
        ad.action = bpy.data.actions[actionname]
    except KeyError:
        ad.action = bpy.data.actions.new(actionname)

    fcurves = ad.action.fcurves
    try:
        fcu = fcurves.find(anim.fcurve_data_path, anim.fcurve_array_index)
    except RuntimeError:
        fcu = fcurves.new(data_path, index=idx, action_group=anim.name)
        fcu.keyframe_points.add(npoints)  # TODO: flexibility
    else:
        if fcu is None:
            fcu = fcurves.new(data_path, index=idx, action_group=anim.name)
            fcu.keyframe_points.add(npoints)  # TODO: flexibility

    if remove:
        fcurves.remove(fcu)
        fcu = None

    return fcu


def restore_state_carver(anim, curve=None):
    """Restore a previous state of a carver property."""

    scn = bpy.context.scene

    dp = anim.fcurve_data_path
    ai = anim.fcurve_array_index
    pv = anim.default_value

    if not dp:
        return

    if curve is None:
        prev_prop = dp.split('.')[-1]
        data_path = '.'.join(dp.split('.')[:-1])
        item = scn.path_resolve(data_path)
        exec('item.{}[{:d}] = {:f}'.format(prev_prop, ai, pv))
    else:
        exec('curve.{} = {:f}'.format(dp, pv))


def restore_state_timeseries(anim):
    """Restore a previous state of a timeseries index property."""

    scn = bpy.context.scene

    dp = anim.fcurve_data_path
    pv = anim.default_value

    # TODO: might do the same for labels?
    prev_prop = 'index_scalars'
    data_path = '.'.join(dp.split('.')[:-1])
    item = scn.path_resolve(data_path)
    exec('item.{} = {:d}'.format(prev_prop, int(pv)))


def restore_state_morph(anim):
    """Restore a previous state of a carver property."""

    scn = bpy.context.scene

    nb_ob = scn.path_resolve(anim.nb_object_data_path)
    ob = bpy.data.objects[nb_ob.name]

    override = bpy.context.copy()
    override['object'] = ob
    bpy.ops.object.shape_key_remove(override, all=True)

    # update
    for obj in bpy.context.scene.objects:
        obj.select = ob == obj
    bpy.context.scene.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.object.mode_set(mode='OBJECT')


def calculate_coefficients(campath, anim):
    """Calculate the coefficients for a campath modifier."""

    max_val = anim.repetitions * campath.data.path_duration
    slope = max_val / (anim.frame_end - anim.frame_start)
    intercept = -(anim.frame_start) * slope

    if anim.reverse:
        intercept = -intercept + 100  # TODO: check correctness of value 100
        slope = -slope
        max_val = -max_val

    return intercept, slope, max_val


def generate_timeline(scn, anims, trackcentre=False):
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


def restrict_trans_timeline(scn, cns, timeline, group=""):
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


def restrict_incluence_timeline(scn, cns, timeline, group=""):
    """Restrict the influence of a constraint according to timeline."""

    frame_current = scn.frame_current

    scn.frame_set(scn.frame_start)
    cns.influence = timeline[scn.frame_start]
    cns.keyframe_insert("influence", group=group)

    for fr in range(scn.frame_start+1, scn.frame_end):
        scn.frame_set(fr)
        cns.influence = timeline[fr]
        cns.keyframe_delete("influence", group=group)
        if ((timeline[fr] != timeline[fr-1]) or
            timeline[fr] != timeline[fr+1]):
            cns.keyframe_insert("influence", group=group)

    scn.frame_set(scn.frame_end)
    cns.influence = timeline[scn.frame_end]
    cns.keyframe_insert("influence", group=group)

    scn.frame_set(frame_current)


def restrict_incluence(cns, anim, group=""):
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
            cns.keyframe_insert(data_path="influence", index=-1, group=group)

    scn.frame_set(frame_current)


def setup_animation_rendering(filepath="render/anim",
                              file_format="AVI_JPEG",
                              blendpath=""):
    """Set rendering properties for animations."""

    scn = bpy.context.scene

    scn.render.filepath = filepath
    scn.render.image_settings.file_format = file_format
    bpy.ops.render.render(animation=True)

    bpy.ops.wm.save_as_mainfile(filepath=blendpath)


def build_fcurve(animrange, fcu, anim):
    """Build a new fcurve."""

    vrange = animrange[1] - animrange[0]
    trange = anim.anim_range[1] - anim.anim_range[0]
    animrange[0] += anim.anim_range[0] * vrange
    animrange[1] = animrange[0] + trange * vrange

    add_fcurve_modifiers(fcu, anim, animrange)

    kfs = get_fcurve_coordinates(animrange, anim)

    for i, (k, v) in enumerate(sorted(kfs.items())):
        kp = fcu.keyframe_points[i]
        kp.co = (k, v)
        if k == 0:
            kp.interpolation = 'CONSTANT'
        else:
            kp.interpolation = anim.interpolation


def add_fcurve_modifiers(fcu, anim, animrange=[]):
    """Add FCurve modifiers."""

    for mod in fcu.modifiers:
        fcu.modifiers.remove(mod)

    mod = fcu.modifiers.new('CYCLES')
    mod.use_restricted_range = True
    mod.frame_start = anim.frame_start
    mod.frame_end = anim.frame_end
    mod.mode_before = 'NONE'
    if anim.mirror:
        mod.mode_after = 'MIRROR'
    else:
        mod.mode_after = 'REPEAT'

    mod = fcu.modifiers.new('NOISE')
    mod.use_restricted_range = True
    mod.frame_start = anim.frame_start
    mod.frame_end = anim.frame_end
    mod.scale = anim.noise_scale
    mod.strength = anim.noise_strength

    mod = fcu.modifiers.new('LIMITS')
    if animrange:
        mod.use_min_y = True
        mod.use_max_y = True
        mod.min_y = animrange[0]
        mod.max_y = animrange[1]


def get_fcurve_coordinates(prange, anim, default_value=None):
    """Calculate the coordinates of the points in the fcurve."""

    vrange = prange[1] - prange[0]
    trange = anim.frame_end - anim.frame_start
    start = anim.frame_start

    if anim.repetitions > 1:
        end = start + trange / anim.repetitions
    else:
        prange[1] *= anim.repetitions
        end = start + trange

    if anim.reverse:
        prange.reverse()
        prange[0] -= anim.offset * vrange
    else:
        prange[0] += anim.offset * vrange

    kfs = {start: prange[0], end: prange[1]}

    if default_value is not None:
        kfs[0] = default_value

    return kfs


def copy_animation_data(source, target):
    """Copy animation data between data blocks."""

    ad = source.animation_data

    properties = [p.identifier for p in ad.bl_rna.properties
                  if not p.is_readonly]

    if target.animation_data is None:
        target.animation_data_create()
    ad2 = target.animation_data
#     ad2.action.name = '{}Action'.format(target.name)
    for prop in properties:
        setattr(ad2, prop, getattr(ad, prop))

    return ad2


# class NB_OT_animate_grow(Operator):
#     bl_idname = "nb.animate_grow"
#     bl_label = "Set growth animation"
#     bl_description = "Add a growth animation"""
#     bl_options = {"REGISTER", "UNDO", "PRESET"}
# 
#     name = StringProperty(
#         name="Name",
#         description="Specify a name for the animation",
#         default="GrowAnimation")
# 
#     nb_object_data_path = StringProperty(
#         name="Object data path",
#         description="Specify a the path to the object")
# 
#     def execute(self, context):
# 
#         scn = context.scene
#         nb = scn.nb
# 
#         ca = [nb.animations]
#         name = nb_ut.check_name(self.name, "", ca)
# 
#         animprops = {"name": name,
#                      "animationtype": 'grow',
#                      "icon": "FULLSCREEN_ENTER",
#                      "nb_object_data_path": self.nb_object_data_path}
#         anim = nb_ut.add_item(nb, "animations", animprops)
#         anim.animationtype = 'grow'
# 
#         self.animate(anim)
# 
#         return {"FINISHED"}
# 
#     @staticmethod
#     def animate(anim):
#         """Set up a grow animation."""
# 
#         scn = bpy.context.scene
#         nb = scn.nb
# 
#         nb_ob = scn.path_resolve(anim.nb_object_data_path)
#         tractob = bpy.data.objects[nb_ob.name]
# 
#         ad = tractob.data.animation_data_create()
#         actname = '{}Action'.format(tractob.name)
# 
#         prop = 'bevel_factor_start'
#         fcu, prev = get_animation_fcurve_data(anim, data_path=prop, idx=0,
#                                               ad=ad, actionname=actname)
#         fcu.data_path = anim.fcurve_data_path = prop
#         if prev:
#             tractob.data.bevel_factor_start = anim.default_value
#         else:
#             anim.default_value = tractob.data.bevel_factor_start
# 
#         build_fcurve([0, 1], fcu, anim)
# 
#         # update
#         bpy.context.scene.frame_current = scn.frame_current
# 
#     def copy_tract(self, context, tractob, create_mirmod=False):
#         """Grow tract via building point-by-point"""
# 
#         scn = bpy.context.scene
#         scn.frame_current = 0
# 
#         # TODO: unique
#         name = tractob.name + "_grow"
#         tractob_copy = tractob.copy()
#         curve_copy = tractob.data.copy()
#         tractob_copy.data = curve_copy
#         tractob_copy.name = name
#         splines = tractob_copy.data.splines
#         for spl in splines:
#             splines.remove(spl)
#         splines = tractob.data.splines
#         for spl in splines:
#             polyline = tractob_copy.data.splines.new('POLY')
#             polyline.points[0].co = spl.points[0].co
# 
#         context.scene.objects.link(tractob_copy)
# 
#         # mirror over x
#         if create_mirmod:
#             mirmod = tractob_copy.modifiers.new('mirror_x', type='MIRROR')
# 
#         return tractob_copy
# 
#     def sort_splines(self, context, tractob):
#         """"""
# 
#         centre = bpy.data.objects.get('Centre')
#         loc = centre.location
#         sldict = {}
#         for idx, spl in enumerate(tractob.data.splines):
#             points = [p.co for p in spl.points]
#             cp_vox = np.mean(np.array(points), axis=0)
#             cp = tractob.matrix_world * Vector(cp_vox[:3])
#             distance = sqrt((loc[0]-cp[0])**2+(loc[1]-cp[1])**2+(loc[2]-cp[2])**2)
#             sldict[idx] = {'cp': cp_vox, 'dist': distance}
#         sldict_inv = {v['dist']: idx for idx, v in sldict.items()}
#         idxlist = []
#         for _, v in sorted(sldict_inv.items()):
#             idxlist.append(v)
#         sel_idx = idxlist
# 
#         return sldict, idxlist, sel_idx
# 
#     def grow_tract(dummy):
#         """Grow 3D curves (from the middle, selected)."""
# 
#         scn = bpy.context.scene
#         tractob = scn.objects['tracks_CC']
#         growob = scn.objects['tracks_CC_grow']
#         stepsize = growob['stepsize']
#         steps_per_frame = growob['steps_per_frame']
#         sel_idx = growob['sel_idx']['sel_idx']
#         offsets = growob['offsets']['offsets']
#         idxs_per_frame = steps_per_frame * stepsize
#         for idx, offset in zip(sel_idx, offsets):
#             spl_old = tractob.data.splines[idx]
#             spl_new = growob.data.splines[idx]
#             idx_block = (scn.frame_current - offset) * idxs_per_frame
#             for step in range(0, steps_per_frame):
#                 p_idx = idx_block + step * stepsize
#                 if p_idx < 1:
#                     continue
#                 try:
#                     old_point_co = spl_old.points[p_idx].co
#                 except IndexError:
#                     pass
#                 else:
#                     try:
#                         new_point = spl_new.points[p_idx]
#                     except IndexError:
#                         spl_new.points.add(1)
#                         new_point = spl_new.points[-1]
#                     new_point.co = old_point_co


class NB_OT_switch_direction(Operator):
    bl_idname = "nb.switch_direction"
    bl_label = "Switch spline directions"
    bl_description = "Switch direction of subset of splines"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    point_index = IntProperty(
        name="Point index",
        description="Index of the spline's reference point",
        default=0,
        min=0)

    axis = EnumProperty(
        name="Axis",
        description="Symmetry axis",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="X")

    co = FloatProperty(
        name="Coordinate",
        description="Coordinate",
        default=0.)

    def draw(self, context):

        row = self.layout.row()
        row.prop(self, "point_index")

        row = self.layout.row()
        row.prop(self, "axis", expand=True)

        row = self.layout.row()
        row.prop(self, "co")

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        split_path = self.data_path.split('.')
        nb_ob = scn.path_resolve('.'.join(split_path[:2]))
        name = nb_ob.name
        tractob = bpy.data.objects[name]

        self.switch_direction(tractob,
                              idx=self.point_index,
                              axis='XYZ'.index(self.axis),
                              co=self.co)

        return {"FINISHED"}

    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)

    def switch_direction(self, tractob, idx=0, axis=0, co=0.):
        """Switch direction of splines."""

        for spl in tractob.data.splines:
            for point in spl.points:
                point.select = spl.points[idx].co[axis] > co

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.switch_direction()
        bpy.ops.object.mode_set(mode='OBJECT')

