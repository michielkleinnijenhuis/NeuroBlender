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


"""The NeuroBlender imports (surfaces) module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements importing surfaces into NeuroBlender.
"""


import os
import numpy as np
from mathutils import Matrix

import bpy
from bpy.types import (Operator,
                       OperatorFileListElement)
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty)
from bpy_extras.io_utils import ImportHelper

from .. import (materials as nb_ma,
                utils as nb_ut)


class ImportSurfaces(Operator, ImportHelper):
    bl_idname = "nb.import_surfaces"
    bl_label = "Import surfaces"
    bl_description = "Import surfaces as mesh data"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        # NOTE: multiline comment """ """ not working here
        default="*.obj;*.stl;" +
                "*.gii;" +
                "*.white;*.pial;*.inflated;*.sphere;*.orig;" +
                "*.blend")

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    sformfile = StringProperty(
        name="sformfile",
        description="",
        default="",
        subtype="FILE_PATH")
    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial smoothing on surfaces",
        default=True)
    colourtype = EnumProperty(
        name="",
        description="Apply this surface colour method",
        default="primary6",
        items=[("none", "none", "none", 1),
               ("golden_angle", "golden_angle", "golden_angle", 2),
               ("primary6", "primary6", "primary6", 3),
               ("random", "random", "random", 4),
               ("directional", "directional", "directional", 5),
               ("pick", "pick", "pick", 6)])
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour for the tract(s)",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.)

    def execute(self, context):

        filenames = [f.name for f in self.files]
        if not filenames:
            filenames = os.listdir(self.directory)

        for f in filenames:
            fpath = os.path.join(self.directory, f)
            info = self.import_surface(context, fpath)
            self.report({'INFO'}, info)

        return {"FINISHED"}

    def draw(self, context):

        layout = self.layout

        row = self.layout.row()
        row.prop(self, "name")

        row = self.layout.row()
        row.prop(self, "beautify")

        row = self.layout.row()
        row.label(text="Colour: ")
        row = self.layout.row()
        row.prop(self, "colourtype")
        row = self.layout.row()
        if self.colourtype == "pick":
            row.prop(self, "colourpicker")
        row = self.layout.row()
        row.prop(self, "transparency")

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def import_surface(self, context, fpath):
        """Import a surface object.

        This imports the surfaces found in the specified file.
        Valid formats include:
        - .gii (via nibabel)
        - .white/.pial/.inflated/.sphere/.orig (FreeSurfer)
        - .obj
        - .stl
        - .blend

        'sformfile' sets matrix_world to affine transformation.

        """

        scn = context.scene
        nb = scn.nb

        ca = [bpy.data.objects,
              bpy.data.meshes,
              bpy.data.materials,
              bpy.data.textures]
        name = nb_ut.check_name(self.name, fpath, ca)

        outcome = "failed"
        ext = os.path.splitext(fpath)[1]

        try:
            fun = "self.read_surfaces_{}".format(ext[1:])
            surfaces = eval('{}(fpath, name, self.sformfile)'.format(fun))

        except NameError:
            reason = "file format '{}' not supported".format(ext)
            info = "import {}: {}".format(outcome, reason)
            return info
        except (IOError, FileNotFoundError):
            reason = "file '{}' not valid".format(fpath)
            info = "import {}: {}".format(outcome, reason)
            return info
        except ImportError:
            reason = "nibabel not found"
            info = "import {}: {}".format(outcome, reason)
            return info

        except:
            reason = "unknown import error"
            info = "import {}: {}".format(outcome, reason)
            raise

        for surf in surfaces:

            ob, affine, sformfile = surf

            ob.matrix_world = affine

            props = {"name": name,
                     "filepath": fpath,
                     "sformfile": sformfile}
            nb_ut.add_item(nb, "surfaces", props)

            nb_ut.move_to_layer(ob, 1)
            scn.layers[1] = True

        scn.objects.active = ob
        ob.select = True
        scn.update()

        info_mat = nb_ma.materialise(ob,
                                     self.colourtype,
                                     self.colourpicker,
                                     self.transparency)
        beaudict = {"iterations": 10,
                    "factor": 0.5,
                    "use_x": True,
                    "use_y": True,
                    "use_z": True}
        info_beau = self.beautification(ob, beaudict)

        info = "import successful"
        if nb.settingprops.verbose:
            info = """{}\nname: '{}'
                        \npath: '{}'
                        \ntransform: {}
                        \n{}\n{}""".format(info, name, fpath, affine,
                                           info_mat, info_beau)

        return info

    def read_surfaces_obj(self, fpath, name, sformfile):
        """Import a surface from a .obj file."""
        # TODO: multiple objects import

        # need split_mode='OFF' for loading scalars onto the correct vertices
        bpy.ops.import_scene.obj(filepath=fpath,
                                 axis_forward='Y', axis_up='Z',
                                 split_mode='OFF')
        ob = bpy.context.selected_objects[0]
        ob.name = name
        affine = nb_ut.read_affine_matrix(sformfile)

        return [(ob, affine, sformfile)]

    def read_surfaces_stl(self, fpath, name, sformfile):
        """Import a surface from a .stl file."""
        # TODO: multiple objects import

        bpy.ops.import_mesh.stl(filepath=fpath,
                                axis_forward='Y', axis_up='Z')
        ob = bpy.context.selected_objects[0]
        ob.name = name
        affine = nb_ut.read_affine_matrix(sformfile)

        return [(ob, affine, sformfile)]

    def read_surfaces_gii(self, fpath, name, sformfile):
        """Import a surface from a .gii file."""
        # TODO: multiple objects import

        scn = bpy.context.scene
        nb = scn.nb

        nib = nb_ut.validate_nibabel('.gifti')

        gio = nib.gifti.giftiio
        img = gio.read(fpath)
        verts = [tuple(vert) for vert in img.darrays[0].data]
        faces = [tuple(face) for face in img.darrays[1].data]
        xform = img.darrays[0].coordsys.xform
        if len(xform) == 16:
            xform = np.reshape(xform, [4, 4])
        affine = Matrix(xform)
        sformfile = fpath

        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        ob = bpy.data.objects.new(name, me)
        scn.objects.link(ob)

        return [(ob, affine, sformfile)]

    def read_surfaces_fs(self, fpath, name, sformfile):
        """Import a surface from a FreeSurfer file."""

        scn = bpy.context.scene
        nb = scn.nb

        nib = nb_ut.validate_nibabel('.gifti')

        fsio = nib.freesurfer.io
        verts, faces = fsio.read_geometry(fpath)
        verts = [tuple(vert) for vert in verts]
        faces = [tuple(face) for face in faces]
        affine = Matrix()

        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.objects.link(ob)

        return [(ob, affine, sformfile)]

    read_surfaces_white = read_surfaces_fs
    read_surfaces_pial = read_surfaces_fs
    read_surfaces_inflated = read_surfaces_fs
    read_surfaces_sphere = read_surfaces_fs
    read_surfaces_orig = read_surfaces_fs

    def read_surfaces_blend(self, fpath, name, sformfile):
        """Import a surface from a .blend file."""

        with bpy.data.libraries.load(fpath) as (data_from, data_to):
            data_to.objects = data_from.objects

        surfaces = []
        for ob in data_to.objects:
            if ob is not None:
                bpy.context.scene.objects.link(ob)
                surfaces.append((ob, ob.matrix_world, sformfile))

        return surfaces

    @staticmethod
    def beautification(ob, argdict={"iterations": 10, "factor": 0.5,
                                    "use_x": True, "use_y": True, "use_z": True}):
        """Smooth the surface mesh."""

        mod = ob.modifiers.new("smooth", type='SMOOTH')
        mod.iterations = argdict["iterations"]
        mod.factor = argdict["factor"]
        mod.use_x = argdict["use_x"]
        mod.use_y = argdict["use_y"]
        mod.use_z = argdict["use_z"]

        info = "smooth: iterations=%3d; factor=%.3f; use_xyz=%s %s %s" \
            % (argdict["iterations"], argdict["factor"],
               argdict["use_x"], argdict["use_y"], argdict["use_z"])

        return info
