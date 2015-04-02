#

import os
import bpy
import numpy as np
from math import sin, pi, radians

# Delete 'Cube'
try:
    bpy.data.objects['Cube'].select = True
    bpy.ops.object.delete()
except:
    print("Cube not found. Good! Let's go!")


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
    """Return all streamlines in a Camino .bfloat tract file."""
    streamlinevector = np.fromfile(bfloatfile, dtype='>f4')
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


def make_polyline(objname, curvename, cList):
    """Create a 3D curve from a list of points."""
    curvedata = bpy.data.curves.new(name=curvename, type='CURVE')
    curvedata.dimensions = '3D'
    #curvedata.bevel_depth = 1
    #curvedata.bevel_resolution = 10
    objectdata = bpy.data.objects.new(objname, curvedata)
    objectdata.location = (0,0,0) #object origin
    bpy.context.scene.objects.link(objectdata)
    polyline = curvedata.splines.new('POLY')
    polyline.points.add(len(cList)-1)
    for num in range(len(cList)):
        x, y, z = cList[num]
        polyline.points[num].co = (x, y, z, 1)


def makeMaterial(name, diffuse, specular, alpha):
    """Create a material."""
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = diffuse
    mat.diffuse_shader = 'LAMBERT' 
    mat.diffuse_intensity = 1.0 
    mat.specular_color = specular
    mat.specular_shader = 'COOKTORR'
    mat.specular_intensity = 0.5
    mat.alpha = alpha
    mat.ambient = 1
    return mat

def setMaterial(ob, mat):
    """Attach a material to the object."""
    me = ob.data
    me.materials.append(mat)

def makeMaterialEmit(name): # dont believe this works
    """Create a default material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = {
        'Geometry': ['NEW_GEOMETRY', (-85.0, 598.0)],
        'Emission': ['EMISSION', (-111.0, 409.0)],
        'Diffuse BSDF': ['BSDF_DIFFUSE', (-116.0, 304.0)],
        'Mix Shader': ['MIX_SHADER', (193.0, 469.0)],
        'Material Output': ['OUTPUT_MATERIAL', (699.0, 435.0)],
        'Noise Texture': ['TEX_NOISE', (377.0, 299.0)]
    }
    for k, v in nodes.items():
        location = Vector(v[1])
        if not k in mat.node_tree.nodes:
            cur_node = mat.node_tree.nodes.new(v[0])
            cur_node.location = location
        else:
            mat.node_tree.nodes[k].location = location
    # from_node, from_socket, to_node, to_socket
    # unfortunately Mix Shader has two input nodes called 'Shader'
    # this means you have to assign to input index instead.
    link00 = ['Emission','Emission','Mix Shader','Shader']
    link01 = ['Mix Shader','Shader','Material Output','Surface']
    link02 = ['Diffuse BSDF','BSDF','Mix Shader','Shader']
    link03 = ['Geometry','Normal','Mix Shader','Fac']
    link04 = ['Noise Texture','Fac','Material Output','Displacement']
    links = [link00, link01, link02, link03, link04]
    node_target = 1
    for link in links:
        from_node = mat.node_tree.nodes[link[0]]
        output_socket = from_node.outputs[link[1]]
        to_node = mat.node_tree.nodes[link[2]]
        if link[0] in ['Emission', 'Diffuse BSDF']:
            input_socket = to_node.inputs[node_target]
            node_target += 1
        else:
            input_socket = to_node.inputs[link[3]]
        mat.node_tree.links.new(output_socket, input_socket)
    nodes = mat.node_tree.nodes
    node = nodes['Emission']
    node.inputs['Color'].default_value = (0.0, 1.0, 1.0, 1.0)
    node.inputs['Strength'].default_value = 0.5
    node = nodes['Diffuse BSDF']
    node.inputs['Color'].default_value = (1.0, 0.0, 0.0, 1.0)
    node.inputs['Roughness'].default_value = 0.0
    node = nodes['Noise Texture']
    node.inputs['Scale'].default_value = 5.0
    node.inputs['Detail'].default_value = 2.0
    node.inputs['Distortion'].default_value = 0.0
    return mat

def readStreamlines(filename, objname, mat): # unused
    # Read in the streamlines
    
    for item in bpy.data.objects:
        if item.name.startswith(objname):
            item.select = True
        else:
            item.select = False
    bpy.context.scene.objects.active = bpy.data.objects[objname]
    bpy.ops.object.join()
    bpy.data.objects[objname].data.bevel_depth = 0.5
    bpy.data.objects[objname].data.bevel_resolution = 10
    setMaterial(bpy.data.objects[objname], mat)

def run(filename, objectname, mat, cam):
    # Read in a tractfile
    if filename.endswith('.Bfloat'):
        streamlines = read_camino_streamlines(filename)
    elif filename.endswith('.vtk'):
        streamlines = read_vtk_streamlines(filename)
    # Create the polylines
    for streamline in streamlines:
        make_polyline(objectname, objectname, streamline)
    # Join the streamlines
    bpy.ops.object.select_all(action='DESELECT')
    for item in bpy.data.objects:
        if item.type == "CURVE":
            item.select = True
    bpy.context.scene.objects.active = bpy.data.objects[objectname]
    bpy.ops.object.join()
    bpy.data.objects[objectname].data.bevel_depth = 0.5
    bpy.data.objects[objectname].data.bevel_resolution = 10
    # Attach a material to the streamline object
    red = makeMaterial(mat[0], mat[1], mat[2], mat[3])
    setMaterial(bpy.data.objects[objectname], red)
    # Move the camera to into position
    obj = bpy.data.objects['Camera']
    obj.location = cam[0]
    obj.rotation_euler = cam[1]
    obj.data.clip_end = cam[2]
    # Create a plane (that emits some nice lighting)
    bpy.ops.mesh.primitive_plane_add(location = cam[0])
    bpy.context.active_object.scale = (100, 100, 100)
    bpy.context.active_object.rotation_euler = (0, radians(45), 0)
    #plem = makeMaterialEmit('PlaneEmitter')
    #setMaterial(bpy.context.active_object, plem)
    # Or move the lightbulb (for now)
    #obj = bpy.data.objects['Lamp']
    #obj.data.type = 'SUN'
    #obj.location = (150.0, 0.0, 100.0)
    # Render the scene
    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080
    (filepath, fileext) = os.path.splitext(filename)
    bpy.data.scenes['Scene'].render.filepath = filepath + '.png'
    bpy.ops.render.render( write_still=True )
    # And we're done
    return
 
if __name__ == "__main__":
    dirname = '/Users/michielk/oxdata/P99/BrainViz/Blender/streamlines'
    run(os.path.join(dirname, 'tracts_cc.Bfloat'), \
        'tracts_cc', ('red', (1,0,0), (1,1,1), 1), \
        ((150, -90, 60), (radians(90), radians(0), radians(90)), 1000))
    run(os.path.join(dirname, 'ttract.vtk'), \
        'ttract', ('green', (0,1,0), (1,1,1), 1), \
        ((150, -90, 60), (radians(90), radians(0), radians(90)), 1000))
