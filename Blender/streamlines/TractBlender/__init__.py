bl_info = {
    "name": "Tractography Visualisation",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 3),
    "blender": (2, 77, 0),
    "location": "Properties -> Scene -> Import Tractography Streamlines",
    "description": "visualising tractography results",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}
#============================================================================#

import os
import bpy
from . import tract_import

def initialize():
    """Perform initialization steps for the add-on."""
    define_tractblender_properties()
#     import_materials()  # FIXME: throws error

def define_tractblender_properties():
    """Set properties for the panel."""
    bpy.types.Scene.tract_name = bpy.props.StringProperty \
        (
        name = "Tract name",
        description = "Specify a name for the tract \
                       [Object > Name]",
        default = ''
        )
    bpy.types.Scene.tract_scale = bpy.props.FloatProperty \
        (
        name = "Scale",
        description = "Resize the tracts \
                       [Object > Transform > Scale]",
        default = 1.0,
        min = 1e-10,
        precision = 4
        )
    bpy.types.Scene.tract_bevel = bpy.props.BoolProperty \
        (
        name = "Bevel streamlines",
        description = "Apply initial bevel on the curves \
                       [Curve > Geometry > Bevel]",
        default = True
        )
    bpy.types.Scene.tract_colourtype = bpy.props.EnumProperty \
        (
        name = "", 
        description = "Choose a tract colouring method \
                       [Material > Surface]", 
        default = 'random', 
        items = [('default', 'default', '', 1), 
                 ('primary6', 'primary6', '', 2), 
                 ('random', 'random', '', 3), 
                 ('directional', 'directional', '', 4), 
                 ('brainbow', 'brainbow', '', 5), 
                 ('pick', 'pick', '', 6)
                ],
        )
    bpy.types.Scene.tract_colourpicker = bpy.props.FloatVectorProperty \
        (
        name = "", 
        description = "Pick a colour for the tract(s)", 
        default = [1.0,0.0,0.0], 
        subtype = "COLOR", 
        )
    bpy.types.Scene.tract_count = bpy.props.IntProperty \
        (
        name = "Tract count",
        description = "The number of loaded tracts",
        default = 0,
        min = 0,
        )
    # submenu: solid color/rgb, smooth, texture,

def register():
    bpy.utils.register_module(__name__)
    initialize()
        
def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.Scene.tract_name
    bpy.types.Scene.tract_scale
    bpy.types.Scene.tract_bevel
    bpy.types.Scene.tract_colourtype
    bpy.types.Scene.tract_colourpicker
    bpy.types.Scene.tract_count

if __name__ == "__main__":
    register()
