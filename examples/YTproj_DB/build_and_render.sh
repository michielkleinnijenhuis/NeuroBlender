NBdir="/Users/michielk/workspace/NeuroBlender"
datadir="/Users/michielk/oxdox/brainart/YTproj_DB"
scenename="YTproj_DB"
blender -b -P $NBdir/examples/YTproj_DB/$scenename.py  # $datadir/${scenename}_scn.blend -a

# TODO: this would need blender as a python module!
# python $NBdir/examples/YTproj_DB/$scenename.py

# TODO: could do a subprocess call here instead

# could this all be done in a jupyter notebook?
