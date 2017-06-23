# NeuroBlender
a Blender add-on for creating neuroscience artwork

## Getting Started

### Prerequisites
- Blender (tested on 2.78.4)
- nibabel (for reading nifti and gifti)

### Installation
Install from zipped package:
1. download NeuroBlender.zip
2. open Blender User Preferences
3. Click 'Install add-on from file' and browse to NeuroBlender.zip
4. Under 'Import-Export' check NeuroBlender to activate the addon
5. install nibabel in Blender (https://github.com/nipy/nibabel)
- e.g. using a conda environment:
```
conda create --name blender python=3.5.1
source activate blender
pip install git+git://github.com/nipy/nibabel.git@master
```
In the NeuroBlender Settings panel, set External site-packages to 
<conda root dir>/envs/blender/lib/python3.5/site-packages
```
nb = bpy.context.scene.nb
nb.settingprops.esp_path = <conda root dir>/envs/blender/lib/python3.5/site-packages
```
Note: It's convenient to save this by creating a NeuroBlender Settings Preset or saving the Blender Startup File
