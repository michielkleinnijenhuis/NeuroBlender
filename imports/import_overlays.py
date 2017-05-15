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
from random import random
import xml.etree.ElementTree
import pickle

import numpy as np

import bpy
from bpy.types import (Operator,
                       OperatorFileListElement)
from bpy.props import (StringProperty,
                       CollectionProperty,
                       EnumProperty)
from bpy_extras.io_utils import ImportHelper

from .. import (materials as nb_ma,
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
               ("bordergroups", "borders", "List the border overlays", 2)])
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
            if not self.name:
                self.name = os.path.basename(fpath)
            info = self.import_overlay(context, fpath)
            self.report({'INFO'}, info)

        return {"FINISHED"}

    def invoke(self, context, event):

        self.overlaytype = context.scene.nb.overlaytype

        parent = nb_ut.active_nb_object()[0]
        self.parentpath = parent.path_from_id()

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def import_overlay(self, context, fpath):
        """Import an overlay onto a NeuroBlender object."""

        scn = context.scene

        parent = scn.path_resolve(self.parentpath)
        obinfo = nb_ut.get_nb_objectinfo(parent.name)
        parent_ob = bpy.data.objects[parent.name]

        if obinfo['type'] == 'tracts':
            fun = self.import_tracts_scalargroups
        else:
            if self.overlaytype == 'scalargroups':
                fun = self.import_surfaces_scalargroups
            elif self.overlaytype == 'labelgroups':
                fun = self.import_surfaces_labelgroups
            elif self.overlaytype == 'bordergroups':
                fun = self.import_surfaces_bordergroups
        info = fun(context, fpath, parent, parent_ob)

        context.scene.objects.active = parent_ob
        parent_ob.select = True

        return info  # TODO: error handling and info

    def import_tracts_scalargroups(self, context, fpath, parent, ob):
        """Import a scalar overlay onto a tract object."""

        # load the data
        sg_data = self.read_tractscalar(fpath)

        # normalize between 0  and 1
        scalars, sg_range, nsc, nsl = self.normalize_data(sg_data)

        # unique names for the scalargroup, scalars and splines
        def name_check(context, argdict):

            _, _, obp = nb_ut.get_nb_collections(context)
            ovt = ["scalargroups", "labelgroups", "bordergroups"]
            ovc, _, ovp = nb_ut.get_nb_collections(context, obp, ovt)
            oit = ["scalars", "labels", "borders"]
            oic, _, _ = nb_ut.get_nb_collections(context, ovp, oit)

            ca1 = ovc
            all_ca1 = [k for c in ca1 for k in c.keys()]
            def ca1fun(name, argdict):
                names = [name]
                return names

            ca2 = oic
            all_ca2 = [k for c in ca2 for k in c.keys()]
            def ca2fun(name, argdict):
                names = ['{}.vol{:04d}'.format(name, i)
                         for i in range(argdict['nscalars'])]
                return names

            ca3 = [bpy.data.images, bpy.data.materials]
            all_ca3 = [k for c in ca3 for k in c.keys()]
            def ca3fun(name, argdict):
                names = ['{}_spl{:08d}'.format(tpname, j)
                         for tpname in ca2fun(name, argdict)
                         for j in range(argdict['nstreamlines'])]
                return names

            funs = [ca1fun, ca2fun, ca3fun]
            old_names = [all_ca1, all_ca2, all_ca3]
            ca_main = ca1

            return old_names, funs, argdict, ca_main

        argdict = {'nscalars': nsc, 'nstreamlines': nsl}
        old_names, funs, argdict, ca_main = name_check(context, argdict)
        name = nb_ut.compare_names(self.name, old_names, funs,
                                   argdict, ca=ca_main)

        # create the scalargroup
        sgprops = {"name": name,
                   "filepath": fpath,
                   "range": sg_range}
        sg = nb_ut.add_item(parent, "scalargroups", sgprops)

        # implement the (mean) overlay on the object
        ob.data.use_uv_as_generated = True
        diffcol = [0.0, 0.0, 0.0, 1.0]
        group = nb_ma.make_cr_matgroup_tract_sg(diffcol, 0.04, sg)

        # add the scalars/streamlines in the timeseries
        for i, (scalar, scalarrange) in enumerate(scalars):
            tpname = '{}.vol{:04d}'.format(name, i)
            sprops = {"name": tpname,
                      "filepath": fpath,
                      "range": scalarrange}
            nb_scalar = nb_ut.add_item(sg, "scalars", sprops)
            for j, (spl, sl) in enumerate(zip(ob.data.splines, scalar)):
                splname = '{}_spl{:08d}'.format(nb_scalar.name, j)
                img = self.create_overlay_tract_img(splname, sl)
                # it seems crazy to make a material/image per streamline!
                mat = nb_ma.make_cr_mat_tract_sg(splname, img, group)
                ob.data.materials.append(mat)
                spl.material_index = len(ob.data.materials) - 1

        return "done"

    @staticmethod
    def read_tractscalar(fpath):
        """Read a tract scalar overlay file."""

        _, ext = os.path.splitext(fpath)

        if ext in ('.npy'):
            scalar = np.load(fpath)
            scalars = [scalar]

        elif ext in ('.npz'):
            npzfile = np.load(fpath)
            for k in npzfile:
                scalar.append(npzfile[k])
            scalars = [scalar]

        elif ext in ('.asc'):
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

        elif ext in ('.pickle'):
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

        nscalars = len(gdata[0])
        nstreamlines = len(gdata[0][0])

        return zip(gdata, dranges), (gmin, gmax), nscalars, nstreamlines

    @staticmethod
    def create_overlay_tract_img(name, scalar):
        """Create an Nx1 image from a streamline's scalar data."""

        # TODO: use numpy here?
        vals = [[val, val, val, 1.0] for val in scalar]
        pixels = [chan for px in vals for chan in px]

        img = bpy.data.images.new(name, len(scalar), 1)
        img.pixels = pixels
        img.source = 'GENERATED'

        return img

    def import_surfaces_scalargroups(self, context, fpath, parent, ob):
        """Import a timeseries overlay onto a surface object."""

        # load the data
        _, ext = os.path.splitext(fpath)
        if ext in ('.label'):
            # NOTE: fs labelfiles have only data for a vertex subset!
            labels, timeseries = self.read_surflabel(fpath, is_label=False)
        else:
            labels = None
            timeseries = self.read_surfscalar(fpath)
            if len(ob.data.vertices) != len(timeseries[0]):
                return

        # normalize between 0  and 1
        timeseries, timeseriesrange = nb_ut.normalize_data(timeseries)

        # unique names for the scalargroup, scalars, vg, vc, images, mat, tex
        def name_check(context, argdict):

            _, _, obp = nb_ut.get_nb_collections(context)
            ovt = ["scalargroups", "labelgroups", "bordergroups"]
            ovc, _, ovp = nb_ut.get_nb_collections(context, obp, ovt)
            oit = ["scalars", "labels", "borders"]
            oic, _, _ = nb_ut.get_nb_collections(context, ovp, oit)

            ca1 = ovc
            all_ca1 = [k for c in ca1 for k in c.keys()]
            all_ca1 += [bpy.data.materials,
                        bpy.data.textures]
            def ca1fun(name, argdict):
                names = [name]
                return names

            ca2 = oic
            all_ca2 = [k for c in ca2 for k in c.keys()]
            _, surfs, _ = nb_ut.get_nb_collections(context,
                                                   colltypes=["surfaces"])
            vgs = [bpy.data.objects[s.name].vertex_groups for s in surfs]
            vcs = [bpy.data.objects[s.name].data.vertex_colors for s in surfs]
            all_ca2 += vgs + vcs
            all_ca2 += [bpy.data.images]
            def ca2fun(name, argdict):
                names = ['{}.vol{:04d}'.format(name, i)
                         for i in range(argdict['nscalars'])]
                names += '{}.volmean'.format(name)
                return names

            funs = [ca1fun, ca2fun]
            old_names = [all_ca1, all_ca2]
            ca_main = ca1

            return old_names, funs, argdict, ca_main

        argdict = {'nscalars': len(timeseries)}
        old_names, funs, argdict, ca_main = name_check(context, argdict)
        name = nb_ut.compare_names(self.name, old_names, funs,
                                   argdict, ca=ca_main)

        # create the scalargroup
        texdir = "//uvtex_{}".format(name)
        # TODO: choice of texdir, & check if exists
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

            tpname = '{}.vol{:04d}'.format(name, i)
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

        return "done"

    def import_surfaces_labelgroups(self, context, fpath, parent, ob):
        """Import a label overlay onto a surface object.

        TODO: decide what is the best approach:
        reading gifti and converting to freesurfer format (current) or
        have a seperate functions for handling .gii annotations
        (this can be found in commit c3b6d66)
        """

        def create_polygon_layer_int(ob, borderlist):
            """Creates a polygon layer and sets value to borderindex."""
            me = ob.data
            pl = me.polygon_layers_int.new("pl")
            loopsets = [set([vi for vi in poly.vertices])
                        for poly in me.polygons]
            for bi, border in enumerate(borderlist):
                pi = [loopsets.index(set(tri))
                      for tri in border['verts']]
                for poly in me.polygons:
                    if poly.index in pi:
                        # NOTE: this overwrites overlaps
                        pl.data[poly.index].value = bi

        # load the data
        _, ext = os.path.splitext(fpath)
        if ext in ('.label'):  # single label
            # NOTE: fs labelfiles have only data for a vertex subset!
            label, _ = self.read_surflabel(fpath, is_label=True)
            ctab = []
            names = []
            trans = 1
        # TODO: figure out from gifti if it is annot or label
        elif ext in ('.annot', '.gii'):  # multiple labels []
            labels, ctab, names = self.read_surfannot(fpath)
        elif ext in ('.border'):  # no labels
            borderlist = self.read_borders(fpath)
            create_polygon_layer_int(ob, borderlist)
            # (for each border?, will be expensive: do one for every file now)
            names = [border['name'] for border in borderlist]
        else:  # assumed scalar overlay type with integer labels??
            # TODO: test this delegation; is it useful for anything at all?
            self.import_surfaces_scalargroups(fpath, parent, ob)
            return

        # unique names for the labelgroup, labels, vg, vc, images, mat, tex
        def name_check(context, argdict):

            _, _, obp = nb_ut.get_nb_collections(context)
            ovt = ["scalargroups", "labelgroups", "bordergroups"]
            ovc, _, ovp = nb_ut.get_nb_collections(context, obp, ovt)
            oit = ["scalars", "labels", "borders"]
            oic, _, _ = nb_ut.get_nb_collections(context, ovp, oit)

            ca1 = ovc
            all_ca1 = [k for c in ca1 for k in c.keys()]
            def ca1fun(name, argdict):
                names = [name]
                return names

            ca2 = oic
            all_ca2 = [k for c in ca2 for k in c.keys()]
            _, surfs, _ = nb_ut.get_nb_collections(context,
                                                   colltypes=["surfaces"])
            all_ca2 += [bpy.data.materials]
            vgs = [bpy.data.objects[s.name].vertex_groups for s in surfs]
            pls = [bpy.data.objects[s.name].data.polygon_layers_int
                   for s in surfs]
            all_ca2 += vgs + pls
            def ca2fun(name, argdict):
                names = [labelname for labelname in argdict['labelnames']]
                return names

            funs = [ca1fun, ca2fun]
            old_names = [all_ca1, all_ca2]
            ca_main = ca1

            return old_names, funs, argdict, ca_main

        if not names:  # should only happen on importing '.label'
            names = ['{}.{}'.format(self.name, self.name)]
        argdict = {'labelnames': names}
        old_names, funs, argdict, ca_main = name_check(context, argdict)
        name = nb_ut.compare_names(self.name, old_names, funs,
                                   argdict, ca=ca_main)
        # FIXME: a unique list of labelnames should be returned here
#         names = 

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
        for i, lname in enumerate(names):

            if ext in ('.label'):
                values = [label.value for label in labelgroup.labels] or [0]
                value = max(values) + 1
                diffcol = [random() for _ in range(3)] + [trans]
            elif ext in ('.annot', '.gii'):
                label = np.where(labels == i)[0]
                value = ctab[i, 4]
                diffcol = ctab[i, 0:4] / 255
            elif ext in ('.border'):
                label = []
                value = i + 1
                diffcol = list(borderlist[i]['rgb']) + [1.0]

            props = {"name": lname,
                     "value": int(value),
                     "colour": diffcol}
            nb_ut.add_item(labelgroup, "labels", props)

            vgs.append(nb_ma.set_vertex_group(ob, lname, label))
            mats.append(nb_ma.make_cr_mat_basic(lname, diffcol, mix=0.05))

        if ext in ('.border'):
            pl = ob.data.polygon_layers_int["pl"]
            nb_ma.set_materials_to_polygonlayers(ob, pl, mats)
        else:
            nb_ma.set_materials_to_vertexgroups(ob, vgs, mats)

        return "done"

    def import_surfaces_bordergroups(self, context, fpath, parent, ob):
        """Import a label overlay onto a surface object."""

        # load the data
        _, ext = os.path.splitext(fpath)
        if ext in ('.border'):
            borderlist = self.read_borders(fpath)
        else:
            print("Only Connectome Workbench .border files supported.")
            return

        # unique names for the bordergroup, borders, mat
        def name_check(context, argdict):

            _, _, obp = nb_ut.get_nb_collections(context)
            ovt = ["scalargroups", "labelgroups", "bordergroups"]
            ovc, _, ovp = nb_ut.get_nb_collections(context, obp, ovt)
            oit = ["scalars", "labels", "borders"]
            oic, _, _ = nb_ut.get_nb_collections(context, ovp, oit)

            ca1 = ovc
            all_ca1 = [k for c in ca1 for k in c.keys()]
            def ca1fun(name, argdict):
                names = [name]
                return names

            ca2 = oic
            all_ca2 = [k for c in ca2 for k in c.keys()]
            all_ca2 += [bpy.data.objects,
                        bpy.data.curves,
                        bpy.data.materials]
            def ca2fun(name, argdict):
                names = argdict['bordernames']
                return names

            funs = [ca1fun, ca2fun]
            old_names = [all_ca1, all_ca2]
            ca_main = ca1

            return old_names, funs, argdict, ca_main

        names = [border['name'] for border in borderlist]
        argdict = {'bordernames': names}
        old_names, funs, argdict, ca_main = name_check(context, argdict)
        name = nb_ut.compare_names(self.name, old_names, funs,
                                   argdict, ca=ca_main)
        # FIXME: a unique list of bordernames should be returned here
#         names = 

        # create the bordergroup
        props = {"name": name,
                 "filepath": fpath}
        bordergroup = nb_ut.add_item(parent, "bordergroups", props)

        # create an empty to hold the border objects
        bordergroup_ob = bpy.data.objects.new(bordergroup.name,
                                              object_data=None)
        context.scene.objects.link(bordergroup_ob)
        bordergroup_ob.parent = ob

        # add the borders in the bordergroup
        for border, bname in zip(borderlist, names):

            diffcol = list(border['rgb']) + [1.0]
            mat = nb_ma.make_cr_mat_basic(border['name'], diffcol, mix=0.05)

            props = {"name": bname,
                     "group": bordergroup.name,
                     "colour": diffcol}
            nb_ut.add_item(bordergroup, "borders", props)

            # create the border object
            curve = bpy.data.curves.new(name=bname, type='CURVE')
            curve.dimensions = '3D'
            curveob = bpy.data.objects.new(bname, curve)
            context.scene.objects.link(curveob)

            # create the curve
            clist = [ob.data.vertices[vi].co[:3]
                     for vi in border['verts'][:, 0]]
            nb_ut.make_polyline(curve, clist, use_cyclic_u=True)

            # bevel the curve
            fill_mode = 'FULL'
            bevel_depth = 0.5
            bevel_resolution = 10
            curveob.data.fill_mode = fill_mode
            curveob.data.bevel_depth = bevel_depth
            curveob.data.bevel_resolution = bevel_resolution
            curveob.parent = bordergroup_ob

            # smooth the curve
            iterations = 10
            factor = 0.5
            mod = curveob.modifiers.new("smooth", type='SMOOTH')
            mod.iterations = iterations
            mod.factor = factor

            nb_ma.set_materials(curveob.data, mat)

        return "done"

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
                labtab = img.labeltable
                labels, ctab, names = gii_to_freesurfer_annot(labels, labtab)
            elif fpath.endswith('.dlabel.nii'):
                pass  # TODO # CIFTI not yet working properly: in nibabel?
            return labels, ctab, names
        else:
            print('nibabel required for reading .annot files')

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
