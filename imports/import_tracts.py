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
from random import sample

import numpy as np

import bpy
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

    qb_separation = BoolProperty(
        name="QuickBundles separate",
        description="Create a tract object for every QuickBundles cluster",
        default=False)

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
            self.import_tract(context, fpath)

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

        row = layout.row()
        row.prop(self, "use_quickbundles")
        if self.use_quickbundles:
            row = layout.row()
            row.prop(self, "qb_points")
            row.prop(self, "qb_threshold")
            row = layout.row()
            row.prop(self, "qb_centroids")
            row.prop(self, "qb_separation")

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def import_tract(self, context, fpath):
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

        ca = [bpy.data.objects,
              bpy.data.meshes,
              bpy.data.materials,
              bpy.data.textures]
        name = nb_ut.check_name(self.name, fpath, ca)

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

        if self.use_quickbundles:
            obs = self.quickbundles(context, name, streamlines)
        else:
            obs = [self.create_tract_object(context, name)]
            self.add_streamlines(obs[0], streamlines)
            # swc colouring
            if ext[1:] == 'swc':
                structs = [(0, '.apical_dendrite'),
                           (1, '.basal_dendrite'),
                           (2, '.axon'),
                           (3, '.soma'),
                           (4, '')]
            else:
                structs = [(-1, '')]

            for i, struct in structs:
                info_mat = nb_ma.materialise(obs[0],
                                             self.colourtype,
                                             self.colourpicker,
                                             self.transparency,
                                             struct, i)

        # TODO: handle cases where transform info is included in tractfile
        affine = nb_ut.read_affine_matrix(self.sformfile)

        for ob in obs:

            ob.matrix_world = affine

            props = {
                "name": ob.name,
                "filepath": fpath,
                "sformfile": self.sformfile,
                "nstreamlines": len(ob.data.splines),
                "tract_weeded": self.weed_tract,
                "streamlines_interpolated": self.interpolate_streamlines
                }
            nb_ut.add_item(nb, "tracts", props)

            nb_ut.move_to_layer(ob, 0)
            scn.layers[0] = True

            group = bpy.data.groups.get("tracts") or \
                bpy.data.groups.new("tracts")
            group.objects.link(ob)

#             scn.objects.active = ob
#             ob.select = True
#             scn.update()

            if self.beautify:
                beaudict = {"mode": "FULL", "depth": 0.05, "res": 5}
                info_beau = self.beautification(ob, beaudict)
            else:
                info_beau = "no bevel"

            info_mat=''
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
                info = infostring.format(info, name, fpath, affine,
                                         self.weed_tract,
                                         self.interpolate_streamlines,
                                         info_mat, info_beau)
            self.report({'INFO'}, info)

        return "done"

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

                if cp['parent'] < 0:  # skip master parent point
                    continue

                pp = swcdict[cp['parent']]

                if cp['structure'] == pp['structure'] == 1:  # no soma
                    continue
                if cp['parent'] < idx - 1:  # new branch
                    if streamline:
                        streamlines.append(streamline)
                    point = pp['co'] + [pp['radius']] + [pp['structure']]
                    streamline = [point]
                    if pp['colourcode'] is not None:
                        streamline += [pp['colourcode']]

                point = cp['co'] + [cp['radius']] + [cp['structure']]
                if cp['colourcode'] is not None:
                    point += [cp['colourcode']]
                streamline.append(point)

            if streamline:
                streamlines.append(streamline)

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
    def beautification(ob, argdict={"mode": "FULL", "depth": 0.5, "res": 10}):
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

    def quickbundles(self, context, name, streamlines):
        """Segment tract with QuickBundles."""

        # TODO: implement other metrics
        try:
            from dipy.segment.clustering import QuickBundles
            from dipy.segment.metric import ResampleFeature
            from dipy.segment.metric import AveragePointwiseEuclideanMetric
        except ImportError:
            obs = [self.create_tract_object(context, name)]
            self.add_streamlines(obs[0], streamlines)
            return obs
        else:

            feature = ResampleFeature(nb_points=self.qb_points)
            metric = AveragePointwiseEuclideanMetric(feature=feature)
            qb = QuickBundles(threshold=self.qb_threshold, metric=metric)
            clusters = qb.cluster(streamlines)

            obs = self.qb_separate(context, name, clusters, streamlines)
            centroid_ob = self.qb_centroid_object(context, name, clusters)

            if centroid_ob is not None:
                obs.append(centroid_ob)

            self.qb_materialise(context, name, clusters, centroid_ob)

        return obs

    def qb_separate(self, context, name, clusters, streamlines):
        """Separate streamline clusters."""

        obs = []
        if self.qb_separation:
            for cluster in clusters:
                cname = '{}.cluster{:05d}'.format(name, cluster.id)
                ob = self.create_tract_object(context, cname)
                cstreamlines = [streamlines[idx]
                                for idx in cluster.indices]
                self.add_streamlines(ob, cstreamlines)
                obs.append(ob)
        else:
            ob = self.create_tract_object(context, name)
            self.add_streamlines(ob, streamlines)
            obs.append(ob)

        return obs

    def qb_centroid_object(self, context, name, clusters):

        if self.qb_centroids:
            cname = '{}.centroids'.format(name)
            centroid_ob = self.create_tract_object(context, cname)
            centroids = [cluster.centroid for cluster in clusters]
            self.add_streamlines_unfiltered(centroid_ob, centroids)
            if self.beautify:
                beaudict = {"mode": "FULL", "depth": 0.5, "res": 5}
                self.beautification(centroid_ob, beaudict)
        else:
            centroid_ob = None

        return centroid_ob

    def qb_materialise(self, context, name, clusters, centroid_ob=None):
        """Assign materials to streamline clusters."""

        trans = 1.
        diff_rn = 0.1
        mix = 0.05
        colourtype = "golden_angle"

        for cluster in clusters:

            cname = '{}.cluster{:05d}'.format(name, cluster.id)
            diffcol = nb_ma.get_golden_angle_colour(cluster.id)
            diffcol.append(trans)
            mat = nb_ma.make_cr_mat_basic(cname, diffcol, mix, diff_rn)
            nb_ma.link_innode(mat, colourtype)

            if self.qb_separation:
                ob = bpy.data.objects[cname]
                ob.data.materials.append(mat)
            else:
                ob = bpy.data.objects[name]
                ob.data.materials.append(mat)
                for cl_idx in cluster.indices:
                    spline = ob.data.splines[cl_idx]
                    spline.material_index = cluster.id

            if centroid_ob is not None:
                centroid_ob.data.materials.append(mat)
                cspline = centroid_ob.data.splines[cluster.id]
                cspline.material_index = cluster.id

    def create_tract_object(self, context, name):
        """Create an empty tract object."""

        curve = bpy.data.curves.new(name=name, type='CURVE')
        curve.dimensions = '3D'
        ob = bpy.data.objects.new(name, curve)
        context.scene.objects.link(ob)

        return ob

    def add_streamlines(self, ob, streamlines):
        """Add streamlines to a tract object."""

        nsamples = int(len(streamlines) * self.weed_tract)
        streamlines_sample = sample(range(len(streamlines)), nsamples)

        for i, streamline in enumerate(streamlines):
            if i in streamlines_sample:
                if self.interpolate_streamlines < 1.:
                    subs_sl = int(1/self.interpolate_streamlines)
                    streamline = np.array(streamline)[::subs_sl, :]
                nb_ut.make_polyline(ob.data, streamline)

        return ob

    def add_streamlines_unfiltered(self, ob, streamlines):
        """Add streamlines to a tract object."""

        for streamline in streamlines:
            nb_ut.make_polyline(ob.data, streamline)

