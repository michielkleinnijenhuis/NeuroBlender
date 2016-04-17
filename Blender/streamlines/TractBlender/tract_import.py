import os
import bpy
import random
import numpy as np

class ImportTractsPanel(bpy.types.Panel):
    """The 'Import Tracts' panel."""
    
    bl_label = "Import Tractography Streamlines"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    
    def draw(self, context):
        """Draw the panel."""
        
        row = self.layout.row()
        row.prop(context.scene, "tract_name")
        
        row = self.layout.row()
        row.prop(context.scene, "tract_scale")
        
        row = self.layout.row()
        row.prop(context.scene, "tract_bevel")
        
        row = self.layout.row()
        row.label(text="Colour: ")
        if context.scene.tract_colourtype == 'pick':
            row.prop(context.scene, "tract_colourpicker")
        row.prop(context.scene, "tract_colourtype")
        
        row = self.layout.row()
        row.separator()
        
        row = self.layout.row()
        row.operator("import.tracts", 
                     text='Import tracts', icon='CURVE_BEZCURVE')

class TractImportButton(bpy.types.Operator):
    """The button that prompt for tracts to import."""
    
    bl_idname = "import.tracts"
    bl_label = "Import tracts"
    
    directory = bpy.props.StringProperty(subtype="FILE_PATH")
    files = bpy.props.CollectionProperty(name='Filepath', 
                                         type=bpy.types.OperatorFileListElement)
    
    def execute(self, context):
        """Import the tracts."""
        
        items = [file.name for file in self.files]
        import_tracts(self.directory, items)
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        """Prompt to select tract files."""
        
        context.window_manager.fileselect_add(self)
        
        return {'RUNNING_MODAL'}

bpy.types.Scene.source =  bpy.props.StringProperty(subtype="FILE_PATH")

def import_tracts(directory, files):
    """Import streamlines.
    
    This imports the streamlines found in the specified directory/files.
    Valid formats include:
    - .Bfloat (Camino big-endian floats; from 'track' command)
      == http://camino.cs.ucl.ac.uk/index.php?n=Main.Fileformats
    - .vtk (vtk polydata (ASCII); e.g. from MRtrix's 'tracks2vtk' command)
      == http://www.vtk.org/wp-content/uploads/2015/04/file-formats.pdf
    - .tck (MRtrix)
      == http://jdtournier.github.io/mrtrix-0.2/appendix/mrtrix.html
    - .npy (2d numpy arrays [Npointsx3]; single streamline per file)
    - .npz (zipped archive of Nstreamlines .npy files)
      == http://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.savez.html
    
    It joins the individual streamlines into one 'Curve' object.
    Tracts are scaled according to the 'scale' box.
    Beautify functions/modifiers are applied to the tract.
    """
    
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    
    sx = sy = sz = bpy.context.scene.tract_scale
    rx = ry = rz = 0
    
    colourtype = bpy.context.scene.tract_colourtype
    
    if not files:
        files = os.listdir(directory)
    
    for f in files:
        fpath = os.path.join(directory, f)
        
        tractname = check_tractname(bpy.context.scene.tract_name, fpath)
        
        if f.endswith('.vtk'):
            streamlines = read_vtk_streamlines(fpath)
        elif f.endswith('.Bfloat'):
            streamlines = read_camino_streamlines(fpath)
        elif f.endswith('.tck'):
            streamlines = read_mrtrix_streamlines(fpath)
        elif f.endswith('.npy'):
            streamlines = read_numpy_streamline(fpath)
        elif f.endswith('.npz'):
            streamlines = read_numpyz_streamlines(fpath)
        
        curve = bpy.data.curves.new(name=tractname, type='CURVE')
        curve.dimensions = '3D'
        ob = bpy.data.objects.new(tractname, curve)
        bpy.context.scene.objects.link(ob)
        for streamline in streamlines:
            ob = make_polyline_ob(curve, streamline)
        
        ob = bpy.data.objects[tractname]
        curve = ob.data
        
        transform_tract(ob, [sx, sy, sz], [rx, ry, rz])
        
        bevel_tract(curve)
        
        materialise_tract(ob, bpy.context.scene.tract_count, colourtype)
        
        bpy.context.scene.tract_count += 1

def check_tractname(tractname, fpath):
    """Make sure a unique tractname is given."""
    
    if not tractname:
        tractname = os.path.basename(fpath)
    
    i = 0
    while bpy.data.objects.get(tractname) is not None:
        tractname = tractname + '.' + str(i)
        i += 1
#         tractname = tractname + '.' + str(random.random())[-10:]
    
    return tractname

def transform_tract(ob, scale=[1,1,1], rot=[0,0,0]):
    """Transform the tract coordinates."""
    
    # TODO: get the transformation matrix from freesurfer/nifti
    ob.scale = scale
    ob.rotation_euler = rot

def bevel_tract(me, depth=0.5, res=10):
    """Set the bevel parameters for the streamlines."""
    
    if bpy.context.scene.tract_bevel:
        me.fill_mode = 'FULL'
        me.bevel_depth = depth
        me.bevel_resolution = res

def materialise_tract(ob, tractnr, colourtype):
    """Attach material to tracts."""
    
    primary6_colours = [[1,0,0],[0,1,0],[0,0,1],
                        [1,1,0],[1,0,1],[0,1,1]]
    
    ob.show_transparent = True
    
    if colourtype in ['primary6', 'random', 'pick']:
        if colourtype == 'primary6':
            matname = 'primary6_' + str(tractnr % 6)
            diffcol = primary6_colours[tractnr % 6] + [0.8]
        elif colourtype == 'random':
            matname = 'tract_' + str(tractnr)
            diffcol = random_RGBA()
        elif colourtype == 'pick':
            matname = 'picked' + str(tractnr)
            diffcol = list(bpy.context.scene.tract_colourpicker) + [1.]
        if bpy.data.materials.get(matname) is not None:
            mat = bpy.data.materials[matname]
        else:
            mat = make_material(matname, diffcol, alpha=0.9)
        set_material(ob.data, mat)
    elif colourtype == 'directional':
        # http://blender.stackexchange.com/questions/43102
        import_materials()
        ob.data.use_uv_as_generated = True
        matname = 'directional'
        mat = bpy.data.materials[matname]
        set_material(ob.data, mat)
    else:
        pass



def read_camino_streamlines(bfloatfile):
    """Return all streamlines in a Camino .bfloat/.Bfloat tract file."""
    
    if bfloatfile.endswith('.Bfloat'):
        streamlinevector = np.fromfile(bfloatfile, dtype='>f4')
    elif bfloatfile.endswith('.bfloat'):
        streamlinevector = np.fromfile(bfloatfile, dtype='<f4')
    
    streamlines = []
    while streamlinevector.size:
        streamline, streamlinevector = unpack_camino_streamline(streamlinevector)
        streamlines.append(streamline)
    
    return streamlines

def unpack_camino_streamline(streamlinevector):
    """Extract the first streamline from the streamlinevector.
    
    streamlinevector contains N streamlines of M points:
    each streamline: [length errorcode M*xyz]
    """
    
    streamline_npoints = streamlinevector[0]
    streamline_end = streamline_npoints * 3 + 2
    streamline = streamlinevector[2:streamline_end]
    streamline = np.reshape(streamline, (streamline_npoints, 3))
    indices = range(0, streamline_end.astype(int))
    streamlinevector = np.delete(streamlinevector, indices, 0)
    
    return streamline, streamlinevector


def read_vtk_streamlines(vtkfile):
    """Return all streamlines in a (MRtrix) .vtk tract file."""
    
    points, tracts = import_vtk_polylines(vtkfile)
    streamlines = unpack_vtk_polylines(points, tracts)
    
    return streamlines

def import_vtk_polylines(vtkfile):
    """Read points and polylines from file"""
    
    with open(vtkfile) as f:
        read_points = 0
        read_tracts = 0
        p = 0
        t = 0
        for line in f:
            tokens = line.rstrip("\n").split(' ')
            if tokens[0] == "POINTS":
                read_points = 1
                npoints = int(tokens[1])
                points = np.zeros((npoints,3), dtype=np.float)
            elif read_points == 1 and p < npoints:
                points[p,0] = float(tokens[0])
                points[p,1] = float(tokens[1])
                points[p,2] = float(tokens[2])
                p += 1
            elif tokens[0] == '' and read_tracts == 1:
                t += 1
                i = -1
            elif tokens[0] == '':
                pass
            elif tokens[0] == "LINES":
                read_tracts = 1
                ntracts = int(tokens[1])
                tracts = [None] * ntracts
                i = -1
            elif read_tracts == 1 and t < ntracts:
                if i == -1:
                    tracts[t] = np.zeros(int(tokens[0]), dtype=np.int)
                    i += 1
                else:
                    tracts[t][i] = int(tokens[0])
                    i += 1
            else:
                pass
    
    return points, tracts

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


def read_mrtrix_streamlines(tckfile):
    """Return all streamlines in a MRtrix .tck tract file."""
    
    datatype, offset = read_mrtrix_header(tckfile)
    streamlinevector = read_mrtrix_tracks(tckfile, datatype, offset)
    streamlines = unpack_mrtrix_streamlines(streamlinevector)
    
    return streamlines

def read_mrtrix_header(tckfile):
    """Return the datatype and offset for a MRtrix .tck tract file."""
    
    with open(tckfile,'rb') as f:
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

def unpack_mrtrix_streamlines(streamlinevector):
    """Extract the streamlines from the streamlinevector.

    streamlinevector contains N streamlines
    separated by 'nan' triplets and ended with an 'inf' triplet
    """
    
    streamlines = []
    streamlinevector = np.reshape(streamlinevector, [-1,3])
    idxs_nan = np.where(np.isnan(streamlinevector))[0][0::3]
    i = 0
    for j in idxs_nan:
        streamlines.append(streamlinevector[i:j,:])
        i = j + 1
    
    return streamlines


def read_numpy_streamline(tckfile):
    """Read a [Npointsx3] streamline from a *.npy file."""
    
    streamline = np.load(tckfile)
    
    return [streamline]

def read_numpyz_streamlines(tckfile):
    """Return all streamlines from a *.npz file.
    
    e.g. from 'np.savez_compressed(outfile, streamlines0=streamlines0, ..=..)'
    NOTE: This doesn't work for .npz pickled in Python 2.x,!! ==>
    Unicode unpickling incompatibility
    """
    
    # TODO: proper checks and error handling
    # TODO: multitract npz
    streamlines = []
    npzfile = np.load(tckfile)
    k = npzfile.files[0]
    if len(npzfile.files) == 0:
        print('No files in archive.')
    elif len(npzfile.files) == 1:         # single tract / streamline
        if len(npzfile[k][0][0]) == 3:      # k contains a list of Nx3 arrays
            streamlines = npzfile[k]
        else:                               # k contains a single Nx3 array
            streamlines.append(npzfile[k])
    elif len(npzfile.files) > 1:          # multiple tracts / streamlines
        if len(npzfile[k][0][0]) == 3:      # k contains a list of Nx3 arrays
            print('multi-tract npz not supported yet.')
        else:                               # each k contains a single Nx3 array
            for k in npzfile:
                streamlines.append(npzfile[k])
    
    return streamlines



def make_polyline(objname, curvename, cList):
    """Create a 3D curve from a list of points."""
    
    curvedata = bpy.data.curves.new(name=curvename, type='CURVE')
    curvedata.dimensions = '3D'
    objectdata = bpy.data.objects.new(objname, curvedata)
    objectdata.location = (0,0,0)
    bpy.context.scene.objects.link(objectdata)
    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(cList)-1)
    for num in range(len(cList)):
        x, y, z = cList[num]
        polyline.points[num].co = (x, y, z, 1)
    
    return objectdata

def make_polyline_ob(curvedata, cList):
    """Create a 3D curve from a list of points."""
    
    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(cList)-1)
    for num in range(len(cList)):
        x, y, z = cList[num]
        polyline.points[num].co = (x, y, z, 1)



def random_RGBA():
    """Get a random RGB triplet + alpha."""
    
    return [random.random() for _ in range(4)]

def set_material(me, mat):
    """Attach a material to a mesh."""
    
    if len(me.materials):
        me.materials[0] = mat
    else:
        me.materials.append(mat)

def make_material(name='Material', 
                  diffuse=[1,0,0,1], specular=[1,1,1,0.5], alpha=1):
    """Create a basic material."""
    
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = diffuse[:3]
    mat.diffuse_shader = 'LAMBERT'
    mat.diffuse_intensity = diffuse[3]
    mat.specular_color = specular[:3]
    mat.specular_shader = 'COOKTORR'
    mat.specular_intensity = specular[3]
    mat.alpha = alpha
    mat.use_transparency = True
    mat.ambient = 1
    
    return mat

def import_materials(matfile='TB_materials_cycles.blend'):
    """"Import any materials included in the module."""
    
    # TODO: perform checks on existing materials
    if bpy.data.materials.get('directional') is None:
        TBdir, _ = os.path.split(__file__)
        matpath = os.path.join(TBdir, matfile)
        with bpy.data.libraries.load(matpath) as (data_from, data_to):
            data_to.materials = data_from.materials
        bpy.context.scene.render.engine = 'CYCLES'
#         
#         return {'directional material imported; \
#                  render engine changed to "cycles"'}

#============================================================================#

def register():
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
