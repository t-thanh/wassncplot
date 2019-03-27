
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


def RT_from_plane( plane ):
    a=plane[0];b=plane[1];c=plane[2];d=plane[3]
    q = (1-c)/(a*a + b*b)
    R=np.eye( 3 )
    T=np.zeros( (3,1) )
    R[0,0] = 1-a*a*q
    R[0,1] = -a*b*q
    R[0,2] = -a
    R[1,0] = -a*b*q
    R[1,1] = 1-b*b*q
    R[1,2] = -b
    R[2,0] = a
    R[2,1] = b
    R[2,2] = c
    T[0]=0
    T[1]=0
    T[2]=d

    return R, T


def load_ocv_matrix( filename ):
    fs_read = cv.FileStorage( filename, cv.FileStorage_READ)
    arr_read = fs_read.getFirstTopLevelNode().mat()
    fs_read.release()
    return np.array( arr_read )


def load_image( campath, index ):
    globstr =  "%s/%06d_*.*"%(campath,index)
    imgfile = glob.glob(globstr)
    I = cv.imread( str(imgfile[0]), cv.IMREAD_GRAYSCALE ).astype( np.uint8 )
    return I


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("ncfile", help="Input netcdf file")
    parser.add_argument("camdir", help="Image directory")
    parser.add_argument("configdir", help="WASS config dir")
    parser.add_argument("planefile", help="Mean sea-plane definition file")
    parser.add_argument("wass_out", help="wass output data dir containing 3D frame data")
    parser.add_argument("out", help="Output dir")
    parser.add_argument("-f", "--first_index", default=0, type=int, help="First data index to process")
    parser.add_argument("-l", "--last_index", default=1, type=int, help="First data index to process")
    parser.add_argument("-b", "--baseline", type=float, help="Baseline of the stereo system")
    parser.add_argument("--scale", default=2, type=float, help="Output image reduction scale")
    parser.add_argument("--zmin", default=-4, type=float, help="Minimum 3D point elevation (used for colorbar limits)")
    parser.add_argument("--zmax", default=+4, type=float, help="Maximum 3D point elevation (used for colorbar limits)")
    parser.add_argument("--alpha", default=0.5, type=float, help="Surface transparency [0..1]")
    parser.add_argument("--pxscale", default=1.0, type=float, help="Desktop pixel scale (set to 0.5 if using OSX with retina display)")
    parser.add_argument("--wireframe", default=1, type=bool, help="Render surface in wireframe")
    parser.add_argument("--savexyz", type=bool, help="Save mapping between image pixels and 3D coordinates as numpy data file")
    args = parser.parse_args()

    wass_out_dir = args.wass_out
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


    K0 = load_ocv_matrix( "%s/intrinsics_00.xml"%args.configdir )
    kk = load_ocv_matrix( "%s/distortion_00.xml"%args.configdir )


    I0 = load_image(args.camdir, args.first_index) 
    Iw = np.floor( I0.shape[1] ); Ih = np.floor( I0.shape[0] )

    P0Cam =  np.vstack( (np.genfromtxt( "%s/%06d_wd/P0cam.txt"%(wass_out_dir,args.first_index) ) ,[0, 0, 0, 1] ) )
    #plane =  np.mean( np.genfromtxt( "%s/planes.txt"%wass_out_dir ), axis=0 )
    plane = np.genfromtxt( args.planefile )
    Rpl, Tpl = RT_from_plane(plane)

    Ri = Rpl.T
    Ti = -Rpl.T@Tpl
    RTplane = np.vstack( (np.hstack( (Ri,Ti) ),[0,0,0,1]) )

    toNorm = np.array( [[ 2.0/Iw, 0     , -1, 0],
                        [ 0     , 2.0/Ih, -1, 0],
                        [ 0,      0,       1, 0],
                        [ 0,      0,       0, 1]], dtype=np.float )
    
    SCALEi = 1.0/stereo_baseline
    P0plane = toNorm @ P0Cam @ RTplane @ np.diag((SCALEi,SCALEi,-SCALEi, 1))

    waveview = None

    print("Rendering grid data...")
    pbar = tqdm( range(args.first_index, args.last_index), file=sys.stdout, unit="frames" )
    
    for data_idx in pbar:

        I0 = load_image(args.camdir, data_idx) 
        I0 = cv.undistort( I0, K0, kk )
        I0 = np.ascontiguousarray( cv.resize( I0,(0,0),fx=1.0/args.scale,fy=1.0/args.scale ) )

        if waveview is None:
            waveview = WaveView( title="Wave field" ,width=I0.shape[1], height=I0.shape[0], wireframe=not (args.wireframe is None), pixel_scale=args.pxscale )
            waveview.setup_field( XX, YY, P0plane.T )
            waveview.set_zrange( args.zmin, args.zmax, args.alpha )

        ZZ_data = np.squeeze( np.array( ZZ[data_idx,:,:] ) )/1000.0
        img, img_xyz = waveview.render( I0, ZZ_data )

        if args.savexyz:
            np.save( '%s/%08d'%(outdir,data_idx), img_xyz)

        img = (img*255).astype( np.uint8 )
        img = cv.cvtColor( img, cv.COLOR_RGB2BGR )
        cv.imwrite('%s/%08d.png'%(outdir,data_idx), img )