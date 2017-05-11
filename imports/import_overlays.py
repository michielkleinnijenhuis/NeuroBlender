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


"""The NeuroBlender imports module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements importing data into NeuroBlender.
"""


import os
from glob import glob
import numpy as np
from mathutils import Vector, Matrix
from random import sample
import xml.etree.ElementTree
import pickle

import bpy
from bpy.types import (Operator,
                       OperatorFileListElement)
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       IntProperty)
from bpy_extras.io_utils import ImportHelper

from .. import (materials as nb_ma,
                renderpresets as nb_rp,
                utils as nb_ut)


class ImportOverlays(Operator, ImportHelper):
    bl_idname = "nb.import_overlays"
    bl_label = "Import bordergroup overlay"
    bl_description = "Import bordergroup overlay to curves"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="")
    overlaytype = EnumProperty(
        name="overlay type",
        description="switch between overlay types",
        items=[("scalargroups", "scalars", "List the scalar overlays", 0),
               ("labelgroups", "labels", "List the label overlays", 1),
               ("bordergroups", "borders",  "List the border overlays", 2)])
    texdir = StringProperty(
        name="Texture directory",
        description="Directory with textures for this scalargroup",
        default="",
        subtype="DIR_PATH")  # TODO

    def execute(self, context):

        filenames = [f.name for f in self.files]
        if not filenames:
            filenames = os.listdir(self.directory)

        for f in filenames:
            fpath = os.path.join(self.directory, f)
            info = self.import_overlay(context, fpath)
            self.report({'INFO'}, info)


        return {"FINISHED"}

    def invoke(self, context, event):

        self.overlaytype = context.scene.nb.overlaytype

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def import_overlay(self, context, fpath):
        """Import an overlay onto a NeuroBlender object."""

        scn = context.scene
        nb = scn.nb

        # TODO: is this sufficient?
        ca = [bpy.data.objects,
              bpy.data.meshes,
              bpy.data.materials,
              bpy.data.textures]
        name = nb_ut.check_name(self.name, fpath, ca)

        try:
            parent = eval(self.parentpath)
        except (SyntaxError, NameError):
            parent = nb_ut.active_nb_object()[0]

        obinfo = nb_ut.get_nb_objectinfo(parent.name)

        parent_ob = bpy.data.objects[parent.name]

        fun = eval("self.import_{}_{}".format(obinfo['type'],
                                              self.overlaytype))
        fun(fpath, parent_ob, name=name)

        context.scene.objects.active = parent_ob
        parent_ob.select = True

    def import_tracts_scalargroups(self, fpath, parent_ob, name=""):
        """Import a scalar overlay onto a tract object."""

        nb_ma.create_vc_overlay_tract(parent_ob, fpath, name=name)

    def import_surfaces_scalargroups(self, fpath, parent_ob, name=""):
        """Import a timeseries overlay onto a surface object."""

        nb_ma.create_vc_overlay(parent_ob, fpath, name=name)

    def import_surfaces_scalars(self, fpath, parent_ob, name=""):
        """Import a scalar overlay onto a surface object."""  # deprecated?

        if fpath.endswith('.label'):  # but not treated as a label
            nb_ma.create_vg_overlay(parent_ob, fpath, name=name, is_label=False)
        else:  # assumed scalar overlay
            nb_ma.create_vc_overlay(parent_ob, fpath, name=name)

    def import_surfaces_labelgroups(self, fpath, parent_ob, name=""):
        """Import a label overlay onto a surface object."""

        if fpath.endswith('.label'):
            nb_ma.create_vg_overlay(parent_ob, fpath, name=name, is_label=True)
        elif (fpath.endswith('.annot') |
              fpath.endswith('.gii') |
              fpath.endswith('.border')):
            nb_ma.create_vg_annot(parent_ob, fpath, name=name)
            # TODO: figure out from gifti if it is annot or label
        else:  # assumed scalar overlay type with integer labels??
            nb_ma.create_vc_overlay(parent_ob, fpath, name=name)

    def import_surfaces_bordergroups(self, fpath, parent_ob, name=""):
        """Import a label overlay onto a surface object."""

        if fpath.endswith('.border'):
            nb_ma.create_border_curves(parent_ob, fpath, name=name)
        else:
            print("Only Connectome Workbench .border files supported.")

    @staticmethod
    def read_tractscalar(fpath):
        """Read a tract scalar overlay file."""

        if fpath.endswith('.npy'):
            scalar = np.load(fpath)
            scalars = [scalar]
        elif fpath.endswith('.npz'):
            npzfile = np.load(fpath)
            for k in npzfile:
                scalar.append(npzfile[k])
            scalars = [scalar]
        elif fpath.endswith('.asc'):
            # mrtrix convention assumed (1 streamline per line)
            scalar = []
            with open(fpath) as f:
                for line in f:
                    tokens = line.rstrip("\n").split(' ')
                    points = []
                    for token in tokens:
                        if token:
                            points.append(float(token))
                    scalar.append(points)
            scalars = [scalar]
        if fpath.endswith('.pickle'):
            with open(fpath, 'rb') as f:
                scalars = pickle.load(f)

        return scalars

    @staticmethod
    def read_surfscalar(fpath):
        """Read a surface scalar overlay file."""

        scn = bpy.context.scene
        nb = scn.nb

        # TODO: handle what happens on importing multiple objects
        # TODO: read more formats: e.g. .dpv, .dpf, ...
        if fpath.endswith('.npy'):
            scalars = np.load(fpath)
        elif fpath.endswith('.npz'):
            npzfile = np.load(fpath)
            for k in npzfile:
                scalars.append(npzfile[k])
        elif fpath.endswith('.gii'):
            nib = nb_ut.validate_nibabel('.gii')
            if nb.nibabel_valid:
                gio = nib.gifti.giftiio
                img = gio.read(fpath)
                scalars = []
                for darray in img.darrays:
                    scalars.append(darray.data)
                scalars = np.array(scalars)
        elif fpath.endswith('dscalar.nii'):
            # CIFTI not yet working properly: in nibabel?
            nib = nb_ut.validate_nibabel('dscalar.nii')
            if nb.nibabel_valid:
                gio = nib.gifti.giftiio
                nii = gio.read(fpath)
                scalars = np.squeeze(nii.get_data())
        else:  # I will try to read it as a freesurfer binary
            nib = nb_ut.validate_nibabel('')
            if nb.nibabel_valid:
                fsio = nib.freesurfer.io
                scalars = fsio.read_morph_data(fpath)
            else:
                with open(fpath, "rb") as f:
                    f.seek(15, os.SEEK_SET)
                    scalars = np.fromfile(f, dtype='>f4')

        return np.atleast_2d(scalars)

    @staticmethod
    def read_surflabel(fpath, is_label=False):
        """Read a surface label overlay file."""

        scn = bpy.context.scene
        nb = scn.nb

        if fpath.endswith('.label'):
            nib = nb_ut.validate_nibabel('.label')
            if nb.nibabel_valid:
                fsio = nib.freesurfer.io
                label, scalars = fsio.read_label(fpath, read_scalars=True)
            else:
                labeltxt = np.loadtxt(fpath, skiprows=2)
                label = labeltxt[:, 0]
                scalars = labeltxt[:, 4]

            if is_label:
                scalars = None  # TODO: handle file where no scalars present

        return label, scalars

    @staticmethod
    def read_surfannot(fpath):
        """Read a surface annotation file."""

        scn = bpy.context.scene
        nb = scn.nb

        nib = nb_ut.validate_nibabel('.annot')
        if nb.nibabel_valid:
            if fpath.endswith(".annot"):
                fsio = nib.freesurfer.io
                labels, ctab, bnames = fsio.read_annot(fpath, orig_ids=False)
                names = [name.decode('utf-8') for name in bnames]
            elif fpath.endswith(".gii"):
                gio = nib.gifti.giftiio
                img = gio.read(fpath)
                img.labeltable.get_labels_as_dict()
                labels = img.darrays[0].data
                labeltable = img.labeltable
                labels, ctab, names = gii_to_freesurfer_annot(labels, labeltable)
            elif fpath.endswith('.dlabel.nii'):
                pass  # TODO # CIFTI not yet working properly: in nibabel?
            return labels, ctab, names
        else:
            print('nibabel required for reading .annot files')

    @staticmethod
    def gii_to_freesurfer_annot(labels, labeltable):
        """Convert gifti annotation file to nibabel freesurfer format."""

        names = [name for _, name in labeltable.labels_as_dict.items()]
        ctab = [np.append((np.array(l.rgba)*255).astype(int), l.key)
                for l in labeltable.labels]
        ctab = np.array(ctab)
        # TODO: check scikit-image relabel_sequential code
        # TODO: check if relabeling is necessary
        newlabels = np.zeros_like(labels)
        i = 1
        for _, l in enumerate(labeltable.labels, 1):
            labelmask = np.where(labels == l.key)[0]
            newlabels[labelmask] = i
            if (labelmask != 0).sum():
                i += 1

        return labels, ctab, names

    @staticmethod
    def read_surfannot_freesurfer(fpath):
        """Read a .annot surface annotation file."""

        scn = bpy.context.scene
        nb = scn.nb

        nib = nb_ut.validate_nibabel('.annot')
        if nb.nibabel_valid:
            fsio = nib.freesurfer.io
            labels, ctab, bnames = fsio.read_annot(fpath, orig_ids=False)
            names = [name.decode('utf-8') for name in bnames]
            return labels, ctab, names
        else:
            print('nibabel required for reading .annot files')

    @staticmethod
    def read_surfannot_gifti(fpath):
        """Read a .gii surface annotation file."""

        scn = bpy.context.scene
        nb = scn.nb

        nib = nb_ut.validate_nibabel('.annot')
        if nb.nibabel_valid:
            gio = nib.gifti.giftiio
            img = gio.read(fpath)
            img.labeltable.get_labels_as_dict()
            labels = img.darrays[0].data
            labeltable = img.labeltable
            return labels, labeltable
        else:
            print('nibabel required for reading .annot files')

    @staticmethod
    def read_borders(fpath):
        """Read a Connectome Workbench .border file."""

        root = xml.etree.ElementTree.parse(fpath).getroot()

    #     v = root.get('Version')
    #     s = root.get('Structure')
    #     nv = root.get('SurfaceNumberOfVertices')
    #     md = root.find('MetaData')

        borderlist = []
        borders = root.find('Class')
        for border in borders:
            borderdict = {}
            borderdict['name'] = border.get('Name')
            borderdict['rgb'] = (float(border.get('Red')),
                                 float(border.get('Green')),
                                 float(border.get('Blue')))
            bp = border.find('BorderPart')
            borderdict['closed'] = bp.get('Closed')
            verts = [[int(c) for c in v.split()]
                     for v in bp.find('Vertices').text.split("\n") if v]
            borderdict['verts'] = np.array(verts)
    #         weights = [[float(c) for c in v.split()]
    #                    for v in bp.find('Weights').text.split("\n") if v]
    #         borderdict['weights'] = np.array(weights)
            borderlist.append(borderdict)

        return borderlist
