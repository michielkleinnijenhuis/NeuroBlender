#

bl_info = {
    "name": "Tractography Visualisation",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 1),
    "blender": (2, 7, 0),
    "location": "Properties -> Scene -> Record Macro",
    "description": "Visualising tractography results",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}
#============================================================================#

import os
import bpy
import numpy as np
from math import sin, pi, radians

# Define import properties
bpy.types.Scene.tract_objectname = bpy.props.StringProperty \
    (
    name = "Object name",
    description = "Specify a name for the tract [default is filename]",
    default = ''
    )
bpy.types.Scene.tract_scale = bpy.props.FloatProperty \
    (
    name = "Scale",
    description = "Resize the tracts",
    default = 1.0,
    min = 1e-10,
    precision=4
    )
bpy.types.Scene.tract_beautify = bpy.props.BoolProperty \
    (
    name = "Beautify",
    description = "preload default modifiers, materials, textures, etc",
    default = True
    )
# submenu: solid color/rgb, smooth, texture, 

class ImportTracts(bpy.types.Panel):
    bl_label = "Import Tracts"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    
    def draw(self, context):
        row = self.layout.row()
        row.prop(context.scene , "tract_objectname")
        
        row = self.layout.row()
        row.prop(context.scene , "tract_scale")
       
        row = self.layout.row()
        row.prop(context.scene , "tract_beautify")

        row = self.layout.row()
        row.operator("import.tract", text='Import Tracts', icon='MESH_ICOSPHERE')

class TractImportButton(bpy.types.Operator):
    """Import and scale the tracts"""
    bl_idname = "import.tract"
    bl_label = "Import tracts"
    
    directory = bpy.props.StringProperty(subtype="FILE_PATH")
    files = bpy.props.CollectionProperty(name='File path', type=bpy.types.OperatorFileListElement)
    
    def execute(self, context):
        
        items = [file.name for file in self.files]
        import_tracts(self.directory, items)
        
        return {'FINISHED'}
        
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
bpy.types.Scene.source =  bpy.props.StringProperty(subtype="FILE_PATH")

def import_tracts(dir,files):
    """"""
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
        
    s = bpy.context.scene.tract_scale
    
    for f in files:
        
        fpath = os.path.join(dir, f)
        if bpy.context.scene.tract_objectname:
            objectname = bpy.context.scene.tract_objectname
        else:
            objectname = os.path.basename(fpath)
        
        if f.endswith('.vtk'):
            streamlines = read_vtk_streamlines(fpath)
        elif f.endswith('.Bfloat'):
            streamlines = read_camino_streamlines(fpath)
        elif f.endswith('.tck'):
            streamlines = read_mrtrix_streamlines(fpath)
        
        for streamline in streamlines:
            make_polyline(objectname, objectname, streamline)
        
        bpy.ops.object.select_all(action='DESELECT')
        for item in bpy.data.objects:
            if item.type == "CURVE":
                item.select = True
        
        ob = bpy.data.objects[objectname]
        bpy.context.scene.objects.active = ob
        bpy.ops.object.join()
        bpy.data.objects[objectname].data.bevel_depth = s * 0.5
        bpy.data.objects[objectname].data.bevel_resolution = 10
        
        bpy.context.scene.objects.active = ob
        bpy.data.objects.get(ob.name).select = True
        ob.scale = [s, s, s]
        ob.rotation_euler = [-0, 0, 0]
        bpy.ops.object.transform_apply(scale=True)
        
        if bpy.types.Scene.tract_beautify:
            pass
            # call beautify functions here

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
    return (streamline, streamlinevector)

def read_camino_streamlines(bfloatfile):
    """Return all streamlines in a Camino .Bfloat tract file."""
    if bfloatfile.endswith('.Bfloat'):
        streamlinevector = np.fromfile(bfloatfile, dtype='>f4')
    elif bfloatfile.endswith('.bfloat'):
        streamlinevector = np.fromfile(bfloatfile, dtype='<f4')
    streamlines = []
    while streamlinevector.size:
        (streamline, streamlinevector) = unpack_camino_streamline(streamlinevector)
        streamlines.append(streamline)
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
    return (points, tracts)

def unpack_vtk_polylines(points, tracts):
    """Convert indexed polylines to coordinate lists"""
    streamlines = []
    for tract in tracts:
        streamline = []
        for point in tract:
            streamline.append(points[point])
        stream = np.reshape(streamline, (len(streamline), 3))
        streamlines.append(stream)
    return streamlines

def read_vtk_streamlines(vtkfile):
    """Return all streamlines in a (MRtrix) .vtk tract file."""
    (points, tracts) = import_vtk_polylines(vtkfile)
    streamlines = unpack_vtk_polylines(points, tracts)
    return streamlines

def read_mrtrix_header(tckfile):
    """Return the datatype and offset for a MRtrix .tck tract file."""
    with open(tckfile) as f:
        for line in f:
            if line == 'END\n':
                break
            else:
                tokens = line().rstrip("\n").split(' ')
                if tokens[0] == 'datatype:':
                    datatype = tokens[1]
                elif tokens[0] == 'file:':
                    offset = tokens[2]
        return (datatype, offset)

def unpack_mrtrix_streamlines(streamlinevector):
    """Extract the streamlines from the streamlinevector.
    
    streamlinevector contains N streamlines 
    separated by NaN triplets and ended with and Inf triplet
    """
    streamline = []
    streamlines = []
    for xyz in streamlinevector:
        point.append(xyz)
        if point.size == 3:
            if point.isnan:
                streamlines.append(streamline)
                streamline = []
            elif point.isinf:
                return streamlines
            else:
                streamline.append(point)
                point = []
                

def read_mrtrix_tracks(tckfile, datatype, offset):
    """Return the data from a MRtrix .tck tract file."""
    f = open(tckfile, "rb")
    f.seek(offset)
    if datatype.startswith('Float32'):
        type = 'f4'
    if datatype.endswith('BE'):
        type = '>' + type
    elif datatype.endswith('LE'):
        type = '<' + type
    streamlinevector = np.fromfile(f, dtype=type)
    return streamlinevector

def read_mrtrix_streamlines(tckfile):
    """Return all streamlines in a MRtrix .tck tract file."""
    (datatype, offset) = read_mrtrix_header(tckfile)
    streamlinevector = read_mrtrix_tracks(tckfile, datatype, offset)
    streamlines = unpack_mrtrix_streamlines(streamlinevector)
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


#============================================================================#
def register():
    bpy.utils.register_module(__name__)
    
    pass
    
def unregister():
    bpy.utils.unregister_module(__name__)
    
    pass
    
if __name__ == "__main__":
    register()  
