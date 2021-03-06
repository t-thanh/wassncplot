
from netCDF4 import Dataset
import numpy as np
import scipy.io as sio
import cv2 as cv
from WaveFieldVisualize.waveview2 import WaveView
from tqdm import tqdm
import sys
import os
import argparse
import glob
import scipy.io





if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("ncfile", help="Input NetCDF4 file")
    parser.add_argument("out", help="Where to store the produced images")
    parser.add_argument("-f", "--first_index", default=0, type=int, help="First data index to process")
    parser.add_argument("-l", "--last_index", default=-1, type=int, help="Last data index to process (-1 to process all the frames)")
    parser.add_argument("-s", "--step_index", default=1, type=int, help="Sequence step")
    parser.add_argument("-sd", "--step_data_index", default=1, type=int, help="Sequence data step")
    parser.add_argument("-b", "--baseline", type=float, help="Baseline of the stereo system (use this option to override the baseline value stored in the netcdf file)")
    parser.add_argument("--zmin", default=-3, type=float, help="Minimum 3D point elevation (used for colorbar limits)")
    parser.add_argument("--zmax", default=+3, type=float, help="Maximum 3D point elevation (used for colorbar limits)")
    parser.add_argument("--alpha", default=0.5, type=float, help="Surface transparency [0..1]")
    parser.add_argument("--pxscale", default=1.0, type=float, help="Desktop pixel scale (set to 0.5 if using OSX with retina display)")
    parser.add_argument("--wireframe", dest="wireframe", action="store_true", help="Render surface in wireframe")
    parser.add_argument("--no-wireframe", dest="wireframe", action="store_false", help="Render shaded surface")
    parser.add_argument("--savexyz", dest="savexyz", action="store_true", help="Save mapping between image pixels and 3D coordinates as numpy data file")
    parser.add_argument("--saveimg", dest="saveimg", action="store_true", help="Save the undistorted image (without the superimposed grid)")
    parser.add_argument("--ffmpeg", dest="ffmpeg", action="store_true", help="Call ffmpeg to create a sequence video file")
    parser.add_argument("--ffmpeg-fps", dest="ffmpeg_fps", default=10.0, type=float, help="Sequence framerate")
    parser.set_defaults(wireframe=True)
    args = parser.parse_args()

    outdir = args.out

    if not os.path.isdir( outdir ):
        print("Output dir does not exist")
        sys.exit( -1 )
    else:
        print("Output renderings and data will be saved in: ", outdir)


    print("Opening netcdf file ", args.ncfile)
    rootgrp = Dataset( args.ncfile, mode="r")

    if args.baseline != None:
        stereo_baseline = args.baseline
    else:
        print("Loading baseline from netcdf")
        stereo_baseline = rootgrp["scale"][0]

    print("Stereo baseline: ",stereo_baseline, " (use -b option to change)")
    XX = np.array( rootgrp["X_grid"] )/1000.0
    YY = np.array( rootgrp["Y_grid"] )/1000.0
    ZZ = rootgrp["Z"]
    P0plane = np.array( rootgrp["meta"]["P0plane"] )
    nframes = ZZ.shape[0]

    Iw, Ih = rootgrp["meta"].image_width, rootgrp["meta"].image_height


    if args.last_index > 0:
        nframes = args.last_index

    waveview = None

    print("Rendering grid data...")
    pbar = tqdm( range(args.first_index, nframes, args.step_index), file=sys.stdout, unit="frames" )

    data_idx = args.first_index

    for image_idx in pbar:

        I0 = cv.imdecode( rootgrp["cam0images"][image_idx], cv.IMREAD_GRAYSCALE )
        #I0 = cv.resize( I0, dsize=None, fx=2, fy=2)

        if waveview is None:
            waveview = WaveView( title="Wave field",width=I0.shape[1],height=I0.shape[0], wireframe=args.wireframe, pixel_scale=args.pxscale )
            waveview.setup_field( XX, YY, P0plane.T )
            waveview.set_zrange( args.zmin, args.zmax, args.alpha )

        ZZ_data = np.squeeze( np.array( ZZ[data_idx,:,:] ) )/1000.0
        #mask = (ZZ_data == 0.0)
        #ZZ_dil = cv.dilate( ZZ_data, np.ones((3,3)))
        #ZZ_data[mask]=ZZ_dil

        img, img_xyz = waveview.render( I0, ZZ_data )

        if args.savexyz:
            scipy.io.savemat( '%s/%08d'%(outdir,image_idx), {"px_2_3D": img_xyz} )

        img = (img*255).astype( np.uint8 )
        img = cv.cvtColor( img, cv.COLOR_RGB2BGR )
        cv.imwrite('%s/%08d_grid.png'%(outdir,image_idx), img )

        if args.saveimg:
            cv.imwrite('%s/%08d.png'%(outdir,image_idx), I0u )

        data_idx += args.step_data_index

    if args.ffmpeg:
        import subprocess
        callarr = ["ffmpeg.exe", "-r","%d"%args.ffmpeg_fps, "-i" ,"%s/%%08d_grid.png"%(outdir), "-c:v", "libx264", "-vf", 'fps=25,format=yuv420p,scale=614x514', "-preset", "slow", "-crf", "22", "%s/video.mp4"%outdir ]

        print("Calling ", callarr)
        subprocess.run(callarr)
