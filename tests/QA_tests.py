#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QA testing tools for RM-tools.
These tools are intended to produce test simulated data sets, and run them
through RM-tools. Automated tools will only be able to confirm that things ran,
but user inspection of the results will be needed to confirm that the expected
values are produced.


Created on Fri Oct 25 10:00:24 2019
@author: Cameron Van Eck
"""
import os
import numpy as np
import subprocess
import shutil
from astropy.io import fits as pf
from scipy.ndimage.filters import gaussian_filter
import unittest


def Faraday_thin_complex_polarization(freq_array,RM,Polint,initial_angle):
    """freq_array = channel frequencies in Hz
       RM = source RM in rad m^-2
       Polint = polarized intensity in whatever units
       initial angle = pre-rotation polarization angle (in degrees)"""
    l2_array=(299792458./freq_array)**2
    Q=Polint*np.cos(2*(np.outer(l2_array,RM)+np.deg2rad(initial_angle)))
    U=Polint*np.sin(2*(np.outer(l2_array,RM)+np.deg2rad(initial_angle)))
    return np.squeeze(np.transpose(Q+1j*U))

def create_1D_data(freq_arr):
    RM=200
    pol_angle_deg=50
    StokesI_midband=1
    fracpol=0.7
    noise_amplitude=0.1
    spectral_index=-0.7
    error_estimate=1  #Size of assumed errors as multiple of actual error.

    pol_spectrum=Faraday_thin_complex_polarization(freq_arr,RM,fracpol,pol_angle_deg)
    I_spectrum=StokesI_midband*(freq_arr/np.median(freq_arr))**spectral_index
    noise_spectrum_I=np.random.normal(scale=noise_amplitude,size=freq_arr.shape)
    noise_spectrum_Q=np.random.normal(scale=noise_amplitude,size=freq_arr.shape)
    noise_spectrum_U=np.random.normal(scale=noise_amplitude,size=freq_arr.shape)
    dIQU=np.ones_like(freq_arr)*noise_amplitude*error_estimate
    
    if not os.path.isdir('simdata/1D'):
        os.makedirs('simdata/1D')
    np.savetxt('simdata/1D/simsource.dat', list(zip(freq_arr,I_spectrum+noise_spectrum_I,
                                I_spectrum*pol_spectrum.real+noise_spectrum_Q,
                                I_spectrum*pol_spectrum.imag+noise_spectrum_U,
                                dIQU,dIQU,dIQU)))
    with open("simdata/1D/sim_truth.txt",'w') as f:
        f.write('RM = {} rad/m^2\n'.format(RM))
        f.write('Intrsinsic polarization angle = {} deg\n'.format(pol_angle_deg))
        f.write('Fractional polarization = {} %\n'.format(fracpol*100.))
        f.write('Stokes I = {} Jy/beam\n'.format(StokesI_midband))
        f.write('Reference frequency for I = {} GHz\n'.format(np.median(freq_arr)/1e9))
        f.write('Spectral index = {}\n'.format(spectral_index))
        f.write('Actual error per channel = {} Jy/beam\n'.format(noise_amplitude))
        f.write('Input assumed error = {} Jy/beam\n'.format(noise_amplitude*error_estimate))
        

def create_3D_data(freq_arr,N_side=100):
    src_RM=200
    src_pol_angle_deg=50
    src_flux=2
    src_x=N_side//4
    src_y=N_side//4
    
    diffuse_RM=50
    diffuse_pol_angle_deg=-10
    diffuse_flux=1

    noise_amplitude=0.1
    beam_size_pix=20
    
    src_pol_spectrum=Faraday_thin_complex_polarization(freq_arr,src_RM,src_flux,src_pol_angle_deg)
    diffuse_pol_spectrum=Faraday_thin_complex_polarization(freq_arr,diffuse_RM,diffuse_flux,diffuse_pol_angle_deg)

    src_Q_cube=np.zeros((N_side,N_side,freq_arr.size))
    src_U_cube=np.zeros((N_side,N_side,freq_arr.size))
    src_Q_cube[src_x,src_y,:]=src_pol_spectrum.real
    src_U_cube[src_x,src_y,:]=src_pol_spectrum.imag

    src_Q_cube=gaussian_filter(src_Q_cube,(beam_size_pix/2.35,beam_size_pix/2.35,0),mode='wrap')
    src_U_cube=gaussian_filter(src_U_cube,(beam_size_pix/2.35,beam_size_pix/2.35,0),mode='wrap')
    scale_factor=np.max(np.sqrt(src_Q_cube**2+src_U_cube**2))/src_flux #Renormalizing flux after convolution
    src_Q_cube=src_Q_cube/scale_factor
    src_U_cube=src_U_cube/scale_factor
    
    diffuse_Q_cube=np.tile(diffuse_pol_spectrum.real[np.newaxis,np.newaxis,:],(N_side,N_side,1))
    diffuse_U_cube=np.tile(diffuse_pol_spectrum.imag[np.newaxis,np.newaxis,:],(N_side,N_side,1))
    
    noise_Q_cube=np.random.normal(scale=noise_amplitude,size=src_Q_cube.shape)
    noise_U_cube=np.random.normal(scale=noise_amplitude,size=src_Q_cube.shape)
    noise_Q_cube=gaussian_filter(noise_Q_cube,(beam_size_pix/2.35,beam_size_pix/2.35,0),mode='wrap')
    noise_U_cube=gaussian_filter(noise_U_cube,(beam_size_pix/2.35,beam_size_pix/2.35,0),mode='wrap')
    scale_factor=np.std(noise_Q_cube)/noise_amplitude #Renormalizing flux after convolution
    noise_Q_cube=noise_Q_cube/scale_factor
    noise_U_cube=noise_U_cube/scale_factor

    Q_cube=src_Q_cube+noise_Q_cube+diffuse_Q_cube
    U_cube=src_U_cube+noise_U_cube+diffuse_U_cube

    header=pf.Header()
    header['BITPIX']=-32
    header['NAXIS']=3
    header['NAXIS1']=N_side
    header['NAXIS2']=N_side
    header['NAXIS3']=freq_arr.size
    header['CTYPE1']='RA---SIN'
    header['CRVAL1']=90
    header['CDELT1']=-1./3600.
    header['CRPIX1']=1
    header['CUNIT1']='deg'
    
    header['CTYPE2']='DEC--SIN'
    header['CRVAL2']=0
    header['CDELT2']=1./3600.
    header['CRPIX2']=1
    header['CUNIT2']='deg'
    
    header['CTYPE3']='FREQ'
    header['CRVAL3']=freq_arr[0]
    header['CDELT3']=freq_arr[1]-freq_arr[0]
    header['CRPIX3']=1
    header['CUNIT3']='Hz'
    
    header['BUNIT']='Jy/beam'
    
    if not os.path.isdir('simdata/3D'):
        os.makedirs('simdata/3D')

    pf.writeto('simdata/3D/Q_cube.fits',np.transpose(Q_cube),header=header,overwrite=True)
    pf.writeto('simdata/3D/U_cube.fits',np.transpose(U_cube),header=header,overwrite=True)
    with open("simdata/3D/freqHz.txt",'w') as f:
        for freq in freq_arr:
            f.write('{:}\n'.format(freq))

    with open("simdata/3D/sim_truth.txt",'w') as f:
        f.write('Point source:\n')
        f.write('RM = {} rad/m^2\n'.format(src_RM))
        f.write('Intrsinsic polarization angle = {} deg\n'.format(src_pol_angle_deg))
        f.write('Polarized Flux = {} Jy/beam\n'.format(src_flux))
        f.write('x position = {} pix\n'.format(src_x))
        f.write('y position = {} pix\n'.format(src_y))
        f.write('\n')
        f.write('Diffuse emission:\n')
        f.write('RM = {} rad/m^2\n'.format(diffuse_RM))
        f.write('Intrsinsic polarization angle = {} deg\n'.format(diffuse_pol_angle_deg))
        f.write('Polarized Flux = {} Jy/beam\n'.format(diffuse_flux))
        f.write('\n')
        f.write('Other:\n')
        f.write('Actual error per channel = {} Jy/beam\n'.format(noise_amplitude))
        f.write('Beam FWHM = {} pix\n'.format(beam_size_pix))

        


class test_RMtools(unittest.TestCase):
    def setUp(self):
        #Clean up old simulations to prevent interference with new runs.
        N_chan=288
        self.freq_arr=np.linspace(800e6,1088e6,num=N_chan)

    def test_a_1D_synth(self):
        create_1D_data(self.freq_arr)
        returncode=subprocess.call('rmsynth1d simdata/1D/simsource.dat -l 600 -d 3 -S',shell=True)
        self.assertEqual(returncode, 0, 'RMsynth1D failed to run.')
        #what else? test output values? Tricky.

    def test_c_3D_synth(self):
        create_3D_data(self.freq_arr)
        returncode=subprocess.call('rmsynth3d simdata/3D/Q_cube.fits simdata/3D/U_cube.fits simdata/3D/freqHz.txt -l 300 -d 10',shell=True)
        self.assertEqual(returncode, 0, 'RMsynth3D failed to run.')
        header=pf.getheader('simdata/3D/FDF_tot_dirty.fits')
        self.assertEqual(header['NAXIS'],3,'Wrong number of axes in output?')
        self.assertEqual((header['NAXIS1'],header['NAXIS2']),(100,100),'Image plane has wrong dimensions!')
        self.assertEqual(header['NAXIS3'],61,'Number of output FD planes has changed.')
    
    def test_b_1D_clean(self):
        if not os.path.exists('simdata/1D/simsource_RMsynth.dat'):
            self.skipTest('Could not test 1D clean; 1D synth failed first.')
        returncode=subprocess.call('rmclean1d simdata/1D/simsource.dat -n 10',shell=True)
        self.assertEqual(returncode, 0, 'RMclean1D failed to run.')
        #how to test output values?
        
    def test_d_3D_clean(self):
        if not os.path.exists('simdata/3D/FDF_tot_dirty.fits'):
            self.skipTest('Could not test 3D clean; 3D synth failed first.')
        returncode=subprocess.call('rmclean3d simdata/3D/FDF_tot_dirty.fits simdata/3D/RMSF_tot.fits -n 10',shell=True)
        self.assertEqual(returncode, 0, 'RMclean3D failed to run.')
        #what else?
    
    def test_e_1Dsynth_fromFITS(self):
        if not os.path.exists('simdata/3D/Q_cube.fits'):
            create_3D_data(self.freq_arr)
        returncode=subprocess.call('rmsynth1dFITS simdata/3D/Q_cube.fits simdata/3D/U_cube.fits 25 25 -l 600 -d 3 -S',shell=True)
        self.assertEqual(returncode, 0, 'RMsynth1D_fromFITS failed to run.')
        
    def test_f_QUfitting(self):
        if not os.path.exists('simdata/1D/simsource.dat'):
            create_1D_data(self.freq_arr)
        if not os.path.exists('models_ns'):            
            shutil.copytree('../RMtools_1D/models_ns','models_ns')
        returncode=subprocess.call('python ../RMtools_1D/do_QUfit_1D_mnest.py simdata/1D/simsource.dat',shell=True)
        self.assertEqual(returncode, 0, 'QU fitting failed to run.')
        shutil.rmtree('models_ns')


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    if os.path.exists('simdata'):
        shutil.rmtree('simdata')

    print('\nUnit tests running. Manual inspection of saved outputs is necessary for full verification.')
    print('Test data inputs and outputs can be found in {}\n\n\n'.format(os.getcwd()))

    unittest.TestLoader.sortTestMethodsUsing=None
    suite = unittest.TestLoader().loadTestsFromTestCase(test_RMtools)
    unittest.TextTestRunner(verbosity=2).run(suite)
    




