#!/usr/bin/env python
#=============================================================================#
#                                                                             #
# NAME:     cl_RMsynth_1D.py                                                  #
#                                                                             #
# PURPOSE: API for runnning RM-synthesis on an ASCII Stokes I, Q & U spectrum.#
#                                                                             #
# MODIFIED: 16-Nov-2018 by J. West                                            #
#                                                                             #
#=============================================================================#
#                                                                             #
# The MIT License (MIT)                                                       #
#                                                                             #
# Copyright (c) 2015 - 2018 Cormac R. Purcell                                 #
#                                                                             #
# Permission is hereby granted, free of charge, to any person obtaining a     #
# copy of this software and associated documentation files (the "Software"),  #
# to deal in the Software without restriction, including without limitation   #
# the rights to use, copy, modify, merge, publish, distribute, sublicense,    #
# and/or sell copies of the Software, and to permit persons to whom the       #
# Software is furnished to do so, subject to the following conditions:        #
#                                                                             #
# The above copyright notice and this permission notice shall be included in  #
# all copies or substantial portions of the Software.                         #
#                                                                             #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR  #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,    #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER      #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING     #
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER         #
# DEALINGS IN THE SOFTWARE.                                                   #
#                                                                             #
#=============================================================================#
  
import sys
#import os
import time
#import argparse
import traceback
import json
import math as m
import numpy as np
import matplotlib.pyplot as plt
#import pdb

from RMutils.util_RM import do_rmsynth
from RMutils.util_RM import do_rmsynth_planes
from RMutils.util_RM import get_rmsf_planes
from RMutils.util_RM import measure_FDF_parms
from RMutils.util_RM import measure_qu_complexity
from RMutils.util_RM import measure_fdf_complexity
from RMutils.util_misc import nanmedian
from RMutils.util_misc import toscalar
from RMutils.util_misc import create_frac_spectra
from RMutils.util_misc import poly5
from RMutils.util_misc import MAD
from RMutils.util_plotTk import plot_Ipqu_spectra_fig
from RMutils.util_plotTk import plot_rmsf_fdf_fig
from RMutils.util_plotTk import plot_complexity_fig
from RMutils.util_plotTk import CustomNavbar
from RMutils.util_plotTk import plot_rmsIQU_vs_nu_ax

C = 2.997924538e8 # Speed of light [m/s]

#-----------------------------------------------------------------------------#
def run_rmsynth(data, polyOrd=3, phiMax_radm2=None, dPhi_radm2=None, 
                nSamples=10.0, weightType="variance", fitRMSF=False,
                noStokesI=False, phiNoise_radm2=1e6, nBits=32, showPlots=False,
                debug=False, verbose=False, log=print,units='Jy/beam'):
    """
    Read the I, Q & U data and run RM-synthesis.
    """

    # Default data types
    dtFloat = "float" + str(nBits)
    dtComplex = "complex" + str(2*nBits)

    # freq_Hz, I, Q, U, dI, dQ, dU
    try:
        if verbose: log("> Trying [freq_Hz, I, Q, U, dI, dQ, dU]", end=' ')
        (freqArr_Hz, IArr, QArr, UArr, dIArr, dQArr, dUArr) = data 
        if verbose: log("... success.")
    except Exception:
        if verbose: log("...failed.")
        # freq_Hz, q, u, dq, du
        try:
            if verbose: log("> Trying [freq_Hz, q, u,  dq, du]", end=' ')
            (freqArr_Hz, QArr, UArr, dQArr, dUArr) = data 
            if verbose: log("... success.")
            noStokesI = True
        except Exception:
            if verbose: log("...failed.")
            if debug:
                log(traceback.format_exc())
            sys.exit()
    if verbose: log("Successfully read in the Stokes spectra.")

    # If no Stokes I present, create a dummy spectrum = unity
    if noStokesI:
        log("Warn: no Stokes I data in use.")
        IArr = np.ones_like(QArr)
        dIArr = np.zeros_like(QArr)
        
    # Convert to GHz for convenience
    freqArr_GHz = freqArr_Hz / 1e9
    dQUArr = (dQArr + dUArr)/2.0
 
    # Fit the Stokes I spectrum and create the fractional spectra
    IModArr, qArr, uArr, dqArr, duArr, fitDict = \
             create_frac_spectra(freqArr  = freqArr_GHz,
                                 IArr     = IArr,
                                 QArr     = QArr,
                                 UArr     = UArr,
                                 dIArr    = dIArr,
                                 dQArr    = dQArr,
                                 dUArr    = dUArr,
                                 polyOrd  = polyOrd,
                                 verbose  = True,
                                 debug    = debug)

    # Plot the data and the Stokes I model fit
    if showPlots:
        if verbose: log("Plotting the input data and spectral index fit.")
        freqHirArr_Hz =  np.linspace(freqArr_Hz[0], freqArr_Hz[-1], 10000)     
        IModHirArr = poly5(fitDict["p"])(freqHirArr_Hz/1e9)    
        specFig = plt.figure(figsize=(12.0, 8))
        plot_Ipqu_spectra_fig(freqArr_Hz     = freqArr_Hz,
                              IArr           = IArr, 
                              qArr           = qArr, 
                              uArr           = uArr, 
                              dIArr          = dIArr,
                              dqArr          = dqArr,
                              duArr          = duArr,
                              freqHirArr_Hz  = freqHirArr_Hz,
                              IModArr        = IModHirArr,
                              fig            = specFig,
                              units          = units)

        # Use the custom navigation toolbar (does not work on Mac OS X)
#        try:
#            specFig.canvas.toolbar.pack_forget()
#            CustomNavbar(specFig.canvas, specFig.canvas.toolbar.window)
#        except Exception:
#            pass

        # Display the figure
#        if not plt.isinteractive():
#            specFig.show()

        # DEBUG (plot the Q, U and average RMS spectrum)
        if debug:
            rmsFig = plt.figure(figsize=(12.0, 8))
            ax = rmsFig.add_subplot(111)
            ax.plot(freqArr_Hz/1e9, dQUArr, marker='o', color='k', lw=0.5,
                    label='rms <QU>')
            ax.plot(freqArr_Hz/1e9, dQArr, marker='o', color='b', lw=0.5,
                    label='rms Q')
            ax.plot(freqArr_Hz/1e9, dUArr, marker='o', color='r', lw=0.5,
                    label='rms U')
            xRange = (np.nanmax(freqArr_Hz)-np.nanmin(freqArr_Hz))/1e9 
            ax.set_xlim( np.min(freqArr_Hz)/1e9 - xRange*0.05,
                         np.max(freqArr_Hz)/1e9 + xRange*0.05)
            ax.set_xlabel('$\\nu$ (GHz)')
            ax.set_ylabel('RMS '+units)
            ax.set_title("RMS noise in Stokes Q, U and <Q,U> spectra")
#            rmsFig.show()

    #-------------------------------------------------------------------------#

    # Calculate some wavelength parameters
    lambdaSqArr_m2 = np.power(C/freqArr_Hz, 2.0)
    dFreq_Hz = np.nanmin(np.abs(np.diff(freqArr_Hz)))
    lambdaSqRange_m2 = ( np.nanmax(lambdaSqArr_m2) -
                         np.nanmin(lambdaSqArr_m2) )        
    dLambdaSqMin_m2 = np.nanmin(np.abs(np.diff(lambdaSqArr_m2)))
    dLambdaSqMax_m2 = np.nanmax(np.abs(np.diff(lambdaSqArr_m2)))

    # Set the Faraday depth range
    fwhmRMSF_radm2 = 2.0 * m.sqrt(3.0) / lambdaSqRange_m2
    if dPhi_radm2 is None:
        dPhi_radm2 = fwhmRMSF_radm2 / nSamples
    if phiMax_radm2 is None:
        phiMax_radm2 = m.sqrt(3.0) / dLambdaSqMax_m2
        phiMax_radm2 = max(phiMax_radm2, 600.0)    # Force the minimum phiMax

    # Faraday depth sampling. Zero always centred on middle channel
    nChanRM = int(round(abs((phiMax_radm2 - 0.0) / dPhi_radm2)) * 2.0 + 1.0)
    startPhi_radm2 = - (nChanRM-1.0) * dPhi_radm2 / 2.0
    stopPhi_radm2 = + (nChanRM-1.0) * dPhi_radm2 / 2.0
    phiArr_radm2 = np.linspace(startPhi_radm2, stopPhi_radm2, nChanRM)
    phiArr_radm2 = phiArr_radm2.astype(dtFloat)
    if verbose: log("PhiArr = %.2f to %.2f by %.2f (%d chans)." % (phiArr_radm2[0],
                                                         phiArr_radm2[-1],
                                                         float(dPhi_radm2),
                                                         nChanRM))
                                                             
    # Calculate the weighting as 1/sigma^2 or all 1s (uniform)
    if weightType=="variance":
        weightArr = 1.0 / np.power(dQUArr, 2.0)
    else:
        weightType = "uniform"
        weightArr = np.ones(freqArr_Hz.shape, dtype=dtFloat)
    if verbose: log("Weight type is '%s'." % weightType)

    startTime = time.time()
    
    # Perform RM-synthesis on the spectrum
    dirtyFDF, lam0Sq_m2 = do_rmsynth_planes(dataQ           = qArr,
                                            dataU           = uArr,
                                            lambdaSqArr_m2  = lambdaSqArr_m2, 
                                            phiArr_radm2    = phiArr_radm2, 
                                            weightArr       = weightArr,
                                            nBits           = nBits,
                                            verbose         = True,
                                            log             = log)

    # Calculate the Rotation Measure Spread Function
    RMSFArr, phi2Arr_radm2, fwhmRMSFArr, fitStatArr = \
        get_rmsf_planes(lambdaSqArr_m2  = lambdaSqArr_m2,
                        phiArr_radm2    = phiArr_radm2, 
                        weightArr       = weightArr, 
                        mskArr          = ~np.isfinite(qArr),
                        lam0Sq_m2       = lam0Sq_m2, 
                        double          = True, 
                        fitRMSF         = fitRMSF, 
                        fitRMSFreal     = False, 
                        nBits           = nBits,
                        verbose         = True,
                        log             = log)
    fwhmRMSF = float(fwhmRMSFArr)
    
    # ALTERNATE RM-SYNTHESIS CODE --------------------------------------------#

    #dirtyFDF, [phi2Arr_radm2, RMSFArr], lam0Sq_m2, fwhmRMSF = \
    #          do_rmsynth(qArr, uArr, lambdaSqArr_m2, phiArr_radm2, weightArr)
    
    #-------------------------------------------------------------------------#
    
    endTime = time.time()
    cputime = (endTime - startTime)
    if verbose: log("> RM-synthesis completed in %.2f seconds." % cputime)
    
    # Determine the Stokes I value at lam0Sq_m2 from the Stokes I model
    # Multiply the dirty FDF by Ifreq0 to recover the PI
    freq0_Hz = C / m.sqrt(lam0Sq_m2)
    Ifreq0 = poly5(fitDict["p"])(freq0_Hz/1e9)
    dirtyFDF *= (Ifreq0)    # FDF is in fracpol units initially, convert back to flux 

    # Calculate the theoretical noise in the FDF !!Old formula only works for wariance weights!
    dFDFth = np.sqrt( np.sum(weightArr**2 * dQUArr**2) / (np.sum(weightArr))**2 )
    
    
    # Measure the parameters of the dirty FDF
    # Use the theoretical noise to calculate uncertainties
    mDict = measure_FDF_parms(FDF         = dirtyFDF,
                              phiArr      = phiArr_radm2,
                              fwhmRMSF    = fwhmRMSF,
                              dFDF        = dFDFth,
                              lamSqArr_m2 = lambdaSqArr_m2,
                              lam0Sq      = lam0Sq_m2)
    mDict["Ifreq0"] = toscalar(Ifreq0)
    mDict["polyCoeffs"] =  ",".join([str(x) for x in fitDict["p"]])
    mDict["IfitStat"] = fitDict["fitStatus"]
    mDict["IfitChiSqRed"] = fitDict["chiSqRed"]
    mDict["lam0Sq_m2"] = toscalar(lam0Sq_m2)
    mDict["freq0_Hz"] = toscalar(freq0_Hz)
    mDict["fwhmRMSF"] = toscalar(fwhmRMSF)
    mDict["dQU"] = toscalar(nanmedian(dQUArr))
    mDict["dFDFth"] = toscalar(dFDFth)
    mDict["units"] = units

        
    # Measure the complexity of the q and u spectra
    mDict["fracPol"] = mDict["ampPeakPIfit"]/(Ifreq0)
    mD, pD = measure_qu_complexity(freqArr_Hz = freqArr_Hz,
                                   qArr       = qArr,
                                   uArr       = uArr,
                                   dqArr      = dqArr,
                                   duArr      = duArr,
                                   fracPol    = mDict["fracPol"],
                                   psi0_deg   = mDict["polAngle0Fit_deg"],
                                   RM_radm2   = mDict["phiPeakPIfit_rm2"])
    mDict.update(mD)
    
    # Debugging plots for spectral complexity measure
    if debug:
        tmpFig = plot_complexity_fig(xArr=pD["xArrQ"],
                                     qArr=pD["yArrQ"],
                                     dqArr=pD["dyArrQ"],
                                     sigmaAddqArr=pD["sigmaAddArrQ"],
                                     chiSqRedqArr=pD["chiSqRedArrQ"],
                                     probqArr=pD["probArrQ"],
                                     uArr=pD["yArrU"],
                                     duArr=pD["dyArrU"],
                                     sigmaAdduArr=pD["sigmaAddArrU"],
                                     chiSqReduArr=pD["chiSqRedArrU"],
                                     probuArr=pD["probArrU"],
                                     mDict=mDict)
        tmpFig.show()
    
    #add array dictionary
    aDict = dict()
    aDict["phiArr_radm2"] = phiArr_radm2
    aDict["phi2Arr_radm2"] = phi2Arr_radm2
    aDict["RMSFArr"] = RMSFArr
    aDict["freqArr_Hz"] = freqArr_Hz
    aDict["weightArr"]=weightArr
    aDict["dirtyFDF"]=dirtyFDF
    
    if verbose: 
       # Print the results to the screen
       log()
       log('-'*80)
       log('RESULTS:\n')
       log('FWHM RMSF = %.4g rad/m^2' % (mDict["fwhmRMSF"]))
    
       log('Pol Angle = %.4g (+/-%.4g) deg' % (mDict["polAngleFit_deg"],
                                              mDict["dPolAngleFit_deg"]))
       log('Pol Angle 0 = %.4g (+/-%.4g) deg' % (mDict["polAngle0Fit_deg"],
                                                mDict["dPolAngle0Fit_deg"]))
       log('Peak FD = %.4g (+/-%.4g) rad/m^2' % (mDict["phiPeakPIfit_rm2"],
                                                mDict["dPhiPeakPIfit_rm2"]))
       log('freq0_GHz = %.4g ' % (mDict["freq0_Hz"]/1e9))
       log('I freq0 = %.4g %s' % (mDict["Ifreq0"],units))
       log('Peak PI = %.4g (+/-%.4g) %s' % (mDict["ampPeakPIfit"],
                                                mDict["dAmpPeakPIfit"],units))
       log('QU Noise = %.4g %s' % (mDict["dQU"],units))
       log('FDF Noise (theory)   = %.4g %s' % (mDict["dFDFth"],units))
       log('FDF Noise (Corrected MAD) = %.4g %s' % (mDict["dFDFcorMAD"],units))
       log('FDF Noise (rms)   = %.4g %s' % (mDict["dFDFrms"],units))
       log('FDF SNR = %.4g ' % (mDict["snrPIfit"]))
       log('sigma_add(q) = %.4g (+%.4g, -%.4g)' % (mDict["sigmaAddQ"],
                                            mDict["dSigmaAddPlusQ"],
                                            mDict["dSigmaAddMinusQ"]))
       log('sigma_add(u) = %.4g (+%.4g, -%.4g)' % (mDict["sigmaAddU"],
                                            mDict["dSigmaAddPlusU"],
                                            mDict["dSigmaAddMinusU"]))
       log()
       log('-'*80)



    # Plot the RM Spread Function and dirty FDF
    if showPlots:
        fdfFig = plt.figure(figsize=(12.0, 8))
        plot_rmsf_fdf_fig(phiArr     = phiArr_radm2,
                          FDF        = dirtyFDF,
                          phi2Arr    = phi2Arr_radm2,
                          RMSFArr    = RMSFArr,
                          fwhmRMSF   = fwhmRMSF,
                          vLine      = mDict["phiPeakPIfit_rm2"],
                          fig        = fdfFig,
                          units      = units)

        # Use the custom navigation toolbar
#        try:
#            fdfFig.canvas.toolbar.pack_forget()
#            CustomNavbar(fdfFig.canvas, fdfFig.canvas.toolbar.window)
#        except Exception:
#            pass
        
        # Display the figure
#        fdfFig.show()

    # Pause if plotting enabled
    if showPlots or debug:        
        plt.show()
        #        #if verbose: print "Press <RETURN> to exit ...",
#        input()

    return mDict, aDict
    
def readFile(dataFile, nBits, verbose):
    """
    Read the I, Q & U data from the ASCII file.
    """

    # Default data types
    dtFloat = "float" + str(nBits)
    dtComplex = "complex" + str(2*nBits)

    # Output prefix is derived from the input file name
    

    # Read the data-file. Format=space-delimited, comments="#".
    if verbose: print("Reading the data file '%s':" % dataFile)
    # freq_Hz, I, Q, U, dI, dQ, dU
    try:
        if verbose: print("> Trying [freq_Hz, I, Q, U, dI, dQ, dU]", end=' ')
        (freqArr_Hz, IArr, QArr, UArr,
         dIArr, dQArr, dUArr) = \
         np.loadtxt(dataFile, unpack=True, dtype=dtFloat)
        if verbose: print("... success.")
        data=[freqArr_Hz, IArr, QArr, UArr, dIArr, dQArr, dUArr]
    except Exception:
        if verbose: print("...failed.")
        # freq_Hz, q, u, dq, du
        try:
            if verbose: print("> Trying [freq_Hz, q, u,  dq, du]", end=' ')
            (freqArr_Hz, QArr, UArr, dQArr, dUArr) = \
                         np.loadtxt(dataFile, unpack=True, dtype=dtFloat)
            if verbose: print("... success.")
            data=[freqArr_Hz, QArr, UArr, dQArr, dUArr]

            noStokesI = True
        except Exception:
            if verbose: print("...failed.")
            if debug:
                print(traceback.format_exc())
            sys.exit()
    if verbose: print("Successfully read in the Stokes spectra.")
    return data

def saveOutput(outdict, arrdict, prefixOut, verbose):
    # Save the  dirty FDF, RMSF and weight array to ASCII files
    if verbose: print("Saving the dirty FDF, RMSF weight arrays to ASCII files.")
    outFile = prefixOut + "_FDFdirty.dat"
    if verbose: 
        print("> %s" % outFile)
    np.savetxt(outFile, list(zip(arrdict["phiArr_radm2"], arrdict["dirtyFDF"].real, arrdict["dirtyFDF"].imag)))
    
    outFile = prefixOut + "_RMSF.dat"
    if verbose: 
        print("> %s" % outFile)       
    np.savetxt(outFile, list(zip(arrdict["phi2Arr_radm2"], arrdict["RMSFArr"].real, arrdict["RMSFArr"].imag)))
    
    outFile = prefixOut + "_weight.dat"
    if verbose: 
        print("> %s" % outFile)
    np.savetxt(outFile, list(zip(arrdict["freqArr_Hz"], arrdict["weightArr"])))

    # Save the measurements to a "key=value" text file
    outFile = prefixOut + "_RMsynth.dat"

    if verbose: 
        print("Saving the measurements on the FDF in 'key=val' and JSON formats.")
        print("> %s" % outFile)

    FH = open(outFile, "w")
    for k, v in outdict.items():
        FH.write("%s=%s\n" % (k, v))
    FH.close()
       

    outFile = prefixOut + "_RMsynth.json"
    
    if verbose: 
        print("> %s" % outFile)
    json.dump(dict(outdict), open(outFile, "w"))       



