# -*- coding: utf-8 -*-
"""
Created on Sat Aug  1 14:13:56 2015

@author: lc585

Fit emission line with model.

Vary the flux in the fitting region also.

"""
from __future__ import division

import numpy as np
from rebin_spectra import rebin_spectra
import astropy.units as u
from lmfit.models import GaussianModel, LorentzianModel, PowerLawModel, ConstantModel
from lmfit import minimize, Parameters, fit_report
import numpy.ma as ma
#import seaborn as sns
import matplotlib.pyplot as plt
from scipy import integrate, optimize
import os
import cPickle as pickle

def resid(p,x,model,data=None,sigma=None):

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

def wave2doppler(w, w0):

    """
    function uses the Doppler equivalency between wavelength and velocity
    """
    w0_equiv = u.doppler_optical(w0)
    w_equiv = w.to(u.km/u.s, equivalencies=w0_equiv)

    return w_equiv

def doppler2wave(v, w0):

    """
    function uses the Doppler equivalency between wavelength and velocity
    """
    w0_equiv = u.doppler_optical(w0)
    w_equiv = v.to(u.AA, equivalencies=w0_equiv)

    return w_equiv



def fit_line_errors(wav,
                    flux,
                    err,
                    z=0.0,
                    w0=6564.89*u.AA,
                    velocity_shift=0.0*(u.km / u.s),
                    continuum_region=[[6000.,6250.]*u.AA,[6800.,7000.]*u.AA],
                    fitting_region=[6400,6800]*u.AA,
                    plot_region=[6000,7000]*u.AA,
                    nGaussians=0,
                    nLorentzians=1,
                    maskout=None,
                    verbose=True,
                    plot=True,
                    plot_savefig='something.png',
                    plot_title='',
                    save_dir=None):



    """
    Velocity shift added to doppler shift to change zero point (can do if HW10
    redshift does not agree with Halpha centroid)

    Fiting and continuum regions given in rest frame wavelengths with
    astropy angstrom units.

    Maskout is given in terms of doppler shift

    """
    n_samples = 5000

    with open(os.path.join('/data/lc585/WHT_20150331/fit_errors_2',plot_title+'_Ha.dat'), 'w') as f:
        f.write('Name Centroid FWHM Median p99 p95 p90 p80 p60 Mean Sigma EQW \n')

    # print 'Warning: Renormalising!'
    flux = flux * 1e18
    err = err * 1e18

    # Transform to quasar rest-frame
    wav =  wav / (1.0 + z)
    wav = wav*u.AA

    flux_array = np.zeros((len(flux), n_samples))
    for i in range(len(flux)):
        flux_array[i,:] = np.random.normal(flux[i], np.abs(err[i]), n_samples)

    # Check if continuum is given in wavelength or doppler units
    if continuum_region[0].unit == (u.km/u.s):
        continuum_region[0] = doppler2wave(continuum_region[0], w0)
    if continuum_region[1].unit == (u.km/u.s):
        continuum_region[1] = doppler2wave(continuum_region[1], w0)

    # Fit to median
    blue_inds = (wav > continuum_region[0][0]) & (wav < continuum_region[0][1])
    red_inds = (wav > continuum_region[1][0]) & (wav < continuum_region[1][1])

    blue_flux, red_flux = flux[blue_inds], flux[red_inds]
    blue_err, red_err = err[blue_inds], err[red_inds]
    blue_wav, red_wav = wav[blue_inds], wav[red_inds]

    blue_flux_array = flux_array[blue_inds]
    red_flux_array =  flux_array[red_inds]


    xdat_bkgd = np.array( [continuum_region[0].mean().value, continuum_region[1].mean().value] )
    ydat_bkgd = np.array( [np.median(blue_flux_array,axis=0), np.median(red_flux_array,axis=0) ]).T

    if fitting_region.unit == (u.km/u.s):
        fitting_region = doppler2wave(fitting_region, w0)

    fitting = (wav > fitting_region[0]) & (wav < fitting_region[1])

    xdat_fit = wav[fitting]
    ydat_fit = flux[fitting]
    yerr_fit = err[fitting]

    flux_array_fit = flux_array[fitting]

    # Transform to doppler shift
    vdat_fit = wave2doppler(xdat_fit, w0)

    # Add velocity shift
    vdat_fit = vdat_fit - velocity_shift


    if maskout is not None:

        if maskout.unit == (u.km/u.s):

            mask = np.array([True] * len(vdat_fit))
            for item in maskout:
                print 'Not fitting between {0} and {1}'.format(item[0], item[1])
                mask[(vdat_fit > item[0]) & (vdat_fit < item[1])] = False


        elif maskout.unit == (u.AA):

            mask = np.array([True] * len(vdat_fit))
            for item in maskout:
                vlims = wave2doppler(item / (1.0 + z), w0) - velocity_shift
                print 'Not fitting between {0} ({1}) and {2} ({3})'.format(item[0], vlims[0], item[1], vlims[1])
                mask[(xdat_fit > (item[0] / (1.0 + z))) & (xdat_fit < (item[1] / (1.0 + z)))] = False

        else:
            print "Units must be km/s or angstrom"

        vdat_fit = vdat_fit[mask]
        ydat_fit = ydat_fit[mask]
        yerr_fit = yerr_fit[mask]
        xdat_fit = xdat_fit[mask]

        flux_array_fit = flux_array_fit[mask]

    if plot:

        fig = plt.figure(figsize=(6,10))

        fit = fig.add_subplot(3,1,1)
        fit.set_xticklabels( () )
        residuals = fig.add_subplot(3,1,2)

        blue_cont = wave2doppler(continuum_region[0], w0) - velocity_shift
        red_cont = wave2doppler(continuum_region[1], w0) - velocity_shift

        fit.axvspan(blue_cont.value[0], blue_cont.value[1], color='grey', lw = 1, alpha = 0.2 )
        fit.axvspan(red_cont.value[0], red_cont.value[1], color='grey', lw = 1, alpha = 0.2 )

        residuals.axvspan(blue_cont.value[0], blue_cont.value[1], color='grey', lw = 1, alpha = 0.2 )
        residuals.axvspan(red_cont.value[0], red_cont.value[1], color='grey', lw = 1, alpha = 0.2 )

        # Mark fitting region
        fr = wave2doppler(fitting_region, w0) - velocity_shift

        # Mask out regions
        xdat_masking = np.arange(xdat_fit.min().value, xdat_fit.max().value, 0.05)*(u.AA)
        vdat_masking = wave2doppler(xdat_masking, w0) - velocity_shift

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

        fit.set_ylabel(r'F$_\lambda$', fontsize=12)
        residuals.set_xlabel(r"$\Delta$ v (kms$^{-1}$)", fontsize=12)
        residuals.set_ylabel("Residual")

        if plot_region.unit == (u.km/u.s):
            plot_region = doppler2wave(plot_region, w0)

        plot_region_inds = (wav > plot_region[0]) & (wav < plot_region[1])
        plotting_limits = wave2doppler(plot_region, w0) - velocity_shift
        fit.set_xlim(plotting_limits[0].value, plotting_limits[1].value)
        residuals.set_xlim(fit.get_xlim())

    for k in range(n_samples):

        # fit power-law to continuum region
        bkgdmod = PowerLawModel()
        bkgdpars = bkgdmod.make_params()
        bkgdpars['exponent'].value = 1.0
        bkgdpars['amplitude'].value = 1.0

        out = minimize(resid,
                       bkgdpars,
                       args=(xdat_bkgd, bkgdmod, ydat_bkgd[k]),
                       method='nelder')

        out = minimize(resid,
                       bkgdpars,
                       args=(xdat_bkgd, bkgdmod, ydat_bkgd[k]),
                       method='leastsq')

        if verbose:
            print fit_report(bkgdpars)


        # subtract continuum, define region for fitting
        ydat_fit_bkgdsub = ydat_fit - resid(bkgdpars, xdat_fit.value, bkgdmod)
        flux_array_fit_bkgdsub = flux_array_fit - resid(bkgdpars, xdat_fit.value, bkgdmod).reshape(len(ydat_fit),1)

        bkgd = ConstantModel()
        mod = bkgd
        pars = bkgd.make_params()

        # A bit unnessesary, but I need a way to do += in the loop below
        pars['c'].value = 0.0
        pars['c'].vary = False


        for i in range(nGaussians):
            gmod = GaussianModel(prefix='g{}_'.format(i))
            mod += gmod
            pars += gmod.guess(ydat_fit, x=vdat_fit.value)

        for i in range (nLorentzians):
            lmod = LorentzianModel(prefix='l{}_'.format(i))
            mod += lmod
            pars += lmod.guess(ydat_fit, x=vdat_fit.value)

        for i in range(nGaussians):
            pars['g{}_center'.format(i)].value = 0.0
            pars['g{}_center'.format(i)].min = -5000.0
            pars['g{}_center'.format(i)].max = 5000.0
            pars['g{}_amplitude'.format(i)].min = 0.0
            pars['g{}_sigma'.format(i)].min = 400.0
            pars['g{}_sigma'.format(i)].max = 10000.0

        for i in range(nLorentzians):
            pars['l{}_center'.format(i)].value = 0.0
            pars['l{}_center'.format(i)].min = -10000.0
            pars['l{}_center'.format(i)].max = 10000.0
            pars['l{}_amplitude'.format(i)].min = 0.0

        # For Ha
        if nGaussians == 2:
            pars['g1_center'].set(expr = 'g0_center')
        if nGaussians == 3:
            pars['g1_center'].set(expr = 'g0_center')
            pars['g2_center'].set(expr = 'g0_center')

        flux_array_fit_bkgdsub[:,k][flux_array_fit_bkgdsub[:,k] < 0.0] = 0.0

        out = minimize(resid,
                       pars,
                       args=(np.asarray(vdat_fit), mod, flux_array_fit_bkgdsub[:,k], yerr_fit),
                       method ='nelder')

        out = minimize(resid,
                       pars,
                       args=(np.asarray(vdat_fit), mod, flux_array_fit_bkgdsub[:,k], yerr_fit),
                       method ='leastsq')


        # print fit_report(pars)
        # print out.redchi
        # Calculate FWHM of distribution

        integrand = lambda x: mod.eval(params=pars, x=np.array(x))
        func_center = optimize.fmin(lambda x: -integrand(x) , 0, disp=False)[0]

        try:

            half_max = mod.eval(params=pars, x=func_center) / 2.0
            root1 = optimize.brentq(lambda x: integrand(x) - half_max, vdat_fit.min().value, func_center)
            root2 = optimize.brentq(lambda x: integrand(x) - half_max, func_center, vdat_fit.max().value)

        except ValueError as e:
            print e

            root1, root2 = np.nan, np.nan

        # print 'FWHM: {}'.format(root2 - root1)

        dv = 1.0

        xs = np.arange(func_center - 10000.0, func_center + 10000.0, dv)
        # xs = np.arange(vdat_fit.min().value, vdat_fit.max().value, dv)
        #xs = np.arange(-3e4, 3e4, dv)

        norm = integrate.quad(integrand, vdat_fit.min().value, vdat_fit.max().value)[0]
        pdf = integrand(xs) / norm
        cdf = np.cumsum(pdf)
        cdf_r = np.cumsum(pdf[::-1])[::-1] # reverse cumsum

        md = xs[np.argmin( np.abs( cdf - 0.5))]
        # print 'Median: {}'.format(md)


        # Not sure this would work if median far from zero but probably would never happen.
        p99 = np.abs(xs[np.argmin(np.abs(cdf_r - 0.005))] - xs[np.argmin(np.abs(cdf - 0.005))])
        p95 = np.abs(xs[np.argmin(np.abs(cdf_r - 0.025))] - xs[np.argmin(np.abs(cdf - 0.025))])
        p90 = np.abs(xs[np.argmin(np.abs(cdf_r - 0.05))] - xs[np.argmin(np.abs(cdf - 0.05))])
        p80 = np.abs(xs[np.argmin(np.abs(cdf_r - 0.1))] - xs[np.argmin(np.abs(cdf - 0.1))])
        p60 = np.abs(xs[np.argmin(np.abs(cdf_r - 0.2))] - xs[np.argmin(np.abs(cdf - 0.2))])

        # print '99%: {}'.format(p99)
        # print '95%: {}'.format(p95)
        # print '90%: {}'.format(p90)
        # print '80%: {}'.format(p80)
        # print '60%: {}'.format(p60)

        m = np.sum(xs * pdf * dv)
        # print 'Mean: {}'.format(m)

        """
        This is working, but for Lorentzian the second moment is not defined.
        It dies off much less quickly than the Gaussian so the sigma is much
        larger. I therefore need to think of the range in which I calcualte
        sigma
        """

        v = np.sum( (xs-m)**2 * pdf * dv )
        sd = np.sqrt(v)
        # print 'Second moment: {}'.format(sd)

        # print 'chi-squred: {0}, dof: {1}'.format(out.chisqr, out.nfree)

        # Equivalent width
        xs = np.arange(func_center - 10000.0, func_center + 10000.0, dv)
        flux_line = integrand(xs)
        xs_wav = doppler2wave(xs*(u.km/u.s),w0)
        flux_bkgd = bkgdmod.eval(params=bkgdpars, x=xs_wav.value)
        f = (flux_line + flux_bkgd) / flux_bkgd
        eqw = (f[:-1] - 1.0) * np.diff(xs_wav.value)
        eqw = np.nansum(eqw)

        with open(os.path.join('/data/lc585/WHT_20150331/fit_errors_2',plot_title+'_Ha.dat'), 'a') as f:
            f.write('{0} {1:.2f} {2:.2f} {3:.2f} {4} {5} {6} {7} {8} {9:.2f} {10:.2f} {11:.3f}\n'.format(plot_title,
                                                                                                         func_center,
                                                                                                         root2 - root1,
                                                                                                         md,
                                                                                                         p99,
                                                                                                         p95,
                                                                                                         p90,
                                                                                                         p80,
                                                                                                         p60,
                                                                                                         m,
                                                                                                         sd,
                                                                                                         eqw))

        print k

        if plot:

            xdat_plot = wav[plot_region_inds]
            vdat_plot = wave2doppler(xdat_plot, w0)
            ydat_plot = flux_array[plot_region_inds,k] - resid(bkgdpars, wav[plot_region_inds].value, bkgdmod)
            yerr_plot = err[plot_region_inds]


            if 'pts1' in locals():
                pts1.set_data((vdat_plot.value, ydat_plot))
            else:
                pts1, = fit.plot(vdat_plot.value, ydat_plot)

            if 'pts2' in locals():
                pts2.set_data((vdat_plot.value,ydat_plot - resid(pars, vdat_plot.value, mod)))
            else:
                pts2, = residuals.plot(vdat_plot.value,
                                       ydat_plot - resid(pars, vdat_plot.value, mod))

            vs = np.linspace(vdat_plot.min().value, vdat_plot.max().value, 1000)

            if 'line' in locals():
                line.set_data((vs, resid(pars, vs, mod)))
            else:
                line, = fit.plot(vs, resid(pars, vs, mod), color='black')


            # plot model components
            i, j = 0, 0
            for key, value in pars.valuesdict().iteritems():
                if key.startswith('g'):
                    i += 1
                if key.startswith('l'):
                    j += 1

            ngaussians = int(float(i) / 4.0)

            if ngaussians == 2:

                comp_mod = GaussianModel()
                comp_p = comp_mod.make_params()

                for key, v in comp_p.valuesdict().iteritems():
                    comp_p[key].value = pars['g0' + '_' + key].value

                if 'line_g0' in locals():
                    line_g0.set_data((np.sort(vdat_plot.value), comp_mod.eval(comp_p, x=np.sort(vdat_plot.value))))
                else:
                    line_g0, = fit.plot( np.sort(vdat_plot.value), comp_mod.eval(comp_p, x=np.sort(vdat_plot.value)) )


                comp_mod = GaussianModel()
                comp_p = comp_mod.make_params()

                for key, v in comp_p.valuesdict().iteritems():
                    comp_p[key].value = pars['g1' + '_' + key].value

                if 'line_g1' in locals():
                    line_g1.set_data((np.sort(vdat_plot.value), comp_mod.eval(comp_p, x=np.sort(vdat_plot.value))))
                else:
                    line_g1, = fit.plot( np.sort(vdat_plot.value), comp_mod.eval(comp_p, x=np.sort(vdat_plot.value)) )

            fig.set_tight_layout(True)

            plt.pause(0.1)

    plt.close()


    return None

###Testing###

# if __name__ == '__main__':

#     from get_spectra import get_liris_spec
#     import matplotlib.pyplot as plt

#     class PlotProperties(object):

#         def __init__(self,
#                      sdss_name,
#                      boss_name,
#                      z,
#                      civ_gh_order,
#                      civ_rebin,
#                      civ_nGaussians,
#                      civ_nLorentzians,
#                      civ_continuum_region,
#                      civ_fitting_region,
#                      civ_maskout,
#                      civ_red_shelf,
#                      ha_gh_order,
#                      ha_rebin,
#                      ha_nGaussians,
#                      ha_nLorentzians,
#                      ha_continuum_region,
#                      ha_fitting_region,
#                      ha_maskout,
#                      name):

#             self.sdss_name = sdss_name
#             self.boss_name = boss_name
#             self.z = z
#             self.civ_gh_order = civ_gh_order
#             self.civ_rebin = civ_rebin
#             self.civ_nGaussians = civ_nGaussians
#             self.civ_nLorentzians = civ_nLorentzians
#             self.civ_continuum_region = civ_continuum_region
#             self.civ_fitting_region = civ_fitting_region
#             self.civ_maskout = civ_maskout
#             self.civ_red_shelf = civ_red_shelf
#             self.ha_gh_order = ha_gh_order
#             self.ha_rebin = ha_rebin
#             self.ha_nGaussians = ha_nGaussians
#             self.ha_nLorentzians = ha_nLorentzians
#             self.ha_continuum_region = ha_continuum_region
#             self.ha_fitting_region = ha_fitting_region
#             self.ha_maskout =  ha_maskout
#             self.name = name

#     SDSSJ1104 = PlotProperties(sdss_name = 'SDSSJ110454.73+095714.8',
#                             boss_name = 'SDSSJ110454.73+095714.8',
#                             z = 2.421565,
#                             civ_gh_order = 6,
#                             civ_rebin  = 2,
#                             civ_nGaussians = 0,
#                             civ_nLorentzians = 1,
#                             civ_continuum_region=[[1445.,1465.]*u.AA,[1700.,1705.]*u.AA],
#                             civ_fitting_region=[1500.,1600.]*u.AA,
#                             civ_maskout  = [[5238.3, 5250.4], [5254.0, 5263.7], [5573.14, 5583.42]]*u.AA,
#                             civ_red_shelf = [1600,1690]*u.AA,
#                             ha_gh_order = 4,
#                             ha_rebin  = 2,
#                             ha_nGaussians  = 2,
#                             ha_nLorentzians = 0,
#                             ha_continuum_region=[[6000.,6250.]*u.AA,[10800,12800]*(u.km/u.s)],
#                             ha_fitting_region=[6400,6800]*u.AA,
#                             ha_maskout  = None,
#                             name = 'SDSSJ1104+0957')


#     fname = os.path.join('/data/lc585/WHT_20150331/html/',SDSSJ1104.name,'tcdimcomb.ms.fits')

#     print SDSSJ1104.sdss_name

#     wav, dw, flux, err = get_liris_spec(fname)

#     fit_line_errors(wav,
#                     flux,
#                     err,
#                     z=SDSSJ1104.z,
#                     w0=6564.89*u.AA,
#                     velocity_shift=0.0*(u.km / u.s),
#                     continuum_region=SDSSJ1104.ha_continuum_region,
#                     fitting_region=SDSSJ1104.ha_fitting_region,
#                     plot_region=[5900,7400]*u.AA,
#                     nGaussians=SDSSJ1104.ha_nGaussians,
#                     nLorentzians=SDSSJ1104.ha_nLorentzians,
#                     maskout=SDSSJ1104.ha_maskout,
#                     verbose=False,
#                     plot=True,
#                     plot_savefig=os.path.join('/data/lc585/WHT_20150331/NewLineFits3/',SDSSJ1104.sdss_name+'_Ha.pdf'),
#                     plot_title=SDSSJ1104.sdss_name,
#                     save_dir=os.path.join('/data/lc585/WHT_20150331/NewLineFits3/',SDSSJ1104.sdss_name,'Ha'))