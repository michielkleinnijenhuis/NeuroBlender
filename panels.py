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


"""The NeuroBlender panels module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements drawing the NeuroBlender panels.
"""


import bpy


class NeuroBlenderBasePanel(bpy.types.Panel):
    """Host the NeuroBlender base geometry"""
    bl_idname = "OBJECT_PT_nb_basegeom"
    bl_label = "NeuroBlender - Base"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):

        scn = context.scene
        nb = scn.nb

        if nb.is_enabled:
            self.draw_nb_panel(context, self.layout)
            if nb.settingprops.switches:
                self.drawunit_switches(context, self.layout, nb)
        else:
            self.drawunit_switch_to_main(self.layout, nb)

    def drawunit_switches(self, context, layout, nb):

        scn = context.scene

        row = layout.row(align=True)
        row.alignment = 'RIGHT'
        props = [{'prop': 'mode',
                  'icons': {'artistic': 'VPAINT_HLT',
                            'scientific': 'RADIO'}},
                 {'prop': 'engine',
                  'icons': {'BLENDER_RENDER': 'NDOF_FLY',
                            'CYCLES': 'NDOF_TURN'}},
                 {'prop': 'verbose',
                  'icons': {True: 'SPEAKER',
                            False: 'FREEZE'}},
                 {'prop': 'advanced',
                  'icons': {True: 'DISCLOSURE_TRI_RIGHT',
                            False: 'DISCLOSURE_TRI_DOWN'}}]
        for prop in props:
            dpath = 'nb.settingprops.{}'.format(prop['prop'])
            propval = scn.path_resolve(dpath)
            icon = prop['icons'][propval]
            row.prop(nb.settingprops, prop['prop'], toggle=True,
                     icon_only=True, emboss=True, icon=icon)

    def draw_nb_panel(self, context, layout):

        scn = context.scene
        nb = scn.nb

        row = layout.row()
        row.prop(nb, "objecttype", expand=True)

        row = layout.row()
        row.separator()

        self.drawunit_UIList(layout, "L1", nb, nb.objecttype)

        row = layout.row()
        row.separator()

        try:
            idx = scn.path_resolve("nb.index_{}".format(nb.objecttype))
            nb_ob = scn.path_resolve("nb.{}[{:d}]".format(nb.objecttype, idx))
        except (IndexError, ValueError):
            pass
        else:
            self.drawunit_tri(layout, "carvers", nb, nb_ob)
            self.drawunit_tri(layout, "material", nb, nb_ob)
            self.drawunit_tri(layout, "transform", nb, nb_ob)
            if nb.settingprops.advanced:
                if nb.objecttype == "surfaces":
                    self.drawunit_tri(layout, "unwrap", nb, nb_ob)
                self.drawunit_tri(layout, "info", nb, nb_ob)

    def drawunit_switch_to_main(self, layout, nb):

        row = layout.row()
        row.label(text="Please use the main scene for NeuroBlender.")

        row = layout.row()
        row.operator("nb.switch_to_main",
                     text="Switch to main",
                     icon="FORWARD")

    def drawunit_UIList(self, layout, uilistlevel, data, obtype, addopt=True):

        scn = bpy.context.scene
        nb = scn.nb

        coll = scn.path_resolve('{}.{}'.format(data.path_from_id(), obtype))

        row = layout.row()
        row.template_list(
            "ObjectList" + uilistlevel, "",
            data, obtype,
            data, "index_" + obtype,
            rows=2
            )
        col = row.column(align=True)

        if addopt:
            rowsub = col.row()
            self.drawunit_addopt(rowsub, nb, uilistlevel, data, obtype)

        if len(coll):
            rowsub = col.row()
            rowsub.operator(
                "nb.oblist_ops",
                icon='ZOOMOUT',
                text=""
                ).action = 'REMOVE_' + uilistlevel

        if bpy.context.scene.nb.settingprops.advanced and (len(coll) > 1):

            rowsub = col.row()
            rowsub.menu(
                "nb.mass_is_rendered_" + uilistlevel,
                icon='DOWNARROW_HLT',
                text=""
                )

            rowsub = col.row()
            rowsub.separator()

            rowsub = col.row()
            rowsub.operator(
                "nb.oblist_ops",
                icon='TRIA_UP',
                text=""
                ).action = 'UP_' + uilistlevel
            rowsub = col.row()
            rowsub.operator(
                "nb.oblist_ops",
                icon='TRIA_DOWN',
                text=""
                ).action = 'DOWN_' + uilistlevel

    def drawunit_addopt(self, layout, nb, uilistlevel, data, obtype):

        if uilistlevel == "AN":
            operator = 'nb.animate_' + nb.animationtype
            layout.operator(
                operator,
                icon='ZOOMIN',
                text=""
                )
            if nb.animationtype == 'camerapath':
                try:
                    nb.presets[nb.index_presets]
                except IndexError:
                    layout.enabled = False
                else:
                    layout.enabled = True
            else:
                layout.enabled = True

            return

        if uilistlevel == "L2":
            if isinstance(data, bpy.types.VoxelvolumeProperties):
                operator = "nb.import_voxelvolumes"
                # TODO: move vvol overlay func to import_overlays.py
            else:
                operator = "nb.import_overlays"
        else:
            operator = "nb.import_" + obtype

        layout.operator(
            operator,
            icon='ZOOMIN',
            text=""
            ).parentpath = data.path_from_id()

    def drawunit_tri(self, layout, triflag, nb, data):

        scn = bpy.context.scene

        row = layout.row()
        prop = "show_{}".format(triflag)
        if scn.path_resolve("nb.{}".format(prop)):
            fun = eval("self.drawunit_tri_{}".format(triflag))
            fun(layout, nb, data)
            icon = 'TRIA_DOWN'
            row.prop(nb, prop, icon=icon, emboss=False)
            row = layout.row()
            row.separator()
        else:
            icon = 'TRIA_RIGHT'
            row.prop(nb, prop, icon=icon, emboss=False)

    def drawunit_tri_unwrap(self, layout, nb, nb_ob):

        self.drawunit_unwrap(layout, nb_ob)

    def drawunit_unwrap(self, layout, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "sphere", text="")
        row = layout.row()
        row.operator("nb.unwrap_surface", text="Unwrap from sphere")

    def drawunit_tri_carvers(self, layout, nb, nb_ob):

        self.drawunit_carvers(layout, nb_ob)

    def drawunit_carvers(self, layout, nb_ob):

        scn = bpy.context.scene
        nb = scn.nb

        self.drawunit_carver(layout, nb_ob)
        try:
            nb_ob.carvers[nb_ob.index_carvers]
        except IndexError:
            pass
        else:
            if nb.settingprops.advanced:
                self.drawunit_carveroptions(layout, nb_ob)
            self.drawunit_carverobjects(layout, nb_ob)

    def drawunit_carver(self, layout, nb_ob):

        row = layout.row()
        row.operator("nb.import_carvers", icon='ZOOMIN', text="")
        row.prop(nb_ob, "carvers_enum", text="")
        row.operator("nb.oblist_ops",
                     icon='ZOOMOUT',
                     text="").action = 'REMOVE_CV'
        row.enabled = not isinstance(nb_ob, bpy.types.TractProperties)

    def drawunit_carveroptions(self, layout, nb_ob):

        try:
            carver = nb_ob.carvers[nb_ob.carvers_enum]
#             ob = bpy.data.objects[nb_ob.name]
#             mod = ob.modifiers[carver.name]
        except KeyError:
            pass
        else:
            row = layout.row()
            row.prop(carver, "name")
#             row = layout.row()
#             row.prop(mod, "operation", expand=True)

        row = layout.row()
        row.separator()

    def drawunit_carverobjects(self, layout, nb_ob):

        scn = bpy.context.scene
        nb = scn.nb

        try:
            carver = nb_ob.carvers[nb_ob.carvers_enum]
        except KeyError:
            pass
        else:

            row = layout.row()
            row.prop(carver, "carveobject_type_enum", text="Carveobject type")

            self.drawunit_UIList(layout, "CO", carver,
                                 "carveobjects", addopt=True)

            try:
                nb_carveob = carver.carveobjects[carver.index_carveobjects]
                ob = bpy.data.objects[carver.name]
                mod = ob.modifiers[nb_carveob.name]
            except (NameError, IndexError, KeyError):
                pass
            else:
                if nb.settingprops.advanced:
                    row = layout.row()
                    row.prop(mod, "operation", expand=True)

                self.drawunit_carvers_tpa(layout, nb_carveob)

    def drawunit_carvers_tpa(self, layout, nb_ob):

        row = layout.row()
        col = row.column()
        col.prop(nb_ob, "slicethickness", expand=True, text="Thickness")
        col = row.column()
        col.prop(nb_ob, "sliceposition", expand=True, text="Position")
        col = row.column()
        col.prop(nb_ob, "sliceangle", expand=True, text="Angle")

    def drawunit_tri_material(self, layout, nb, nb_ob):

        if isinstance(nb_ob, bpy.types.VoxelvolumeProperties):
            self.drawunit_rendertype(layout, nb_ob)
            tex = bpy.data.textures[nb_ob.name]
            self.drawunit_texture(layout, tex, nb_ob)
        else:
            self.drawunit_material(layout, nb_ob)

    def drawunit_material(self, layout, nb_ob):

        scn = bpy.context.scene
        nb = scn.nb

        if nb.settingprops.engine.startswith("BLENDER"):

            self.drawunit_basic_blender(layout, nb_ob)

        else:

            if nb.settingprops.advanced:
                row = layout.row()
                row.prop(nb_ob, "colourtype", expand=True)

                row = layout.row()
                row.separator()

            self.drawunit_basic_cycles(layout, nb_ob)

    def drawunit_basic_blender(self, layout, nb_ob):

        mat = bpy.data.materials[nb_ob.name]

        row = layout.row(align=True)
        row.prop(mat, "diffuse_color", text="")
        row.prop(mat, "alpha", text="Transparency")
        if isinstance(nb_ob, (bpy.types.LabelProperties,
                              bpy.types.BorderProperties)):
            row.operator("nb.revert_label", icon='BACK', text="")

    def drawunit_basic_cycles(self, layout, nb_ob):

        scn = bpy.context.scene
        nb = scn.nb

        mat = bpy.data.materials[nb_ob.name]
        colour = mat.node_tree.nodes["RGB"].outputs[0]
        trans = mat.node_tree.nodes["Transparency"].outputs[0]

        row = layout.row(align=True)
        row.prop(colour, "default_value", text="")
        row.prop(trans, "default_value", text="Transparency")
        if isinstance(nb_ob, (bpy.types.LabelProperties,
                              bpy.types.BorderProperties)):
            row.operator("nb.revert_label", icon='BACK', text="")

        if nb.settingprops.advanced:
            self.drawunit_basic_cycles_mix(layout, mat)

    def drawunit_basic_cycles_mix(self, layout, mat):

        nt = mat.node_tree

        row = layout.row(align=True)
        row.prop(nt.nodes["Diffuse BSDF"].inputs[1],
                 "default_value", text="diffuse")
        row.prop(nt.nodes["Glossy BSDF"].inputs[1],
                 "default_value", text="glossy")
        row.prop(nt.nodes["MixDiffGlos"].inputs[0],
                 "default_value", text="mix")

    def drawunit_texture(self, layout, tex, nb_coll=None):

        scn = bpy.context.scene
        nb = scn.nb

        if nb.settingprops.advanced:
            if tex.type == 'VOXEL_DATA':
                row = layout.row()
                row.prop(tex.voxel_data, "interpolation")
                row = layout.row()
                row.separator()

            row = layout.row()
            row.prop(tex, "intensity")
            row.prop(tex, "contrast")
            row.prop(tex, "saturation")

            row = layout.row()
            row.separator()

            row = layout.row()
            row.prop(tex, "use_color_ramp", text="Ramp")

        if tex.use_color_ramp:

            row = layout.row()
            row.separator()

            self.drawunit_colourmap(layout, nb, tex, nb_coll)

            row = layout.row()
            row.separator()

            self.drawunit_colourramp(layout, tex, nb_coll)

        else:

            mat = bpy.data.materials[nb_coll.name]
            ts = mat.texture_slots.get(nb_coll.name)
            row.prop(ts, "color")

    def drawunit_colourmap(self, layout, nb, ramp, nb_coll):

        row = layout.row(align=True)
        row.prop(nb_coll, "colourmap_enum", expand=False)
        row.prop(nb, "cr_keeprange", toggle=True,
                 icon="ALIGN", icon_only=True)
        row.operator("nb.colourmap_presets", text="", icon='ZOOMIN')

    def drawunit_colourramp(self, layout, ramp, nb_coll=None):

        scn = bpy.context.scene
        nb = scn.nb

        row = layout.row()
        layout.template_color_ramp(ramp, "color_ramp", expand=True)

        if ((nb_coll is not None) and nb.settingprops.advanced):

            row = layout.row()
            row.separator()

            row = layout.row()
            row.label(text="non-normalized colour stop positions:")

            self.calc_nn_elpos(nb_coll, ramp)
            row = layout.row()
            row.enabled = False
            row.template_list("ObjectListCR", "",
                              nb_coll, "nn_elements",
                              nb_coll, "index_nn_elements",
                              rows=2)

            if hasattr(nb_coll, "showcolourbar"):

                row = layout.row()
                row.separator()

                row = layout.row()
                row.prop(nb_coll, "showcolourbar")

                if nb_coll.showcolourbar:

                    row = layout.row()
                    row.prop(nb_coll, "colourbar_size", text="size")
                    row.prop(nb_coll, "colourbar_position", text="position")

                    row = layout.row()
                    row.prop(nb_coll, "textlabel_colour", text="Textlabels")
                    row.prop(nb_coll, "textlabel_placement", text="")
                    row.prop(nb_coll, "textlabel_size", text="size")

    def calc_nn_elpos(self, nb_ov, ramp):
        """Calculate the non-normalized positions of elements."""

        def equalize_elements(nnels, n_els):
            """Prepare the listobject for displaying n_new elements."""

            n_nnels = len(nnels)

            if n_els > n_nnels:
                for _ in range(n_els - n_nnels):
                    nnels.add()
            elif n_els < n_nnels:
                for _ in range(n_nnels - n_els):
                    nnels.remove(0)

        els = ramp.color_ramp.elements
        nnels = nb_ov.nn_elements

        equalize_elements(nnels, len(els))

        for i, el in enumerate(nnels):
            el.calc_nn_position(els[i].position, nb_ov.range)

    def drawunit_rendertype(self, layout, nb_ob):

        scn = bpy.context.scene
        nb = scn.nb

        row = layout.row()
        row.prop(nb_ob, "rendertype", expand=True)

        row = layout.row()
        row.separator()

        if nb.settingprops.advanced and (nb_ob.rendertype == "SURFACE"):
            mat = bpy.data.materials[nb_ob.name]
            row = layout.row()
            row.prop(mat, "alpha", text="Carvebox alpha")

    def drawunit_tri_transform(self, layout, nb, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "sformfile", text="")

        if nb.settingprops.advanced:
            ob = bpy.data.objects[nb_ob.name]
            row = layout.row()
            col = row.column()
            col.prop(ob, "matrix_world")

    def drawunit_tri_info(self, layout, nb, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "filepath")
        row.enabled = False

        infofun = eval('self.drawunit_info_{}'.format(nb.objecttype))
        infofun(layout, nb_ob)

    def drawunit_info_tracts(self, layout, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "nstreamlines",
                 text="Number of streamlines", emboss=False)
        row.enabled = False

        row = layout.row()
        row.prop(nb_ob, "streamlines_interpolated",
                 text="Interpolation factor", emboss=False)
        row.enabled = False

        row = layout.row()
        row.prop(nb_ob, "tract_weeded",
                 text="Tract weeding factor", emboss=False)
        row.enabled = False

    def drawunit_info_surfaces(self, layout, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "is_unwrapped",
                 text="Has the surface been unwrapped?", emboss=False)
        row.enabled = False

    def drawunit_info_voxelvolumes(self, layout, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "texdir")

        row = layout.row()
        row.prop(nb_ob, "texformat")
        row.enabled = False

        row = layout.row()
        row.prop(nb_ob, "range", text="Datarange", emboss=False)
        row.enabled = False

        row = layout.row()
        row.prop(nb_ob, "dimensions", text="Dimensions", emboss=False)
        row.enabled = False


class NeuroBlenderOverlayPanel(bpy.types.Panel):
    """Host the NeuroBlender overlay functions"""
    bl_idname = "OBJECT_PT_nb_overlays"
    bl_label = "NeuroBlender - Overlays"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = NeuroBlenderBasePanel.draw
    drawunit_switches = NeuroBlenderBasePanel.drawunit_switches
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = NeuroBlenderBasePanel.drawunit_UIList
    drawunit_addopt = NeuroBlenderBasePanel.drawunit_addopt
    drawunit_tri = NeuroBlenderBasePanel.drawunit_tri
    drawunit_basic_blender = NeuroBlenderBasePanel.drawunit_basic_blender
    drawunit_basic_cycles = NeuroBlenderBasePanel.drawunit_basic_cycles
    drawunit_basic_cycles_mix = NeuroBlenderBasePanel.drawunit_basic_cycles_mix
    drawunit_rendertype = NeuroBlenderBasePanel.drawunit_rendertype
    drawunit_texture = NeuroBlenderBasePanel.drawunit_texture
    calc_nn_elpos = NeuroBlenderBasePanel.calc_nn_elpos
    drawunit_colourmap = NeuroBlenderBasePanel.drawunit_colourmap
    drawunit_colourramp = NeuroBlenderBasePanel.drawunit_colourramp

    def draw_nb_panel(self, context, layout):

        scn = context.scene
        nb = scn.nb

        try:
            idx = scn.path_resolve("nb.index_{}".format(nb.objecttype))
            nb_ob = scn.path_resolve("nb.{}[{:d}]".format(nb.objecttype, idx))
        except (IndexError, ValueError):
            row = self.layout.row()
            row.label(text="No {} loaded ...".format(nb.objecttype))
        else:
            self.draw_nb_overlaypanel(layout, nb, nb_ob)

    def draw_nb_overlaypanel(self, layout, nb, nb_ob):

        scn = bpy.context.scene
        nb = scn.nb

        row = layout.row()
        row.prop(nb, "overlaytype", expand=True)

        row = layout.row()
        row.separator()

        self.drawunit_UIList(layout, "L2", nb_ob, nb.overlaytype)

        row = layout.row()
        row.separator()

        try:
            dpath = nb_ob.path_from_id()
            ovtype = nb.overlaytype
            idx = scn.path_resolve("{}.index_{}".format(dpath, ovtype))
            nb_ov = scn.path_resolve("{}.{}[{:d}]".format(dpath, ovtype, idx))
        except (IndexError, ValueError):
            pass
        else:
            self.draw_nb_overlayprops(layout, nb, nb_ob, nb_ov)

    def draw_nb_overlayprops(self, layout, nb, nb_ob, nb_ov):

        if nb.overlaytype == "scalargroups":

            # (time)series
            if len(nb_ov.scalars) > 1:
                row = layout.row()
                row.template_list("ObjectListTS", "",
                                  nb_ov, "scalars",
                                  nb_ov, "index_scalars",
                                  rows=2, type="COMPACT")

            # texture baking
            if nb.objecttype == 'surfaces':
                self.drawunit_bake(layout, nb_ob)

            self.drawunit_tri(layout, "overlay_material", nb, nb_ov)

        else:

            self.drawunit_tri(layout, "items", nb, nb_ov)

        if nb.settingprops.advanced:
            self.drawunit_tri(layout, "overlay_info", nb, nb_ov)

    def drawunit_bake(self, layout, nb_ob):

        row = layout.row()
        row.separator()

        scn = bpy.context.scene
        nb = scn.nb

        row = layout.row()
        col = row.column()
        col.operator("nb.wp_preview", text="", icon="GROUP_VERTEX")
        col = row.column()
        col.operator("nb.vw2vc", text="", icon="GROUP_VCOL")
        col = row.column()
        col.operator("nb.vw2uv", text="", icon="GROUP_UVS")
        col.enabled = nb_ob.is_unwrapped
        col = row.column()
        col.prop(nb.settingprops, "uv_bakeall", toggle=True)
        col.enabled = nb_ob.is_unwrapped

        row = layout.row()
        row.separator()

    def drawunit_tri_overlay_material(self, layout, nb, nb_ov):

        scn = bpy.context.scene
        nb = scn.nb

        if nb.objecttype == "tracts":

            ng = bpy.data.node_groups.get("TractOvGroup.{}".format(nb_ov.name))
            ramp = ng.nodes["ColorRamp"]

            self.drawunit_colourmap(layout, nb, ramp, nb_ov)

            row = layout.row()
            row.separator()

            self.drawunit_colourramp(layout, ramp, nb_ov)

        elif nb.objecttype == "surfaces":

            mat = bpy.data.materials[nb_ov.name]
            ramp = mat.node_tree.nodes["ColorRamp"]

            self.drawunit_colourmap(layout, nb, ramp, nb_ov)

            row = layout.row()
            row.separator()

            self.drawunit_colourramp(layout, ramp, nb_ov)

            row = layout.row()
            row.separator()

            self.drawunit_basic_cycles_mix(layout, mat)

        elif nb.objecttype == "voxelvolumes":

            itemtype = nb.overlaytype.replace("groups", "s")
            item = eval("nb_ov.{0}[nb_ov.index_{0}]".format(itemtype))
            dpath = nb_ov.path_from_id()
#             item = scn.path_resolve("{0}.{1}[{0}.index_{1}]".format(dpath, itemtype))

            parentpath = '.'.join(dpath.split('.')[:-1])
            nb_parent = bpy.context.scene.path_resolve(parentpath)
            mat = bpy.data.materials[nb_parent.name]
            ts = mat.texture_slots.get(nb_ov.name)

            # TODO: texture mixing options and reorder textures from NB
            row = layout.row()
            row.prop(ts, "blend_type")

            self.drawunit_texture(layout, ts.texture, nb_ov)

    def drawunit_tri_items(self, layout, nb, nb_ov):

        scn = bpy.context.scene
        nb = scn.nb

        itemtype = nb.overlaytype.replace("groups", "s")

        if nb.objecttype == "voxelvolumes":

            dpath = nb_ov.path_from_id()
            parentpath = '.'.join(dpath.split('.')[:-1])
            nb_parent = bpy.context.scene.path_resolve(parentpath)
            mat = bpy.data.materials[nb_parent.name]

            if nb.settingprops.advanced:
                ts = mat.texture_slots.get(nb_ov.name)
                row = layout.row()
                row.prop(ts, "emission_factor")
                row.prop(ts, "emission_color_factor")

        self.drawunit_UIList(layout, "L3", nb_ov, itemtype, addopt=False)

        self.drawunit_tri(layout, "itemprops", nb, nb_ov)
#         if itemtype == "labels":
#             if len(nb_ov.labels) < 33:  # TODO: proper method
#                 self.drawunit_tri(layout, "itemprops", nb, nb_ov)
#             else:
#                 self.drawunit_tri(layout, "overlay_material", nb, nb_ov)
#         else:
#             self.drawunit_tri(layout, "itemprops", nb, nb_ov)

    def drawunit_tri_itemprops(self, layout, nb, nb_ov):

        scn = bpy.context.scene
        nb = scn.nb

        try:
            # TODO: make label panel code less convoluted
            dpath = nb_ov.path_from_id()
            itemtype = nb.overlaytype.replace("groups", "s")
            idx = scn.path_resolve("{}.index_{}".format(dpath, itemtype))
            data = scn.path_resolve("{}.{}[{:d}]".format(dpath, itemtype, idx))
        except (IndexError, ValueError):
            pass
        else:
            drawfun = eval('self.drawunit_{}'.format(itemtype))
            drawfun(layout, nb, data)

    def drawunit_labels(self, layout, nb, nb_ov):

        if nb.objecttype == "voxelvolumes":

            dpath = nb_ov.path_from_id()
            parentpath = '.'.join(dpath.split('.')[:-1])
            nb_parent = bpy.context.scene.path_resolve(parentpath)
            tex = bpy.data.textures[nb_parent.name]

            el = tex.color_ramp.elements[nb_parent.index_labels + 1]
            row = layout.row()
            row.prop(el, "color", text="")

        else:

            if nb.settingprops.engine.startswith("BLENDER"):
                self.drawunit_basic_blender(layout, nb_ov)
            else:
                self.drawunit_basic_cycles(layout, nb_ov)

    def drawunit_borders(self, layout, nb, item):

        self.drawunit_basic_cycles(layout, item)

        row = layout.row()
        row.separator()

        ob = bpy.data.objects[item.name]

        row = layout.row()
        row.label(text="Smoothing:")
        row.prop(ob.modifiers["smooth"], "factor")
        row.prop(ob.modifiers["smooth"], "iterations")

        row = layout.row()
        row.label(text="Bevel:")
        row.prop(ob.data, "bevel_depth")
        row.prop(ob.data, "bevel_resolution")

    def drawunit_tri_overlay_info(self, layout, nb, nb_ov):

        row = layout.row()
        row.prop(nb_ov, "filepath")
        row.enabled = False

        if nb.overlaytype == "scalargroups":

            row = layout.row()
            row.prop(nb_ov, "texdir")

            row = layout.row()
            row.enabled = False  # TODO: option to change range?
#             (and revert it by getting it from file)
            row.prop(nb_ov, "range")


class NeuroBlenderScenePanel(bpy.types.Panel):
    """Host the NeuroBlender scene setup functionality"""
    bl_idname = "OBJECT_PT_nb_scene"
    bl_label = "NeuroBlender - Scene setup"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = NeuroBlenderBasePanel.draw
    drawunit_switches = NeuroBlenderBasePanel.drawunit_switches
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = NeuroBlenderBasePanel.drawunit_UIList
    drawunit_addopt = NeuroBlenderBasePanel.drawunit_addopt
    drawunit_tri = NeuroBlenderBasePanel.drawunit_tri
    drawunit_basic_cycles = NeuroBlenderBasePanel.drawunit_basic_cycles
    drawunit_basic_cycles_mix = NeuroBlenderBasePanel.drawunit_basic_cycles_mix

    def draw_nb_panel(self, context, layout):

        scn = context.scene
        nb = scn.nb

        self.drawunit_presets(layout, nb)

        try:
            idx = nb.index_presets
            preset = nb.presets[idx]
        except IndexError:
            pass
        else:
            row = layout.row()
            row.prop(preset, "name")

            row = layout.row()
            row.separator()

            self.drawunit_tri(layout, "cameras", nb, preset)
            self.drawunit_tri(layout, "lights", nb, preset)
            self.drawunit_tri(layout, "tables", nb, preset)
            self.drawunit_tri(layout, "bounds", nb, preset)

    def drawunit_presets(self, layout, nb):

        row = layout.row()
        row.operator("nb.add_preset", icon='ZOOMIN', text="")
        row.prop(nb, "presets_enum", expand=False, text="")
        row.operator("nb.del_preset", icon='ZOOMOUT', text="")

    def drawunit_tri_cameras(self, layout, nb, preset):

        try:
            cam = preset.cameras[preset.index_cameras]
            # TODO: multiple cameras in a preset
        except IndexError:
            cam = preset.cameras.add()
            preset.index_cameras = (len(preset.cameras)-1)
        else:
            cam_ob = bpy.data.objects[cam.name]

            row = layout.row()

            split = row.split(percentage=0.55)
            col = split.column(align=True)
            col.label("Quick camera view:")
            row1 = col.row(align=True)
            row1.prop(cam, "cam_view_enum_LR", expand=True)
            row1 = col.row(align=True)
            row1.prop(cam, "cam_view_enum_AP", expand=True)
            row1 = col.row(align=True)
            row1.prop(cam, "cam_view_enum_IS", expand=True)

            col.prop(cam, "cam_distance", text="distance")

            split = split.split(percentage=0.1)
            col = split.column()
            col.separator()

            col = split.column(align=True)
            col.prop(cam_ob, "location", index=-1)

            row = layout.row()
            row.separator()

            if nb.settingprops.advanced:
                row = layout.row()

                split = row.split(percentage=0.55)
                col = split.column(align=True)
                col.label(text="Track object:")
                col.prop(cam, "trackobject", text="")
                if cam.trackobject == "None":
                    col.prop(cam_ob, "rotation_euler", index=2, text="tumble")

                split = split.split(percentage=0.1)
                col = split.column()
                col.separator()

                camdata = cam_ob.data
                col = split.column(align=True)
                col.label(text="Clipping:")
                col.prop(camdata, "clip_start", text="Start")
                col.prop(camdata, "clip_end", text="End")

    def drawunit_tri_lights(self, layout, nb, preset):

        lights = bpy.data.objects[preset.lightsempty]
        row = layout.row(align=True)
        col = row.column(align=True)
        col.prop(lights, "rotation_euler", index=2, text="Rotate rig (Z)")
        col = row.column(align=True)
        col.prop(lights, "scale", index=2, text="Scale rig (XYZ)")

        row = layout.row()
        row.separator()

        self.drawunit_UIList(layout, "PL", preset, "lights", addopt=True)
        self.drawunit_lightprops(layout, preset.lights[preset.index_lights])

    def drawunit_lightprops(self, layout, light):

        light_ob = bpy.data.objects[light.name]

        row = layout.row()

        split = row.split(percentage=0.55)
        col = split.column(align=True)
        col.label("Quick access:")
        col.prop(light, "type", text="")
        col.prop(light, "strength")
        if light.type == "PLANE":
            row = col.row(align=True)
            row.prop(light, "size", text="")

        split = split.split(percentage=0.1)
        col = split.column()
        col.separator()

        col = split.column(align=True)
        col.prop(light_ob, "location")

    def drawunit_tri_tables(self, layout, nb, preset):

        try:
            tab = preset.tables[0]
        except IndexError:
            tab = preset.tables.add()
            preset.index_tables = (len(preset.tables)-1)
        else:
            row = layout.row()
            row.prop(tab, "is_rendered", toggle=True)
            row = layout.row()
            self.drawunit_basic_cycles(layout, tab)

    def drawunit_tri_bounds(self, layout, nb, preset):

        preset_ob = bpy.data.objects[preset.centre]

        row = layout.row()
        props = [{'prop': 'location',
                  'op': "nb.reset_presetcentre",
                  'text': 'Recentre'},
                 {'prop': 'scale',
                  'op': "nb.reset_presetdims",
                  'text': 'Rescale'}]
        for propdict in props:
            col = row.column()
            row1 = col.row()
            row1.operator(propdict['op'], icon='BACK', text=propdict['text'])
            if nb.settingprops.advanced:
                row1 = col.row()
                col1 = row1.column()
                col1.prop(preset_ob, propdict['prop'])


class NeuroBlenderAnimationPanel(bpy.types.Panel):
    """Host the NeuroBlender animation functionality"""
    bl_idname = "OBJECT_PT_nb_animation"
    bl_label = "NeuroBlender - Animations"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = NeuroBlenderBasePanel.draw
    drawunit_switches = NeuroBlenderBasePanel.drawunit_switches
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = NeuroBlenderBasePanel.drawunit_UIList
    drawunit_addopt = NeuroBlenderBasePanel.drawunit_addopt
    drawunit_tri = NeuroBlenderBasePanel.drawunit_tri

    def draw_nb_panel(self, context, layout):

        scn = context.scene
        nb = scn.nb

        row = layout.row(align=True)
        row.prop(bpy.context.scene, "frame_start")
        row.prop(bpy.context.scene, "frame_end")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(nb, "animationtype", expand=True)

        row = layout.row()
        self.drawunit_UIList(layout, "AN", nb, "animations")

        try:
            anim = nb.animations[nb.index_animations]
        except IndexError:
            pass
        else:
            row = layout.row()
            row.separator()

            self.drawunit_tri(layout, "timings", nb, nb)

            animtype = anim.animationtype
            drawfun = eval('self.drawunit_animation_{}'.format(animtype))
            drawfun(layout, nb)

    def drawunit_tri_timings(self, layout, nb, dummy):

        self.drawunit_animation_timings(layout, nb)

    def drawunit_animation_timings(self, layout, nb):

        anim = nb.animations[nb.index_animations]

        row = layout.row(align=True)
        row.prop(anim, "frame_start")
        row.prop(anim, "frame_end")

        row = layout.row(align=True)
        row.prop(anim, "repetitions")
        row.prop(anim, "offset")

    def drawunit_animation_camerapath(self, layout, nb):

        try:
            preset = nb.presets[nb.index_presets]
        except IndexError:
            row = layout.row()
            row.label('No presets (cameras) loaded.')
        else:
            self.drawunit_tri(layout, "camerapath", nb, preset)
            self.drawunit_tri(layout, "tracking", nb, preset)

    def drawunit_tri_camerapath(self, layout, nb, preset):

        self.drawunit_camerapath(layout, nb, preset)

    def drawunit_camerapath(self, layout, nb, preset):

        anim = nb.animations[nb.index_animations]

        # TODO: rewrite of campath options
        row = layout.row()
        col = row.column()
        col.prop(anim, "reverse", toggle=True,
                 icon="ARROW_LEFTRIGHT", icon_only=True)
        col = row.column()
        col.prop(anim, "campaths_enum", expand=False, text="")
        col = row.column()
        col.operator("nb.del_campath", icon='ZOOMOUT', text="")
        col.enabled = True

        row = layout.row()
        row.separator()

        box = layout.box()
        self.drawunit_tri(box, "newpath", nb, anim)

        if nb.settingprops.advanced and (anim.campaths_enum != "No_CamPaths"):
            self.drawunit_tri(box, "points", nb, anim)

    def drawunit_tri_tracking(self, layout, nb, preset):

        self.drawunit_tracking(layout, nb, preset)

    def drawunit_tracking(self, layout, nb, preset):

        anim = nb.animations[nb.index_animations]

        nb_cam = preset.cameras[preset.index_cameras]
        cam_ob = bpy.data.objects[nb_cam.name]

        row = layout.row()
        row.prop(anim, "tracktype", expand=True)

        if nb.settingprops.advanced:

            row.separator()
            row = layout.row()

            split = layout.split(percentage=0.33)
            col = split.column()
            col.prop(cam_ob, "rotation_euler", index=2, text="tumble")
            col.enabled = anim.tracktype != "TrackObject"

            col = split.column()
            row = col.row(align=True)
            row.prop(cam_ob.data, "clip_start")
            row.prop(cam_ob.data, "clip_end")

    def drawunit_tri_points(self, layout, nb, anim):

        row = layout.row()
        row.operator("nb.add_campoint",
                     text="Add point at camera position")

        try:
            cu = bpy.data.objects[anim.campaths_enum].data
            data = cu.splines[0]
        except:
            pass
        else:
            if len(data.bezier_points):
                ps = "bezier_points"
            else:
                ps = "points"

            row = layout.row()
            row.template_list("ObjectListCP", "",
                              data, ps,
                              data, "material_index", rows=2,
                              maxrows=4, type="DEFAULT")

    def drawunit_tri_newpath(self, layout, nb, anim):

        row = layout.row()
        row.prop(anim, "pathtype", expand=True)

        row = layout.row()
        if anim.pathtype == 'Circular':
            row = layout.row()
            row.prop(anim, "axis", expand=True)
        elif anim.pathtype == 'Streamline':
            row = layout.row()
            row.prop(anim, "anim_tract", text="")
            row.prop(anim, "spline_index")
        elif anim.pathtype == 'Select':
            row = layout.row()
            row.prop(anim, "anim_curve", text="")
        elif anim.pathtype == 'Create':
            pass  # TODO: name, for every option?

        row = layout.row()
        row.separator()

        row = layout.row()
        row.operator("nb.add_campath", text="Add trajectory")

    def drawunit_animation_carver(self, layout, nb):

        self.drawunit_tri(layout, "carvers", nb, nb)

    def drawunit_tri_carvers(self, layout, nb, preset):

        anim = nb.animations[nb.index_animations]

        row = layout.row()
        col = row.column()
        col.prop(anim, "reverse", toggle=True,
                 icon="ARROW_LEFTRIGHT", icon_only=True)
        col = row.column()
        col.prop(anim, "nb_object_data_path", expand=False, text="")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(anim, "sliceproperty", expand=True)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(anim, "axis", expand=True)

    def drawunit_animation_timeseries(self, layout, nb):

        self.drawunit_tri(layout, "timeseries", nb, nb)

    def drawunit_tri_timeseries(self, layout, nb, dummy):

        anim = nb.animations[nb.index_animations]

        row = layout.row()
        col = row.column()
        col.prop(anim, "reverse", toggle=True,
                 icon="ARROW_LEFTRIGHT", icon_only=True)
        col = row.column()
        col.prop(anim, "nb_object_data_path", expand=False, text="")


class NeuroBlenderSettingsPanel(bpy.types.Panel):
    """Host the NeuroBlender settings"""
    bl_idname = "OBJECT_PT_nb_settings"
    bl_label = "NeuroBlender - Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = NeuroBlenderBasePanel.draw
    drawunit_switches = NeuroBlenderBasePanel.drawunit_switches
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main
    drawunit_tri = NeuroBlenderBasePanel.drawunit_tri

    def draw_nb_panel(self, context, layout):

        scn = context.scene
        nb = scn.nb

        settingprops = nb.settingprops

        self.drawunit_settings_preset(layout)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(settingprops, "projectdir")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(settingprops, "esp_path")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(settingprops, "mode", expand=True)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(settingprops, "engine", expand=True)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(settingprops, "verbose", toggle=True)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(settingprops, "advanced", toggle=True)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(settingprops, "switches", expand=True)

        row = layout.row()
        row.separator()

        self.drawunit_tri(layout, "texture_preferences", nb, data=None)

        self.drawunit_tri(layout, "manage_colourmaps", nb, data=None)

    def drawunit_settings_preset(self, layout):

        menu_name = 'OBJECT_MT_setting_presets'
        label = bpy.context.scene.nb.settingprops.sp_presetlabel
        preset_op_name = "nb.setting_presets"

        self.drawunit_presetmenu(layout, menu_name, label, preset_op_name)

    def drawunit_presetmenu(self, layout, menu_name, label, preset_op):

        row = layout.row(align=True)
        row.menu(menu_name, text=label)
        # FIXME: change the label on create or remove
        row.operator(preset_op, text="", icon='ZOOMIN')
        row.operator(preset_op, text="", icon='ZOOMOUT').remove_active = True

    def drawunit_tri_texture_preferences(self, layout, nb, data):

        row = layout.row()
        row.prop(nb.settingprops, "texformat")
        row = layout.row()
        row.prop(nb.settingprops, "texmethod")
        row = layout.row()
        row.prop(nb.settingprops, "uv_resolution")

    def drawunit_tri_manage_colourmaps(self, layout, nb, data):

        self.drawunit_manage_colourmaps(layout, nb)

    def drawunit_manage_colourmaps(self, layout, nb):

        menu_name = 'OBJECT_MT_colourmap_presets'
        label = bpy.context.scene.nb.cm_presetlabel
        preset_op_name = "nb.colourmap_presets"

        self.drawunit_presetmenu(layout, menu_name, label, preset_op_name)

        name = 'manage_colourmaps'

        try:
            mat = bpy.data.materials[name]
            ts = getattr(mat, "texture_slot", None)
            tex = bpy.data.textures[name]
        except KeyError:
            pass
        else:
            layout.template_color_ramp(tex, "color_ramp", expand=True)
            layout.separator()
            layout.template_preview(tex, parent=mat, slot=ts)
            layout.separator()
            layout.operator("nb.reset_colourmaps")
