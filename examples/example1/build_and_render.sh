NBdir="/Users/michielk/workspace/NeuroBlender"
scenename="example1"
datadir = "/Users/michielk/workspace/NeuroBlender/examples/example1/data"
blender -b -P $NBdir/examples/example1/example1.py -- $datadir
blender -b $datadir/example1_scn.blend -a
