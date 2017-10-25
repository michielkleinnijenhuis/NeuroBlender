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


"""The NeuroBlender imports (tracts) module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements importing tracts into NeuroBlender.
"""


import os
import sys
import importlib
import random
from mathutils import Vector, Matrix
from glob import glob

import numpy as np

import bpy
import bmesh
from bpy.types import PropertyGroup as pg
from bpy.types import (Operator,
                       OperatorFileListElement)
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       IntProperty,
                       FloatVectorProperty,
                       FloatProperty)
from bpy_extras.io_utils import ImportHelper

from .. import (materials as nb_ma,
                utils as nb_ut)


class NB_OT_import_tracts(Operator, ImportHelper):
    bl_idname = "nb.import_tracts"
    bl_label = "Import tracts"
    bl_description = "Import tracts as curves"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        # NOTE: multiline comment """ """ not working here
        default="*.vtk;" +
                "*.bfloat;*.Bfloat;*.bdouble;*.Bdouble;" +
                "*.tck;*.trk;" +
                "*.npy;*.npz;*.dpy")

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
    interpolate_streamlines = FloatProperty(
        name="Interpolate streamlines",
        description="Interpolate the individual streamlines",
        default=1.,
        min=0.,
        max=1.)
    weed_tract = FloatProperty(
        name="Tract weeding",
        description="Retain a random selection of streamlines",
        default=1.,
        min=0.,
        max=1.)

    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial bevel on streamlines",
        default=True)

    radius = FloatProperty(
        name="Tract radius",
        description="The radius of the streamlines",
        default=1.,
        min=0.)
    radius_variation = BoolProperty(
        name="Tract radius variation",
        description="random variation on the streamline radius",
        default=False)
    radius_factor_soma = FloatProperty(
        name="Soma radius factor",
        description="Multiplication factor for soma radius",
        default=0.5,
        min=0.)

    colourtype = EnumProperty(
        name="",
        description="Apply this tract colour method",
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

    use_quickbundles = BoolProperty(
        name="QuickBundles",
        description="Use QuickBundles to segment the tract",
        default=False)

    qb_points = IntProperty(
        name="QuickBundles points",
        description="Resample the streamlines to N points",
        default=50,
        min=2)

    qb_threshold = FloatProperty(
        name="QuickBundles threshold",
        description="Set the threshold for QuickBundles",
        default=30.,
        min=0.)

    qb_centroids = BoolProperty(
        name="QuickBundles centroids",
        description="Create a QuickBundles centroids object",
        default=False)

    def execute(self, context):

        filenames = [f.name for f in self.files]
        if not filenames:
            filenames = os.listdir(self.directory)

        for f in filenames:
            fpath = os.path.join(self.directory, f)
            streamlines = self.read_streamlines_from_file(fpath)
            # TODO: handle cases where transform info is included in tractfile
            affine = nb_ut.read_affine_matrix(self.sformfile)
            self.import_tract(
                context, streamlines, fpath, affine, self.sformfile,
                weed_tract=self.weed_tract,
                interpolate_streamlines=self.interpolate_streamlines,
                use_quickbundles=self.use_quickbundles,
                )

        return {"FINISHED"}

    def draw(self, context):

        layout = self.layout

        row = layout.row()
        row.prop(self, "name")
        row = layout.row()
        row.prop(self, "interpolate_streamlines")
        row = layout.row()
        row.prop(self, "weed_tract")

        row = layout.row()
        row.separator()
        row = layout.row()
        row.prop(self, "beautify")
        row = layout.row()
        row.label(text="Colour: ")
        row = layout.row()
        row.prop(self, "colourtype")
        row = layout.row()
        if self.colourtype == "pick":
            row.prop(self, "colourpicker")
        row = layout.row()
        row.prop(self, "transparency")

        # TODO: only show when dipy detected
        # TODO: draw qb operator instead?
        row = layout.row()
        row.prop(self, "use_quickbundles")
        if self.use_quickbundles:
            row = layout.row()
            row.prop(self, "qb_points")
            row.prop(self, "qb_threshold")
            row = layout.row()
            row.prop(self, "qb_centroids")

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def import_tract(self, context, streamlines,
                     fpath='',
                     affine=Matrix(),
                     sformfile='',
                     weed_tract=1.,
                     interpolate_streamlines=1.,
                     use_quickbundles=False):
        """Import a tract object.

        This imports the streamlines found in the specified file and
        joins the individual streamlines into one 'Curve' object.
        Valid formats include:
        - .bfloat/.Bfloat/.bdouble/.Bdouble (Camino)
          http://camino.cs.ucl.ac.uk/index.php?n=Main.Fileformats
        - .tck (MRtrix)
          http://jdtournier.github.io/mrtrix-0.2/appendix/mrtrix.html
        - .vtk (vtk polydata (ASCII); from MRtrix's 'tracks2vtk' command)
          http://www.vtk.org/wp-content/uploads/2015/04/file-formats.pdf
        - .trk (TrackVis; via nibabel)
        - .dpy (dipy; via dipy)
        - .npy (2d numpy arrays [Npointsx3]; single streamline per file)
        - .npz (zipped archive of Nstreamlines .npy files)
          http://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.savez.html

        'weed_tract' thins tracts by randomly selecting streamlines.
        'interpolate_streamlines' keeps every nth point of the streamlines
        (int(1/interpolate_streamlines)).
        'sformfile' sets matrix_world to affine transformation.

        """

        scn = context.scene
        nb = scn.nb

        # TODO: check names in groups
        ca = [bpy.data.objects,
              bpy.data.meshes,
              bpy.data.materials,
              bpy.data.textures]
        name = nb_ut.check_name(self.name, fpath, ca)

        # create object
        ob = self.create_tract_object(context, name)
        nb_ob, info = self.tract_to_nb(context, ob, fpath, sformfile,
                                       weed_tract, interpolate_streamlines)

        matgroup = [(-1, name)]
        if os.path.splitext(fpath)[1][1:] == 'swc':
            matgroup += [(1, '{}.soma'.format(name)),
                         (2, '{}.axon'.format(name)),
                         (3, '{}.basal_dendrite'.format(name)),
                         (4, '{}.apical_dendrite'.format(name))]
            for i, matname in reversed(matgroup):
                nb_ma.materialise(ob, matname=matname, idx=i)
            self.labelgroup_to_nb(name, nb_ob, matgroup[1:])
        elif not use_quickbundles:
            for i, matname in reversed(matgroup):
                nb_ma.materialise(ob, matname=matname, idx=i)

        # add streamlines
        self.add_streamlines(
            ob, streamlines,
            weed_tract=weed_tract,
            interpolate_streamlines=interpolate_streamlines,
            )

        if use_quickbundles:
            bpy.ops.nb.create_labelgroup(
                data_path=nb_ob.path_from_id(),
                qb_points=self.qb_points,
                qb_threshold=self.qb_threshold,
                qb_centroids=self.qb_centroids,
                )

        # beautify
        if self.beautify:
            self.beautification(ob)

        ob.matrix_world = affine

        self.report({'INFO'}, info)

        return nb_ob

    @staticmethod
    def tract_to_nb(context, ob, fpath='', sformfile='',
                    weed_tract=1., interpolate_streamlines=1.):
        """Add a tract object to NeuroBlender."""

        scn = context.scene
        nb = scn.nb

        props = {
            "name": ob.name,
            "filepath": fpath,
            "sformfile": sformfile,
            "nstreamlines": len(ob.data.splines),
            "tract_weeded": weed_tract,
            "streamlines_interpolated": interpolate_streamlines
            }
        nb_ob = nb_ut.add_item(nb, "tracts", props)

        nb_ut.move_to_layer(ob, 0)
        scn.layers[0] = True

        group = bpy.data.groups.get("tracts") or \
            bpy.data.groups.new("tracts")
        group.objects.link(ob)

        scn.objects.active = ob
        ob.select = True
        scn.update()

        info_mat = ''
        info = "Tract import successful"
        if nb.settingprops.verbose:
            infostring = "{}\n"
            infostring += "name: '{}'\n"
            infostring += "path: '{}'\n"
            infostring += "transform: \n"
            infostring += "{}\n"
            infostring += "decimate: "
            infostring += "weeding: {}; "
            infostring += "interpolation: {};\n"
            infostring += "{}\n"
            infostring += "{}"
            info = infostring.format(info, ob.name, fpath,
                                     ob.matrix_world,
                                     weed_tract,
                                     interpolate_streamlines,
                                     info_mat)

        return nb_ob, info

    @staticmethod
    def labelgroup_to_nb(name, parent, matgroup):
        """Add a labelgroup to NeuroBlender."""

        # create the group
        props = {"name": name,
                 "filepath": '',
                 "prefix_parentname": True,
                 'spline_postfix': 'cluster{:05d}'}
        group = nb_ut.add_item(parent, "labelgroups", props)

        # add the items
        for i, matname in matgroup:

            value = i
            mat = bpy.data.materials[matname]
            diffcol = mat.node_tree.nodes["RGB"].outputs[0].default_value

            props = {"name": matname,
                     "value": int(value),
                     "colour": diffcol}
            nb_ut.add_item(group, "labels", props)

        return group

    def read_streamlines_from_file(self, fpath):
        """Read a set of streamlines from file."""

        outcome = "failed"
        ext = os.path.splitext(fpath)[1]

        try:
            fun = "self.read_streamlines_{}".format(ext[1:])
            streamlines = eval('{}(fpath)'.format(fun))

        except NameError:
            reason = "file format '{}' not supported".format(ext)
            info = "import {}: {}".format(outcome, reason)
            return info
        except (IOError, FileNotFoundError):
            reason = "file '{}' not valid".format(fpath)
            info = "import {}: {}".format(outcome, reason)
            return info

        except:
            reason = "unknown import error"
            info = "import {}: {}".format(outcome, reason)
            raise
        else:
            info = "imported {} streamlines from {}".format(len(streamlines), fpath)

        self.report({'INFO'}, info)

        return streamlines

    def read_streamlines_npy(self, fpath):
        """Read a [Npointsx3] streamline from a *.npy file."""

        streamline = np.load(fpath)

        return [streamline]

    def read_streamlines_npz(self, fpath):
        """Return all streamlines from a *.npz file.

        e.g. from
        'np.savez_compressed(outfile, streamlines0=streamlines0, ..=..)'
        NOTE: This doesn't work for .npz pickled in Python 2.x,!! ==>
        Unicode unpickling incompatibility
        """

        # TODO: proper checks and error handling
        # TODO: multitract npz
        streamlines = []
        npzfile = np.load(fpath)
        k = npzfile.files[0]
        if len(npzfile.files) == 0:
            print('No files in archive.')
        elif len(npzfile.files) == 1:  # single tract / streamline
            if len(npzfile[k][0][0]) == 3:  # k contains a list of Nx3 arrays
                streamlines = npzfile[k]
            else:  # k contains a single Nx3 array
                streamlines.append(npzfile[k])
        elif len(npzfile.files) > 1:  # multiple tracts / streamlines
            if len(npzfile[k][0][0]) == 3:  # k contains a list of Nx3 arrays
                print('multi-tract npz not supported yet.')
            else:  # each k contains a single Nx3 array
                for k in npzfile:
                    streamlines.append(npzfile[k])

        return streamlines

    def read_streamlines_dpy(self, fpath):
        """Return all streamlines in a dipy .dpy tract file (uses dipy)."""

        if nb_ut.validate_dipy('.trk'):
            dpr = Dpy(fpath, 'r')  # FIXME
            streamlines = dpr.read_tracks()
            dpr.close()

        return streamlines

    def read_streamlines_trk(self, fpath):
        """Return all streamlines in a Trackvis .trk tract file."""

        nib = nb_ut.validate_nibabel('.trk')
        if bpy.context.scene.nb.settingprops.nibabel_valid:
            tv = nib.trackvis
            streams, _ = tv.read(fpath)
            streamlines = [s[0] for s in streams]

            return streamlines

    def read_streamlines_tck(self, fpath):
        """Return all streamlines in a MRtrix .tck tract file."""

        datatype, offset = self.read_mrtrix_header(fpath)
        streamlinevector = self.read_mrtrix_tracks(fpath, datatype, offset)
        streamlines = self.unpack_mrtrix_streamlines(streamlinevector)

        return streamlines

    @staticmethod
    def read_mrtrix_header(tckfile):
        """Return the datatype and offset for a MRtrix .tck tract file."""

        with open(tckfile, 'rb') as f:
            data = f.read()
            lines = data.split(b'\n')
            for line in lines:
                if line == b'END':
                    break
                else:
                    tokens = line.decode("utf-8").rstrip("\n").split(' ')
                    if tokens[0] == 'datatype:':
                        datatype = tokens[1]
                    elif tokens[0] == 'file:':
                        offset = int(tokens[2])

            return datatype, offset

    @staticmethod
    def read_mrtrix_tracks(tckfile, datatype, offset):
        """Return the data from a MRtrix .tck tract file."""

        f = open(tckfile, "rb")
        f.seek(offset)
        if datatype.startswith('Float32'):
            ptype = 'f4'
        if datatype.endswith('BE'):
            ptype = '>' + ptype
        elif datatype.endswith('LE'):
            ptype = '<' + ptype
        streamlinevector = np.fromfile(f, dtype=ptype)

        return streamlinevector

    @staticmethod
    def unpack_mrtrix_streamlines(streamlinevector):
        """Extract the streamlines from the streamlinevector.

        streamlinevector contains N streamlines
        separated by 'nan' triplets and ended with an 'inf' triplet
        """

        streamlines = []
        streamlinevector = np.reshape(streamlinevector, [-1, 3])
        idxs_nan = np.where(np.isnan(streamlinevector))[0][0::3]
        i = 0
        for j in idxs_nan:
            streamlines.append(streamlinevector[i:j, :])
            i = j + 1

        return streamlines

    def read_streamlines_vtk(self, fpath):
        """Return all streamlines in a (MRtrix) .vtk tract file."""

        points, tracts, _, _, _ = self.import_vtk_polylines(fpath)
        streamlines = self.unpack_vtk_polylines(points, tracts)

        return streamlines

    @staticmethod
    def import_vtk_polylines(vtkfile):
        """Read points and polylines from file"""

        with open(vtkfile) as f:
            scalars = cscalars = lut = None
            read_points = 0
            read_tracts = 0
            read_scalars = 0
            read_cscalars = 0
            read_lut = 0
            for line in f:
                tokens = line.rstrip("\n").split(' ')

                if tokens[0] == "POINTS":
                    read_points = 1
                    npoints = int(tokens[1])
                    points = []
                elif read_points == 1 and len(points) < npoints*3:
                    for token in tokens:
                        if token:
                            points.append(float(token))

                elif tokens[0] == "LINES":
                    read_tracts = 1
                    ntracts = int(tokens[1])
                    tracts = []
                elif read_tracts == 1 and len(tracts) < ntracts:
                    tract = []
                    for token in tokens[1:]:
                        if token:
                            tract.append(int(token))
                    tracts.append(tract)

                elif tokens[0] == "POINT_DATA":
                    nattr = int(tokens[1])
                elif tokens[0] == "SCALARS":
                    read_scalars = 1
                    scalar_name = tokens[1]
                    scalar_dtype = tokens[2]
                    scalar_ncomp = tokens[3]
                    scalars = []
                elif read_scalars == 1 and len(scalars) < nattr:
                    scalar = []
                    for token in tokens:
                        if token:
                            scalar.append(float(token))  # NOTE: floats assumed
                    scalars.append(scalar)

                elif tokens[0] == "COLOR_SCALARS":
                    read_cscalars = 1
                    cscalar_name = tokens[1]
                    cscalar_ncomp = tokens[2]
                    cscalars = []
                elif read_cscalars == 1 and len(cscalars) < nattr:
                    cscalar = []
                    for token in tokens:
                        if token:
                            cscalar.append(float(token))
                    cscalars.append(cscalar)

                elif tokens[0] == "LOOKUP_TABLE":
                    read_lut = 1
                    lut_name = tokens[1]
                    lut_size = tokens[2]
                    lut = []
                elif read_lut == 1 and len(lut) < lut_size:
                    entry = []
                    for token in tokens:
                        if token:
                            entry.append(float(token))
                    lut.append(entry)

                elif tokens[0] == '':
                    pass
                else:
                    pass

            points = np.reshape(np.array(points), (npoints, 3))

        return points, tracts, scalars, cscalars, lut

    # TODO SCALARS
    # SCALARS dataName dataType numComp
    # LOOKUP_TABLE tableName
    # s0
    # s1
    # TODO COLOR_SCALARS
    # POINT_DATA 754156
    # COLOR_SCALARS scalars 4
    # 0 1 0.988235 1 0 1 0.988235 1 0 1 0.996078 1
    # 0 0.980392 1 1 0 0.956863 1 1
    # 0 0.854902 1 1 0 0.560784 1 1

    @staticmethod
    def unpack_vtk_polylines(points, tracts):
        """Convert indexed polylines to coordinate lists."""

        streamlines = []
        for tract in tracts:
            streamline = []
            for point in tract:
                streamline.append(points[point])
            stream = np.reshape(streamline, (len(streamline), 3))
            streamlines.append(stream)

        return streamlines

    def read_streamlines_Bfloat(self, fpath):
        """Return all streamlines in a Camino .Bfloat tract file."""

        streamlines = self.read_camino_streamlines(fpath, '>f4')

        return streamlines

    def read_streamlines_bfloat(self, fpath):
        """Return all streamlines in a Camino .bfloat tract file."""

        streamlines = self.read_camino_streamlines(fpath, '<f4')

        return streamlines

    def read_streamlines_Bdouble(self, fpath):
        """Return all streamlines in a Camino .Bdouble tract file."""

        streamlines = self.read_camino_streamlines(fpath, '>f8')

        return streamlines

    def read_streamlines_bdouble(self, fpath):
        """Return all streamlines in a Camino .bdouble tract file."""

        streamlines = self.read_camino_streamlines(fpath, '<f8')

        return streamlines

    @staticmethod
    def read_camino_streamlines(fpath, camdtype):
        """Return all streamlines in a Camino tract file."""

        streamlinevec = np.fromfile(fpath, dtype=camdtype)

        streamlines = []
        offset = 0
        while offset < len(streamlinevec):
            npoints = streamlinevec[offset].astype(int)
            ntokens = npoints * 3
            offset += 2
            streamline = streamlinevec[offset:ntokens + offset]
            streamline = np.reshape(streamline, (npoints, 3))
            offset += ntokens
            streamlines.append(streamline)

        return streamlines

    @staticmethod
    def unpack_camino_streamline(streamlinevec):
        """Extract the first streamline from the streamlinevector.

        streamlinevector contains N streamlines of M points:
        each streamline: [length seedindex M*xyz]
        # DEPRECATED: deletion is incredibly sloooooooowwww
        """

        streamline_npoints = streamlinevec[0]
        streamline_end = streamline_npoints * 3 + 2
        streamline = streamlinevec[2:streamline_end]
        streamline = np.reshape(streamline, (streamline_npoints, 3))
        indices = range(0, streamline_end.astype(int))
        streamlinevec = np.delete(streamlinevec, indices, 0)

        return streamline, streamlinevec

    def read_streamlines_swc(self, fpath):
        """Return all neuron branches in a swc file."""

        swcdict = {}
        streamlines = []
        streamline = []
        with open(fpath, 'rb') as f:
            data = f.read()
            lines = data.split(b'\n')
            for line in lines:

                if line.startswith(b'#') or line == b'':
                    continue

                idx, cp = self.decode_line_swc(line)
                swcdict[idx] = cp

                if 'branchpoint' not in cp.keys():
                    cp['branchpoint'] = False

                if cp['parent'] < 0:  # skip master parent point
                    continue

                pp = swcdict[cp['parent']]

                if cp['structure'] == 1:
                    cp['radius'] *= self.radius_factor_soma

                if cp['structure'] == pp['structure'] == 1:  # no soma
                    continue

                if cp['parent'] < idx - 1:  # new branch

                    pp['branchpoint'] = True

                    if streamline:
                        streamlines.append(streamline)
                    point = pp['co'] + [pp['radius']] + [pp['structure']] + [idx]
                    streamline = [point]
                    if pp['colourcode'] is not None:
                        streamline += [pp['colourcode']]

                point = cp['co'] + [cp['radius']] + [cp['structure']] + [idx]
                if cp['colourcode'] is not None:
                    point += [cp['colourcode']]
                streamline.append(point)

            if streamline:
                streamlines.append(streamline)

        # mark branchpoints
        for streamline in streamlines:
            for point in streamline:
                idx = point[5]
                point.append(float(swcdict[idx]['branchpoint']))

        return streamlines

    def decode_line_swc(self, line):
        """Parse a line of a swc file.
        structure lookup:
        Standardized swc files (www.neuromorpho.org)
        0 - undefined
        1 - soma
        2 - axon
        3 - (basal) dendrite
        4 - apical dendrite
        5+ - custom
        """

        tokens = line.decode("utf-8").rstrip("\n").split(' ')
        if not tokens[0]:  # catch spaces in front of line
            tokens = tokens[1:]

        idx = int(tokens[0])
        pointdict = {
            'structure': int(tokens[1]),
            'co': [float(token) for token in tokens[2:5]],
            'radius': float(tokens[5]),
            'parent': int(tokens[6]),
            }

        try:
            pointdict['colourcode'] = int(tokens[7])  # TODO: implement
        except IndexError:
            pointdict['colourcode'] = None

        return idx, pointdict

    @staticmethod
    def beautification(ob, argdict={"mode": "FULL",
                                    "depth": 0.2,
                                    "res": 5}):
        """Bevel the streamlines."""

        ob.data.fill_mode = argdict["mode"]
        ob.data.bevel_depth = argdict["depth"]
        ob.data.bevel_resolution = argdict["res"]

        infostring = "bevel: "
        infostring += "mode='{}'; "
        infostring += "depth={:.3f}; "
        infostring += "resolution={:d};"
        info = infostring.format(argdict["mode"],
                                 argdict["depth"],
                                 argdict["res"])

        return info

    @staticmethod
    def create_tract_object(context, name):
        """Create an empty tract object."""

        curve = bpy.data.curves.new(name=name, type='CURVE')
        curve.dimensions = '3D'
        ob = bpy.data.objects.new(name, curve)
        context.scene.objects.link(ob)

        return ob

    @staticmethod
    def add_streamlines(ob, streamlines,
                        radius=0.2, radius_variation=False,
                        weed_tract=1., interpolate_streamlines=1.):
        """Add streamlines to a tract object."""

        if (weed_tract == 1) and (interpolate_streamlines == 1):
            for streamline in streamlines:
                nb_ut.make_polyline(ob.data, streamline,
                                    radius, radius_variation)
        else:

            nsamples = int(len(streamlines) * weed_tract)
            streamlines_sample = random.sample(range(len(streamlines)), nsamples)

            for i, streamline in enumerate(streamlines):
                if i in streamlines_sample:
                    if interpolate_streamlines < 1.:
                        # TODO: spline interpolation
                        subs_sl = int(1/interpolate_streamlines)
                        idxs = set(list(range(0, len(streamline), subs_sl)))
                        idxs.add(len(streamline))
                        for i, point in enumerate(streamline):
                            if point[6]:
                                idxs.add(i)
                        mask = [True if i in idxs else False
                                for i, point in enumerate(streamline)]
                        streamline = np.array(streamline)[mask, :]
                    nb_ut.make_polyline(ob.data, streamline,
                                        radius, radius_variation)

        return ob


class NB_OT_attach_neurons(Operator, ImportHelper):
    bl_idname = "nb.attach_neurons"
    bl_label = "Attach neurons"
    bl_description = "Attach neurons to model"
    bl_options = {"REGISTER"}

    create_tract = NB_OT_import_tracts.create_tract_object

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(options={"HIDDEN"}, default="*.py;")

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    density = FloatProperty(
        name="Neuron density",
        description="The fraction of streamlines with a neuron attached",
        default=1.,
        min=0.,
        max=1.)

    radius_factor = FloatProperty(
        name="Radius factor",
        description="Multiplication factor for the radius",
        default=0.01,
        min=0.)

    keep_neurons = BoolProperty(
        name="Keep neurons",
        description="Retain the original neurons",
        default=False)

    keep_layers = BoolProperty(
        name="Keep layers",
        description="Retain separate objects for the neuron layers",
        default=False)

    merge_to_tract = BoolProperty(
        name="Merge to tract",
        description="Integrate the neurons in the tract object",
        default=False)

    def execute(self, context):

        scn = context.scene

        if self.merge_to_tract:
            self.keep_layers = False

        layers = self.load_config()

        split_path = self.data_path.split('.')
        nb_ob = scn.path_resolve('.'.join(split_path[:2]))
        obinfo = nb_ut.get_nb_objectinfo(nb_ob.name)
        buildtype = obinfo['type']
        ob = bpy.data.objects[nb_ob.name]
        if len(split_path) > 2:
            nb_it = scn.path_resolve(self.data_path)
            buildtype = '{}_labelgroup'.format(buildtype)
        else:
            nb_it = None

        layerobs = []
        for layer in layers:

            layer = self.import_neurons(context, layer)

            idxs = self.get_indices(buildtype, ob, nb_it)
            layer['idxs'] = idxs[::int(1/self.density)]

            layerob = self.place_neuron_layer(context, buildtype, layer, ob)
            layerobs.append(layerob)

            if self.keep_layers:
                NB_OT_import_tracts.tract_to_nb(
                    context, layerob,
                    interpolate_streamlines=layer['interpolate_streamlines']
                    )

            if not self.keep_neurons:
                self.remove_neurons(context, layer['neuronset'])

        if not self.keep_layers:

            bpy.ops.object.select_all(action='DESELECT')
            for layerob in layerobs:
                layerob.select = True

            if buildtype.startswith('tracts') and self.merge_to_tract:
                for mat in layerob.data.materials[1:]:
                    ob.data.materials.append(mat)
                    # FIXME: how does this combine with overlays?!
                ob = self.join(ob, ob.name)
                layerobs = [ob]
                # TODO: update NB object
            else:
                cob = self.join(layerob, 'circuits')
                if buildtype.startswith('tracts'):
                    layerobs = [ob, cob]
                else:
                    layerobs = [cob]
                NB_OT_import_tracts.tract_to_nb(
                    context, cob,
                    interpolate_streamlines=layer['interpolate_streamlines']
                    )
        else:
            if buildtype.startswith('tracts'):
                layerobs.append(ob)

        for layerob in layerobs:
            for spl in layerob.data.splines:
                for point in spl.points:
                    point.radius *= self.radius_factor

        return {"FINISHED"}

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def load_config(self, selection=[]):
        """Load a configuration for neuron layers."""

        if self.directory not in sys.path:
            sys.path.append(self.directory)
        modulename = os.path.splitext(self.files[0].name)[0]
        conf = importlib.import_module(modulename)

        alllayers = conf.config()
        if selection:
            layers = [layer for i, layer in enumerate(alllayers)
                      if i in selection]
            return layers
        else:
            return alllayers

    def import_neurons(self, context, layer):
        """Import a set of neurons."""

        scn = context.scene
        nb = scn.nb

        bpy.ops.object.select_all(action='DESELECT')

        swcs = glob(os.path.join(layer['directory'], layer['swcs_regex']))
        files = [{"name": os.path.basename(swc)} for swc in swcs]
        bpy.ops.nb.import_tracts(
            directory=layer['directory'],
            files=files,
            beautify=False,
            interpolate_streamlines=layer['interpolate_streamlines'],
            )

        layer['neuronset'] = []
        for i, neuronob in enumerate(context.selected_objects):

            nb_ob = nb.tracts.get(neuronob.name)
            nb_ob.name = '{}_{:02d}'.format(layer['celltype'], i)

            # FIXME: robust orient and length estimates
            neuron_length = max(neuronob.dimensions)
            neuron_orient = self.neuron_orientation(neuronob,
                                                    layer['celltype'])
            if neuron_orient is not None:
                layer['neuronset'].append(
                    {'name': neuronob.name,
                     'orientation': neuron_orient,
                     'location': neuronob.location,
                     'length': neuron_length})
            else:
                self.remove_neuron(context, nb_ob.name)

#             if (layer['extend_streamline'] and (layer['snappoint'] == 'soma')):
#                 self.delete_processes_by_matindex(neuronob, 2)

        return layer

    def remove_neurons(self, context, neuronset):
        """Remove a set of neuron tract objects."""

        for neuron in neuronset:
            self.remove_neuron(context, neuron['name'])

    def remove_neuron(self, context, name):
        """Remove a neuron tract object."""

        scn = context.scene
        nb = scn.nb

        nb_ob = nb.tracts.get(name)
        bpy.ops.nb.nblist_ops(action="REMOVE_L1",
                              data_path=nb_ob.path_from_id())

    def delete_processes_by_matindex(self, ob, idx):
        """Delete an axon from an swc neuron."""

        for spl in ob.data.splines:
            if spl.material_index == idx:
                ob.data.splines.remove(spl)

    def neuron_orientation(self, neuronob, celltype):
        """Determine the orientation of a neuron curve object."""

        neuron_orient = None

        if celltype == 'pyramidal':
            # TODO: use apical dendrite instead/aswell
            for spl in neuronob.data.splines:
                if spl.material_index == 2:
                    soma = spl.points[0].co
                    axend = spl.points[-1].co
                    neuron_orient = soma - axend

        elif celltype == 'basket':
            neuron_orient = Vector([0, 0, 1])

        return neuron_orient

    def get_transmat(self, neuron, target):
        """Build a transformation matrix for neuron rotation."""

        # scale
        scalefactor = target['length'] / neuron['length']
        mat_scale = Matrix.Scale(scalefactor, 4)

        # translation
        translation = target['location'] - neuron['location']
        mat_trans = Matrix.Translation(translation)

        # rotation
        no = neuron['orientation']
        to = target['orientation']
        rotation = no.rotation_difference(to)
        mat_rot = rotation.to_matrix().to_4x4()

        return mat_trans * mat_rot * mat_scale

    def place_neuron_layer(self, context, buildtype, layer, ob):
        """Place a layer of neurons."""

        bpy.ops.object.select_all(action='DESELECT')

        for idx in layer['idxs']:

            neuron = random.choice(layer['neuronset'])
            neuronob = bpy.data.objects[neuron['name']]

            if buildtype.startswith('tracts'):
                v0, v1, spline, is_valid = self.target_tracts(ob, idx)
            elif buildtype.startswith('surfaces'):
                v0, v1, _, is_valid = self.target_surfaces(ob, idx)

            if not is_valid:
                continue

            target = self.target_dict(v0, v1, layer)
            transmat = self.get_transmat(neuron, target)
            cob = self.place_neuron(context, neuronob, transmat)

            if buildtype.startswith('tracts') and layer['extend_streamline']:
                self.extend_axon(spline, cob, layer['snappoint'])

        self.join(cob, layer['name'])

        return cob

    def place_neuron(self, context, neuronob, transmat):
        """Copy and transform a neuron object."""

        curve = neuronob.data.copy()
        curve.transform(transmat)
        curveob = bpy.data.objects.new('ob', curve)
        curveob.select = True
        context.scene.objects.link(curveob)

        # reset the radius to correct for scaling
        scalefactor = transmat.to_scale()[0]
        for spl in curveob.data.splines:
            for point in spl.points:
                point.radius /= scalefactor

        return curveob

    def target_tracts(self, ob, idx, length=1.):
        """Attach a layer of neurons to tract ends."""

        spline = ob.data.splines[idx]
        is_valid = len(spline.points) > 1

        v0 = Vector(spline.points[-1].co[:3])
        vt = Vector(spline.points[-2].co[:3])
        v1 = v0 + (v0 - vt)

        return v0, v1, spline, is_valid

    def target_surfaces(self, ob, idx, length=1.):
        """Attach a layer of neurons to tract ends."""

        v0 = ob.data.vertices[idx].co

        if 'white' in ob.name:
            outername = ob.name.replace('white', 'pial')
            outer = bpy.data.objects.get(outername)
        else:
            outer = None

        if outer is not None:
            v1 = outer.data.vertices[idx].co
        else:
            v1 = v0 + ob.data.vertices[idx].normal * length

        return v0, v1, v0, True

    def target_dict(self, v0, v1, layer):
        """Create target for neuron by extrapolating spline."""

        segvec = v1 - v0
        target = {'orientation': segvec,
                  'location': v0 + segvec * layer['offset'],
                  'length': segvec.length * layer['scalefactor']}

        return target

    def join(self, ob, layername):
        """Join neurons/layers together and rename."""

        ob.select = True
        bpy.context.scene.objects.active = ob
        bpy.ops.object.join()

        ob.name = ob.data.name = layername
        ob.material_slots[0].material.name = layername

        for ms in ob.material_slots[1:]:
            mat = ms.material
            split_name = mat.name.split('.')
            newname = '.'.join([layername] + [split_name[-1]])
            ms.material = mat.copy()
            ms.material.name = newname

        return ob

    def extend_axon(self, spline, neuronob, snappoint='soma'):
        """Extend the tract spline to the neuron."""

        # find an axon spline in the neuron
        for spl in neuronob.data.splines:
            if spl.material_index == 2:
                break

        # determine the end to attach the streamline to
        idx = 0 if snappoint == 'soma' else -1

        # add a point on the streamline
        spline.points.add()
        spline.points[-1].co = spl.points[idx].co
        spline.points[-1].radius = spl.points[idx].radius

        # remove the axons from the neuron
        if snappoint == 'soma':
            self.delete_processes_by_matindex(neuronob, 2)

    def get_vertex_indices_in_groups(self, surf, vgs):
        """Return all vertex indices included in a vertex group."""

        vi_select = []
        vgs_idxs = [g.index for g in vgs]
        me = surf.data
        for poly in surf.data.polygons:
            for vi in poly.vertices:
                allgroups = [g.group for g in me.vertices[vi].groups]
                for vgs_idx in vgs_idxs:
                    if vgs_idx in allgroups:
                        vi_select.append(vi)
        return vi_select

    def get_indices(self, buildtype, ob, nb_it=None):
        """Return the indices for attaching neuron."""

        if buildtype == 'tracts':
            idxs = [i for i in range(0, len(ob.data.splines))]
        elif buildtype == 'surfaces':
            idxs = [i for i in range(0, len(ob.data.vertices))]
        elif buildtype == 'tracts_labelgroup':
            idxs = [i for i, spl in enumerate(ob.data.splines)
                    if spl.material_index == nb_it.value]
        elif buildtype == 'surfaces_labelgroup':
            vgs = [ob.vertex_groups[nb_it.name]]
            idxs = self.get_vertex_indices_in_groups(ob, vgs)

        return idxs
