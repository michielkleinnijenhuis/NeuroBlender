#!/usr/bin/env python2

import os
import sys
from argparse import ArgumentParser
import pickle
import errno

import vtk
import numpy as np
import nibabel as nib


def main(argv):

    parser = ArgumentParser(description='...')
    parser.add_argument('labelimages', default=[], nargs='+',
                        help='path to labelimage(s)')
    parser.add_argument('-l', '--lookuptable', default="",
                        help='path to pickled lookup table')
    args = parser.parse_args()
    labelimages = args.labelimages
    lutpickle = args.lookuptable

    for labelimage in labelimages:

        basepath, ext = os.path.splitext(labelimage)
        if ext == '.gz':
            basepath = os.path.splitext(basepath)[0]

        print(basepath, ext)
        labeldata, affine = read_labelimage_nii(labelimage)
        labels = np.unique(labeldata)
        labels = np.delete(labels, 0)

        try:
            with open(lutpickle, "rb") as f:
                lut = pickle.load(f)
        except:
            lut = {l: {'name': 'label.{:05d}'.format(l)} for l in labels}

        mkdir_p(basepath)
        labels2meshes_vtk(basepath, lut, labeldata, labels,
                          spacing=[1, 1, 1], offset=[0, 0, 0])

        np.save(os.path.join(basepath, 'affine'), affine)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def read_labelimage_nii(labelimage):
    """Get labeldata and spacing from nifti file."""

    img = nib.load(labelimage)
    labeldata = img.get_data()
    hdr = img.get_header()
    affine = hdr.get_best_affine()
#     spacing = hdr.get_zooms()
#     offset = [affine[0][3], affine()[1][3], affine()[2][3]]

    return labeldata, affine  # spacing, offset


def labels2meshes_vtk(surfdir, compdict, labelimage, labels=[],
                      spacing=[1, 1, 1], offset=[0, 0, 0]):
    """Generate meshes from a labelimage with vtk marching cubes."""

    labelimage = np.lib.pad(labelimage.tolist(),
                            ((1, 1), (1, 1), (1, 1)),
                            'constant')
    dims = labelimage.shape

    vol = vtk.vtkImageData()
    vol.SetDimensions(dims[0], dims[1], dims[2])
    vol.SetOrigin(offset[0] * spacing[0] + spacing[0],
                  offset[1] * spacing[1] + spacing[1],
                  offset[2] * spacing[2] + spacing[2])
    # vol.SetOrigin(0, 0, 0)
    vol.SetSpacing(spacing[0], spacing[1], spacing[2])

    sc = vtk.vtkFloatArray()
    sc.SetNumberOfValues(labelimage.size)
    sc.SetNumberOfComponents(1)
    sc.SetName('tnf')
    for ii, val in enumerate(np.ravel(labelimage.swapaxes(0, 2))):
        # FIXME: why swapaxes??? zyx => xyz?
        sc.SetValue(ii, val)
    vol.GetPointData().SetScalars(sc)

    dmc = vtk.vtkDiscreteMarchingCubes()
    dmc.SetInput(vol)
    dmc.ComputeNormalsOn()

    for label in labels:
        try:
            labelname = compdict[label]['name']
        except (IndexError, KeyError):
            print("Skipping label {:05d}".format(label))
        else:
            fpath = os.path.join(surfdir, '{}.stl'.format(labelname))
            print("Processing label {:05d} ({})".format(label, labelname))
            dmc.SetValue(0, label)
            dmc.Update()

            writer = vtk.vtkSTLWriter()
            writer.SetInputConnection(dmc.GetOutputPort())
            writer.SetFileName(fpath)
            writer.Write()


if __name__ == "__main__":
    main(sys.argv)
