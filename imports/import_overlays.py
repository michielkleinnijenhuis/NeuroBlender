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
from random import random
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
    bl_label = "Import overlays"
    bl_description = "Import overlays onto a NeuroBlender tract/surface"
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

        if not self.parentpath:
            parent = nb_ut.active_nb_object()[0]
            self.parentpath = parent.path_from_id()

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

        parent = eval(self.parentpath)

        obinfo = nb_ut.get_nb_objectinfo(parent.name)

        parent_ob = bpy.data.objects[parent.name]

        fun = eval("self.import_{}_{}".format(obinfo['type'],
                                              self.overlaytype))
        fun(fpath, parent, parent_ob, name=name)

        context.scene.objects.active = parent_ob
        parent_ob.select = True

        return "done"  # TODO: error handling and info

    def import_tracts_scalargroups(self, fpath, parent, ob, name=""):
        """Import a scalar overlay onto a tract object."""

        sg_data = self.read_tractscalar(fpath)

        scalars, sg_range = self.normalize_data(sg_data)

        # TODO: check against all other scalargroups etc
        ca = [parent.scalargroups]
        name = nb_ut.check_name(name, fpath, ca)

        sgprops = {"name": name,
                   "filepath": fpath,
                   "range": sg_range}
        sg = nb_ut.add_item(parent, "scalargroups", sgprops)

        ob.data.use_uv_as_generated = True
        diffcol = [0.0, 0.0, 0.0, 1.0]
        group = nb_ma.make_cr_matgroup_tract_sg(diffcol, 0.04, sg)

        for j, (scalar, scalarrange) in enumerate(scalars):

            # TODO: check against all other scalargroups etc
            ca = [sg.scalars for sg in parent.scalargroups]
            tpname = "%s.vol%04d" % (name, j)
            scalarname = nb_ut.check_name(tpname, fpath, ca)

            sprops = {"name": scalarname,
                      "filepath": fpath,
                      "range": scalarrange}
            nb_scalar = nb_ut.add_item(sg, "scalars", sprops)

            for i, (spl, sl) in enumerate(zip(ob.data.splines, scalar)):

                # TODO: implement name check that checks for the prefix 'name'
                splname = nb_scalar.name + '_spl' + str(i).zfill(8)
                ca = [bpy.data.images,
                      bpy.data.materials]
                splname = nb_ut.check_name(splname, fpath, ca, maxlen=52)

                img = self.create_overlay_tract_img(splname, sl)

                # it seems crazy to make a material/image per streamline!
                mat = nb_ma.make_cr_mat_tract_sg(splname, img, group)
                ob.data.materials.append(mat)
                spl.material_index = len(ob.data.materials) - 1

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
    def normalize_data(nn_group):
        """"Normalize the data in the scalargroup between 0 and 1."""
        gmin = float('Inf')
        gmax = -float('Inf')
        dranges = []
        for nn_data in nn_group:
            dmin = float('Inf')
            dmax = -float('Inf')
            for streamline in nn_data:
                dmin = min(dmin, min(streamline))
                dmax = max(dmax, max(streamline))
            dranges.append([dmin, dmax])
            gmin = min(gmin, dmin)
            gmax = max(gmax, dmax)
        gdata = [[(np.array(streamline) - gmin) / (gmax - gmin)
                  for streamline in nn_data]
                 for nn_data in nn_group]

        return zip(gdata, dranges), (gmin, gmax)

    @staticmethod
    def create_overlay_tract_img(name, scalar):
        """Create an Nx1 image from a streamline's scalar data."""

        vals = [[val, val, val, 1.0] for val in scalar]
        img = bpy.data.images.new(name, len(scalar), 1)
        pixels = [chan for px in vals for chan in px]
        img.pixels = pixels
        img.source = 'GENERATED'

        return img

    def import_surfaces_scalargroups(self, fpath, parent, ob, name=""):
        """Import a timeseries overlay onto a surface object."""

        # load the data
        if fpath.endswith('.label'):
            # NOTE: fs labelfiles have only data for a vertex subset!
            labels, timeseries = self.read_surflabel(fpath, is_label=False)
        else:
            labels = None
            timeseries = self.read_surfscalar(fpath)

        # check validity
        if ((not list(labels)) and
                (len(ob.data.vertices) != len(timeseries[0]))):
            return

        # normalize between 0  and 1
        timeseries, timeseriesrange = nb_ut.normalize_data(timeseries)

        # unique name for the overlay
        ca = [parent.scalargroups,
              ob.vertex_groups,
              bpy.data.materials]  # TODO: all other scalargroups, scalars etc
        name = nb_ut.check_name(name, fpath, ca)

        # create the scalargroup
        texdir = "//uvtex_{}".format(name)  # TODO: choice of texdir, & check if exists
        props = {"name": name,
                 "filepath": fpath,
                 "range": timeseriesrange,
                 "texdir": texdir}
        scalargroup = nb_ut.add_item(parent, "scalargroups", props)
        if timeseries.shape[0] == 1:
            scalargroup.icon = "FORCE_CHARGE"

        # implement the (mean) overlay on the object
        nb_ma.set_vertex_group(ob, "{}.volmean".format(name),
                               label=labels,
                               scalars=np.mean(timeseries, axis=0))
        mat = nb_ma.make_cr_mat_surface_sg(scalargroup)
        nb_ma.set_materials(ob.data, mat)

        # add the scalars in the timeseries
        for i, scalars in enumerate(timeseries):

            tpname = "%s.vol%04d" % (name, i)
            props = {"name": tpname,
                     "filepath": fpath,
                     "range": timeseriesrange}
            nb_ut.add_item(scalargroup, "scalars", props)

            nb_ma.set_vertex_group(ob, tpname,
                                   label=labels,
                                   scalars=scalars)
            # TODO: timeseries could be baked here (speedup needed)

        # load the textures
#         abstexdir = bpy.path.abspath(texdir)
#         if os.path.isdir(abstexdir):
#             nfiles = len(glob(os.path.join(abstexdir, '*.png')))
#             if nfiles == len(scalargroup.scalars):
#                 nb_ma.load_surface_textures(name, abstexdir,
#                                             len(scalargroup.scalars))

    def import_surfaces_labelgroups(self, fpath, parent, ob, name=""):
        """Import a label overlay onto a surface object.

        TODO: decide what is the best approach:
        reading gifti and converting to freesurfer format (current) or
        have a seperate functions for handling .gii annotations
        (this can be found in commit c3b6d66)
        """

        # load the data
        if fpath.endswith('.label'):  # single label
            # NOTE: fs labelfiles have only data for a vertex subset!
            label, _ = self.read_surflabel(fpath, is_label=True)
            ctab = []
            names = []
            trans = 1
        # TODO: figure out from gifti if it is annot or label
        elif (fpath.endswith('.annot') |
              fpath.endswith('.gii')):  # multiple labels []
            labels, ctab, names = self.read_surfannot(fpath)
        elif fpath.endswith('.border'):
            pass  # TODO
        else:  # assumed scalar overlay type with integer labels??
            # TODO: test this delegation; is it useful for anything at all?
            self.import_surfaces_scalargroups(fpath, parent, ob, name)
            return

        # check validity
        # TODO

        # unique names for the labelgroup and labels
        ca = [parent.labelgroups,
              ob.vertex_groups,
              bpy.data.materials]  # TODO: all other labelgroups, labels etc
        name = nb_ut.check_name(name, fpath, ca)
        if not names:
            names = ['{}.{}'.format(name, name)]
        labelnames = [nb_ut.check_name(labelname, "", ca)
                      for labelname in names]

        # create the labelgroup
        # TODO: choice of texdir, & check if exists
#         texdir = "//uvtex_{}".format(name)
        props = {"name": name,
                 "filepath": fpath}
        labelgroup = nb_ut.add_item(parent, "labelgroups", props)

        # implement the (mean) overlay on the object
        # TODO: find out if this is necessary
#         nb_ma.set_vertex_group(ob, name)
#         mat = nb_ma.make_cr_mat_surface_sg(labelgroup)
#         nb_ma.set_materials(ob.data, mat)

        # add the labels in the labelgroup
        vgs = []
        mats = []
        for i, labelname in enumerate(labelnames):

            if list(ctab):  # from annot-like
                label = np.where(labels == i)[0]
                value = ctab[i, 4]
                diffcol = ctab[i, 0:4] / 255
            else:  # from label-like
                values = [label.value for label in labelgroup.labels] or [0]
                value = max(values) + 1
                diffcol = [random() for _ in range(3)] + [trans]

            props = {"name": labelname,
                     "value": int(value),
                     "colour": diffcol}
            nb_ut.add_item(labelgroup, "labels", props)

            vgs.append(nb_ma.set_vertex_group(ob, labelname, label))
            mats.append(nb_ma.make_cr_mat_basic(labelname, diffcol, mix=0.05))

        nb_ma.set_materials_to_vertexgroups(ob, vgs, mats)

    def import_surfaces_bordergroups(self, fpath, parent, parent_ob, name=""):
        """Import a label overlay onto a surface object."""

        if fpath.endswith('.border'):
            nb_ma.create_border_curves(parent_ob, fpath, name=name)
        else:
            print("Only Connectome Workbench .border files supported.")

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
            if nb.settingprops.nibabel_valid:
                gio = nib.gifti.giftiio
                img = gio.read(fpath)
                scalars = []
                for darray in img.darrays:
                    scalars.append(darray.data)
                scalars = np.array(scalars)
        elif fpath.endswith('dscalar.nii'):
            # CIFTI not yet working properly: in nibabel?
            nib = nb_ut.validate_nibabel('dscalar.nii')
            if nb.settingprops.nibabel_valid:
                gio = nib.gifti.giftiio
                nii = gio.read(fpath)
                scalars = np.squeeze(nii.get_data())
        else:  # I will try to read it as a freesurfer binary
            nib = nb_ut.validate_nibabel('')
            if nb.settingprops.nibabel_valid:
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
            if nb.settingprops.nibabel_valid:
                fsio = nib.freesurfer.io
                label, scalars = fsio.read_label(fpath, read_scalars=True)
            else:
                labeltxt = np.loadtxt(fpath, skiprows=2)
                label = labeltxt[:, 0]
                scalars = labeltxt[:, 4]

            if is_label:
                scalars = None  # TODO: handle file where no scalars present

        return label, np.atleast_2d(scalars)

    @staticmethod
    def read_surfannot(fpath):
        """Read a surface annotation file."""

        scn = bpy.context.scene
        nb = scn.nb

        nib = nb_ut.validate_nibabel('.annot')
        if nb.settingprops.nibabel_valid:
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
        if nb.settingprops.nibabel_valid:
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
        if nb.settingprops.nibabel_valid:
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
