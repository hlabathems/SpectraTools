# -*- coding: utf-8 -*-
"""
Created on Thu Aug  6 14:04:15 2015

@author: lc585

Fit emission line with many sixth order Gauss-Hermite polynomial
References: van der Marel & Franx (1993); Cappelari (2000)

"""

import numpy as np
import astropy.units as u
from lmfit import minimize, Parameters, fit_report 
from lmfit.models import PowerLawModel
from lmfit.model import Model 
import numpy.ma as ma
import seaborn as sns
import matplotlib.pyplot as plt
import os
import cPickle as pickle
from spectra.fit_line import wave2doppler, resid, doppler2wave
from scipy.interpolate import interp1d
import math
from scipy import integrate, optimize

def resid(p, x, model, data=None, sigma=None):

        mod = model.eval( params=p, x=x )

        if data is not None:
            resids = mod - data
            if sigma is not None:
                weighted = np.sqrt(resids ** 2 / sigma ** 2)
                return weighted
            else:
                return resids
        else:
            return mod

def gh_resid(p, x, order, data=None, sigma=None):

        mod = gausshermite(x, p, order)

        if data is not None:
            resids = mod - data
            if sigma is not None:
                weighted = np.sqrt(resids ** 2 / sigma ** 2)
                return weighted
            else:
                return resids
        else:
            return mod

def gausshermite(x, p, order):

    h0 = (p['amp0'].value/(np.sqrt(2*math.pi)*p['sig0'].value)) * np.exp(-(x-p['cen0'].value)**2 /(2*p['sig0'].value**2))

    if order > 0:
        h1 = np.sqrt(2.0) * x * (p['amp1'].value/(np.sqrt(2*math.pi)*p['sig1'].value)) * np.exp(-(x-p['cen1'].value)**2 /(2*p['sig1'].value**2))

    if order > 1:
        h2 = (2.0*x*x - 1.0) / np.sqrt(2.0) * (p['amp2'].value/(np.sqrt(2*math.pi)*p['sig2'].value)) * np.exp(-(x-p['cen2'].value)**2 /(2*p['sig2'].value**2))
        
    if order > 2:
        h3 = x * (2.0*x*x - 3.0) / np.sqrt(3.0) * (p['amp3'].value/(np.sqrt(2*math.pi)*p['sig3'].value)) * np.exp(-(x-p['cen3'].value)**2 /(2*p['sig3'].value**2))
       
    if order > 3:   
        h4 = (x*x*(4.0*x*x-12.0)+3.0) / (2.0*np.sqrt(6.0)) * (p['amp4'].value/(np.sqrt(2*math.pi)*p['sig4'].value)) * np.exp(-(x-p['cen4'].value)**2 /(2*p['sig4'].value**2))
       
    if order > 4:
        h5 = (x*(x*x*(4.0*x*x-20.0) + 15.0)) / (2.0*np.sqrt(15.0)) * (p['amp5'].value/(np.sqrt(2*math.pi)*p['sig5'].value)) * np.exp(-(x-p['cen5'].value)**2 /(2*p['sig5'].value**2))
       
    if order > 5:
        h6 = (x*x*(x*x*(8.0*x*x-60.0) + 90.0) - 15.0) / (12.0*np.sqrt(5.0)) * (p['amp6'].value/(np.sqrt(2*math.pi)*p['sig6'].value)) * np.exp(-(x-p['cen6'].value)**2 /(2*p['sig6'].value**2))
       
    if order == 0:
        return h0
    if order == 1:
        return h0 + h1 
    if order == 2:
        return h0 + h1 + h2 
    if order == 3:
        return h0 + h1 + h2 + h3 
    if order == 4:
        return h0 + h1 + h2 + h3 + h4  
    if order == 5:
        return h0 + h1 + h2 + h3 + h4 + h5  
    if order == 6:
        return h0 + h1 + h2 + h3 + h4 + h5 + h6                       

def plot_fit(wav=None,
             flux=None,
             err=None,
             wav_mod=None,
             flux_mod=None,
             plot_savefig=None,
             plot_title='',
             maskout=None,
             z=0.0,
             w0=6564.89*u.AA,
             continuum_region=[[6000.,6250.]*u.AA,[6800.,7000.]*u.AA],
             fitting_region=[6400,6800]*u.AA,
             plot_region=None):


    # plotting region
    print plot_region 

    if plot_region.unit == (u.km/u.s):
        plot_region = doppler2wave(plot_region, w0)  
    
    plot_region_inds = (wav > plot_region[0]) & (wav < plot_region[1])

    # Transform to doppler shift
    vdat = wave2doppler(wav, w0)

    xdat = wav[plot_region_inds]
    vdat = vdat[plot_region_inds]
    ydat = flux[plot_region_inds]
    yerr = err[plot_region_inds]

    fig = plt.figure(figsize=(6,8))

    fit = fig.add_subplot(2,1,1)
    fit.set_xticklabels( () )
    residuals = fig.add_subplot(2,1,2)

    fit.errorbar(vdat.value, ydat, yerr=yerr, linestyle='', alpha=0.4)
     
    # Mark continuum fitting region
 
    blue_cont = wave2doppler(continuum_region[0], w0)
    red_cont = wave2doppler(continuum_region[1], w0)
   
    fit.axvspan(blue_cont.value[0], blue_cont.value[1], color='grey', lw = 1, alpha = 0.2 )
    fit.axvspan(red_cont.value[0], red_cont.value[1], color='grey', lw = 1, alpha = 0.2 )
   
    residuals.axvspan(blue_cont.value[0], blue_cont.value[1], color='grey', lw = 1, alpha = 0.2 )
    residuals.axvspan(red_cont.value[0], red_cont.value[1], color='grey', lw = 1, alpha = 0.2 )

    # Mark fitting region
    fr = wave2doppler(fitting_region, w0) 

    # Mask out regions
    xdat_masking = np.arange(xdat.min().value, xdat.max().value, 0.05)*(u.AA)
    vdat_masking = wave2doppler(xdat_masking, w0)

    mask = (vdat_masking.value < fr.value[0]) | (vdat_masking.value > fr.value[1])


    if maskout is not None:

        if maskout.unit == (u.km/u.s):

            for item in maskout:
                mask = mask | ((vdat_masking.value > item.value[0]) & (vdat_masking.value < item.value[1]))

        elif maskout.unit == (u.AA):

            for item in maskout:
                xmin = item.value[0] / (1.0 + z)
                xmax = item.value[1] / (1.0 + z)
                mask = mask | ((xdat_masking.value > xmin) & (xdat_masking.value < xmax))


    vdat1_masking = ma.array(vdat_masking.value)
    vdat1_masking[mask] = ma.masked

    for item in ma.extras.flatnotmasked_contiguous(vdat1_masking):
        fit.axvspan(vdat1_masking[item].min(), vdat1_masking[item].max(), color=sns.color_palette('deep')[4], alpha=0.4)
        residuals.axvspan(vdat1_masking[item].min(), vdat1_masking[item].max(), color=sns.color_palette('deep')[4], alpha=0.4)   

    line, = fit.plot(wav_mod, flux_mod, color='black')

    plotting_limits = wave2doppler(plot_region, w0) 
    fit.set_xlim(plotting_limits[0].value, plotting_limits[1].value)

    f = interp1d(wav_mod, flux_mod, kind='cubic', bounds_error=False, fill_value=0.0)
    

    residuals.errorbar(vdat.value, ydat - f(vdat) , yerr=yerr, linestyle='', alpha=0.4)

    residuals.set_xlim(fit.get_xlim())

    fit.set_ylabel(r'F$_\lambda$', fontsize=12)
    residuals.set_xlabel(r"$\Delta$ v (kms$^{-1}$)", fontsize=12)
    residuals.set_ylabel("Residual")


    fig.tight_layout()

    if plot_savefig is not None:
        fig = fig.savefig(plot_savefig)

    plt.show()

    plt.close()

    return None

def fit_line(wav,
             flux,
             err,
             z=0.0,
             w0=6564.89*u.AA,
             velocity_shift=0.0*(u.km / u.s),
             continuum_region=[[6000.,6250.]*u.AA,[6800.,7000.]*u.AA],
             fitting_region=[6400,6800]*u.AA,
             plot_region=[6000,7000]*u.AA,
             maskout=None,
             order=6,
             plot=True,
             plot_savefig='something.png',
             plot_title='',
             verbose=True,
             save_dir=None):

    """
    Velocity shift added to doppler shift to change zero point (can do if HW10
    redshift does not agree with Halpha centroid)

    Fiting and continuum regions given in rest frame wavelengths with
    astropy angstrom units.

    Maskout is given in terms of doppler shift

    """

    # print 'Warning: Renormalising!'
    # flux = flux * 1e18
    # err = err * 1e18 

    # Transform to quasar rest-frame
    wav =  wav / (1.0 + z)
    wav = wav*u.AA

    # Check if continuum is given in wavelength or doppler units 
    if continuum_region[0].unit == (u.km/u.s):
        continuum_region[0] = doppler2wave(continuum_region[0], w0)  
    if continuum_region[1].unit == (u.km/u.s):
        continuum_region[1] = doppler2wave(continuum_region[1], w0)  

    # index is true in the region where we fit the continuum
    continuum = ((wav > continuum_region[0][0]) & \
                 (wav < continuum_region[0][1])) | \
                 ((wav > continuum_region[1][0]) & \
                 (wav < continuum_region[1][1]))

    # index of the region we want to fit
    if fitting_region.unit == (u.km/u.s):
        fitting_region = doppler2wave(fitting_region, w0)  
    
    fitting = (wav > fitting_region[0]) & (wav < fitting_region[1])


    xdat = wav[continuum].value
    ydat = flux[continuum]
    yerr = err[continuum]

    bkgdmod = PowerLawModel()
    bkgdpars = bkgdmod.make_params()
    bkgdpars['exponent'].value = 1.0
    bkgdpars['amplitude'].value = 1.0

    out = minimize(resid,
                   bkgdpars,
                   args=(xdat, bkgdmod, ydat, yerr),
                   method='leastsq')

    if verbose:
        print fit_report(bkgdpars)
  

    # subtract continuum, define region for fitting
    xdat = wav[fitting]
    ydat = flux[fitting] - resid(bkgdpars, wav[fitting].value, bkgdmod)
    yerr = err[fitting]

    # Transform to doppler shift
    vdat = wave2doppler(xdat, w0)

    # Add velocity shift
    vdat = vdat - velocity_shift

    """
    Remember that this is to velocity shifted array

    Accepts units km/s or angstrom (observed frame)
    """

    if maskout is not None:

        if maskout.unit == (u.km/u.s):

            mask = np.array([True] * len(vdat))
            for item in maskout:
                print 'Not fitting between {0} and {1}'.format(item[0], item[1])
                mask[(vdat > item[0]) & (vdat < item[1])] = False


        elif maskout.unit == (u.AA):

            mask = np.array([True] * len(vdat))
            for item in maskout:
                vlims = wave2doppler(item / (1.0 + z), w0) - velocity_shift
                print 'Not fitting between {0} ({1}) and {2} ({3})'.format(item[0], vlims[0], item[1], vlims[1])
                mask[(xdat > (item[0] / (1.0 + z))) & (xdat < (item[1] / (1.0 + z)))] = False

        else:
            print "Units must be km/s or angstrom"

        vdat = vdat[mask]
        ydat = ydat[mask]
        yerr = yerr[mask]

    # Calculate mean and variance 
    p = ydat / np.sum(ydat)
    m = np.sum(vdat * p) 
    v = np.sum(p * (vdat-m)**2)
    sd = np.sqrt(v)  

    vs = np.linspace(vdat.min(), vdat.max(), 1000)

    pars = Parameters() 

    pars.add('amp0', value = 1.0, min=0.0) 
    pars.add('sig0', value = 1.0, min=0.05) 
    pars.add('cen0', value = 0.0, min=vdat.min().value/sd.value, max=vdat.max().value/sd.value) 


    if order > 0: 
        pars.add('amp1', value = 1.0, min=0.0) 
        pars.add('sig1', value = 1.0, min=0.05) 
        pars.add('cen1', value = 0.0, min=vdat.min().value/sd.value, max=vdat.max().value/sd.value) 

    if order > 1:    
        pars.add('amp2', value = 1.0, min=0.0) 
        pars.add('sig2', value = 1.0, min=0.05) 
        pars.add('cen2', value = 0.0, min=vdat.min().value/sd.value, max=vdat.max().value/sd.value) 
    
    if order > 2:
        pars.add('amp3', value = 1.0, min=0.0) 
        pars.add('sig3', value = 1.0, min=0.05) 
        pars.add('cen3', value = 0.0, min=vdat.min().value/sd.value, max=vdat.max().value/sd.value) 
    
    if order > 3:
        pars.add('amp4', value = 1.0, min=0.0) 
        pars.add('sig4', value = 1.0, min=0.05) 
        pars.add('cen4', value = 0.0, min=vdat.min().value/sd.value, max=vdat.max().value/sd.value) 
    
    if order > 4:
        pars.add('amp5', value = 1.0, min=0.0) 
        pars.add('sig5', value = 1.0, min=0.05) 
        pars.add('cen5', value = 0.0, min=vdat.min().value/sd.value, max=vdat.max().value/sd.value) 
    
    if order > 5:
        pars.add('amp6', value = 1.0, min=0.0) 
        pars.add('sig6', value = 1.0, min=0.05) 
        pars.add('cen6', value = 0.0, min=vdat.min().value/sd.value, max=vdat.max().value/sd.value) 


    out = minimize(gh_resid,
                   pars,
                   args=(vdat.value/sd.value, order, ydat, yerr))

    if verbose:
        print fit_report(pars)


    # Save results

    if save_dir is not None:

        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        param_file = os.path.join(save_dir, 'my_params.txt')
        parfile = open(param_file, 'w')
        pars.dump(parfile)
        parfile.close()

        vdat_file = os.path.join(save_dir, 'vdat.txt')
        parfile = open(vdat_file, 'wb')
        pickle.dump(vdat, parfile, -1)
        parfile.close()

        ydat_file = os.path.join(save_dir, 'ydat.txt')
        parfile = open(ydat_file, 'wb')
        pickle.dump(ydat, parfile, -1)
        parfile.close()


        yerr_file = os.path.join(save_dir, 'yerr.txt')
        parfile = open(yerr_file, 'wb')
        pickle.dump(yerr, parfile, -1)
        parfile.close()

    # Calculate FWHM of distribution

    integrand = lambda x: gh_resid(pars, x, order)
    
    func_center = optimize.fmin(lambda x: -integrand(x) , 0)[0]
    
    print 'Peak: {}'.format(func_center * sd.value)
    
    half_max = integrand(func_center) / 2.0

    root1 = optimize.brentq(lambda x: integrand(x) - half_max, vdat.min().value, func_center)
    root2 = optimize.brentq(lambda x: integrand(x) - half_max, func_center, vdat.max().value)

    print 'FWHM: {}'.format((root2 - root1)* sd.value)

    dv = 1.0   

    xs = np.arange(vdat.min().value, vdat.max().value, dv) / sd.value      
    
    norm = np.sum(integrand(xs) * dv)
    pdf = integrand(xs) / norm
    cdf = np.cumsum(pdf) 

    md = xs[np.argmin( np.abs( cdf - 0.5))]
    print 'Median: {}'.format(md * sd.value)

    m = np.sum(xs * pdf * dv) 
    print 'Mean: {}'.format(m * sd.value)

    """
    This is working, but for Lorentzian the second moment is not defined. 
    It dies off much less quickly than the Gaussian so the sigma is much 
    larger. I therefore need to think of the range in which I calcualte 
    sigma
    """

    v = np.sum( (xs-m)**2 * pdf * dv )
    sigma = np.sqrt(v)
    print 'Second moment: {}'.format(sigma * sd.value) 

    if plot:
        plot_fit(wav=wav,
                 flux = flux - resid(bkgdpars, wav.value, bkgdmod),
                 err=err,
                 wav_mod=vs,
                 flux_mod=gausshermite(vs.value/sd.value, pars, order),
                 plot_savefig = plot_savefig,
                 maskout = maskout,
                 z=z,
                 w0=w0,
                 continuum_region=continuum_region,
                 fitting_region=fitting_region,
                 plot_region=plot_region,
                 plot_title=plot_title)

    return None


if __name__ == '__main__':

    from get_spectra import get_boss_dr12_spec
    import matplotlib.pyplot as plt

    wav, dw, flux, err = get_boss_dr12_spec('SDSSJ123611.21+112921.6')

    fit_line(wav,
             flux,
             err,
             z=2.155473,
             w0=np.mean([1548.202,1550.774])*u.AA,
             continuum_region=[[1445.,1465.]*u.AA,[1700.,1705.]*u.AA],
             fitting_region=[1460.,1580.]*u.AA,
             plot_region=[1440,1720]*u.AA,
             maskout=[[-15610,-11900],[-3360,-2145],[135,485],[770,1024]]*(u.km/u.s),
             plot=True,
             save_dir='/data/lc585/WHT_20150331/NewLineFits/SDSSJ123611.21+112921.6/gausshermite/CIV')
    plt.show() 
