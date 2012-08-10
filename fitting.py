# -*- coding: utf-8 -*-
# vim: set autoindent shiftwidth=4 softtabstop=4 expandtab:

"""
This module contains many tools for fitting data
"""

import numpy as np
import inspect
import scipy.constants as C
from scipy.special import jn
from scipy.optimize import leastsq
# see also scipy.optimize.curve_fit
import matplotlib.pylab as plt
import collections

def xcothx(x):
    """
    This functions returns the x/tanh(x) and does the proper thing
    when x=0.
    """
    # similar to sinc function
    x = np.asanyarray(x)
    # remove 0 from x
    nx = np.where(x==0, 1e-16, x)
    # 1e-8 is enough to give exactly 1.
    #return where(x==0, 1., nx/tanh(nx))
    return nx/np.tanh(nx)

def noisePower(V, T, R=50.):
    """
    Use this function to fit the noise power (from a diode).
    T is in Kelvin
    V in Volts is the dc voltage on the sample
    R in Ohms of the tunnel junction
    The returned values is the noise power density.
    i.e. (I-Iavg)^2
    The current is obtained by integrating over the bandwidth.

    For V=0, this is 4 kB T/R
    For large V this tends to 2e V/R
    """
    kbt = C.k*T
    v = C.e * V / (2.*kbt)
    return xcothx(v) * (4.*kbt/R)
noisePower.display_str = r"$2e\frac{V}{R} \coth\left(\frac{eV}{2k_B T}\right)$"

def noisefitV(V, T, A, Toffset, R=50.):
    """
    Use this function to fit. Based on noisePower.
    Use this when you know the applied DC voltage (in volts) on the sample.
    A is the scale of the fit. It contains the effect of the
    bandwidth and the amplifiers gains. In the measurement unit.
    The Toffset is in units of Kelvin and is the noise temperature of the
    amplifiers, assuming Ro=50 Ohms.
    """
    kbt = C.k*T
    offset = 4.*C.k*Toffset/50.
    Aunit = 4.*kbt/R
    return A*(noisePower(V, T, R)+offset)/Aunit
noisefitV.display_str = r"$\frac{A}{4k_B T/R}\left(2e\frac{V}{R} \coth\left(\frac{eV}{2k_B T}\right) +\frac{4 k_B T_{offset}}{50})\right)$"

def noisefitI(I, T, A, Toffset, R=50.):
    """
    Use this function to fit. Based on noisePower.
    Use this when you know the applied DC current (in amps) on the sample.
    A is the scale of the fit. It contains the effect of the
    bandwidth and the amplifiers gains. In the measurement unit.
    The Toffset is in units of Kelvin and is the noise temperature of the
    amplifiers, assuming Ro=50 Ohms.
    """
    kbt = C.k*T
    offset = 4.*C.k*Toffset/50.
    Aunit = 4.*kbt/R
    return A*(noisePower(I*R, T, R)+offset)/Aunit
noisefitI.display_str = r"$\frac{A}{4k_B T/R}\left(2eI \coth\left(\frac{eIR}{2k_B T}\right) +\frac{4 k_B T_{offset}}{50})\right)$"

def noiseRF(Vdc, T, Vac, f, R=50., N=100):
    """
    Vdc in Volts
    RF signal of Vac (Volts peak) at frequency f (Hz)
    T in Kelvin
    R in Ohms of the junction.
    N is the limit of the sum of bessels (from -N to +N)
    """
    hf = C.h*f
    kbt = C.k*T
    ev = C.e*Vdc
    vac = C.e*Vac/hf
    n = np.arange(-N, N+1)[:,None]
    x=(ev-n*hf)/(2.*kbt)
    tmp = jn(n,vac)**2 *xcothx(x)
    return tmp.sum(axis=0) * (4*kbt/R)
noiseRF.display_str = r"$\frac{4 k_B T}{R} \sum_{n=-N}^{N} J_n(e V_{AC}/hf)^2 \frac{e V_{DC}-nhf}{2 k_B T} \coth\left(\frac{e V_{DC}-nhf}{2 k_B T}\right)$"


def noiseRFfit(Vdc, T, A, Toffset, Vac, f=20e9, R=70., N=100):
    """
    A is the scale of the fit. It contains the effect of the
    bandwidth and the amplifiers gains. In the measurement unit.
    The Toffset is in units of Kelvin and is the noise temperature of the
    amplifiers, assuming Ro=50 Ohms.

    Vdc in Volts
    RF signal of Vac (Volts peak) at frequency f (Hz)
    T in Kelvin
    R in Ohms of the junction.
    N is the limit of the sum of bessels (from -N to +N)
    """
    kbt = C.k*T
    offset = 4.*C.k*Toffset/50.
    Aunit = 4.*kbt/R
    return A*(noiseRF(Vdc, T, Vac, f, R, N)+offset)/Aunit
noiseRFfit.display_str = r"$ A \left(\left[\sum_{n=-N}^{N} J_n(e V_{AC}/hf)^2 \frac{e V_{DC}-nhf}{2 k_B T} \coth\left(\frac{e V_{DC}-nhf}{2 k_B T} \right)\right] + T_{offset}/T\right)$"



#########################################################
def getVarNames(func):
    """
    This function finds the name of the parameter as used in the function
    definition.
    It returns a tuple (para, kwpara, varargs, varkw, defaults)
    Where para is a list of the name positional parameters
          kwpara is a list of the keyword parameters
          varargs and varkw ar the name for the *arg and **kwarg
           paramters. They are None if not present.
          defaults are the default values for the kwpara
    """
    (args, varargs, varkw, defaults) = inspect.getargspec(func)
    Nkw = len(defaults)
    Nall = len(args)
    Narg = Nall-Nkw
    para = args[:Narg]
    kwpara = args[Narg:]
    return (para, kwpara, varargs, varkw, defaults)

def toEng(p, pe, signif=2):
    if pe != 0:
        pe10 = np.log10(np.abs(pe))
    else:
        pe10 = 0
    if p != 0:
        p10 = np.log10(np.abs(p))
    else:
        p10 = pe10
    pe10f = int(np.floor(pe10))
    p10f = int(np.floor(p10))
    #For pe make the rescaled value
    # between 9.9 and 0.010
    pe10Eng = (int(np.floor(pe10+2))/3)*3.
    #For p make the rescaled value
    # between 499 and 0.5
    p10Eng = (int(np.floor(p10 - np.log10(.5)))/3)*3.
    if pe != 0:
        expEng = max(pe10Eng, p10Eng)
        frac_prec = signif-1 - (pe10f-expEng)
    else:
        expEng = p10Eng
        frac_prec = 15-(p10f-expEng) #15 digit of precision
    if frac_prec < 0:
        frac_prec = 0
    pe_rescaled = pe/10.**expEng
    p_rescaled = p/10.**expEng
    return p_rescaled, pe_rescaled, expEng, frac_prec

def convVal(p, pe, signif=2):
    # handle one p, pe at a time
    p_rescaled, pe_rescaled, expEng, frac_prec = toEng(p, pe, signif=signif)
    if pe == 0:
        if p == 0:
            return '0', None, '0'
        else:
            return ( ('%%.%if'%frac_prec)%p_rescaled, None, '%i'%expEng )
    else:
        return ( ('%%.%if'%frac_prec)%p_rescaled,
                 ('%%.%if'%frac_prec)%pe_rescaled, '%i'%expEng )

def printResult(func, p, pe, extra={}, signif=2):
    (para, kwpara, varargs, varkw, defaults) = getVarNames(func)
    N = len(p)
    Npara = len(para) -1
    para = para[1:] # first para is X
    if len(pe) != N:
        raise ValueError, "p and pe don't have the same dimension"
    if Npara > N:
        raise ValueError, "The function has too many positional parameters"
    if Npara < N and varargs == None:
        raise ValueError, "The function has too little positional parameters"
    if Npara < N and varargs != None:
        # create extra names par1, par2, for all needed varargs
        para.extend(['par%i'%(i+1) for i in range(N-Npara)])
    kw = collections.OrderedDict(zip(kwpara, defaults))
    kw.update(extra)
    ret = []
    for n,v,ve in zip(para,p,pe):
        ps, pes, es = convVal(v, ve, signif=signif)
        if pes == None:
            ret.append('%s:\t%s\t\tx10$^%s$'%(n, ps, es))
        else:
            ret.append('%s:\t%s\t+- %s\tx10$^%s$'%(n, ps, pes, es))
    ret.extend(['%s:\t%r'%kv for kv in kw.iteritems()])
    return ret

# the argument names from a function are obtained with:
# v=inspect.getargspec(sinc)
# v[0]
# v.args

def fitcurve(func, x, y, p0, yerr=None, extra={}, errors=True, **kwarg):
    """
    func is the function. It needs to be of the form:
          f(x, p1, p2, p3, ..., k1=1, k2=2, ...)
    can also be defined as
          f(x, *ps, **ks)
          where ps will be a list and ks a dictionnary
    where x is the independent variables. All the others are
    the parameters (they can be named as you like)
    The function can also have and attribute display_str that contains
    the function representation in TeX form (func.disp='$a_1 x+b x^2$')

    x is the independent variable (passed to the function).
    y is the dependent variable. The fit will minimize sum((func(x,..)-y)**2)
    p0 is a vector of the initial parameters used for the fit. It needs to be
    at least as long as all the func parameters without default values.

    yerr when given is the value of the sigma (the error) of all the y.
         It needs a shape broadcastable to y, so it can be a constant.

    extra is a way to specify any of the function parameters that
          are not included in the fit. It needs to be a dictionnary.
          It will be passed to the function evaluation as
           func(..., **extra)
          so if extra={'a':1, 'b':2}
          which is the same as extra=dict(a=1, b=2)
          then the function will be effectivaly called like:
           func(..., a=1, b=2)
    errors controls the handling of the yerr.
           It can be True (default), or False.
           When False, yerr are used as fitting weights.
            w = 1/yerr**2

    The kwarg available are the ones for leastsq (see its documentation):
     ftol
     xtol
     gtol
     maxfev
     epsfcn
     factor
     diag

    Returns pf, chi2, pe, extras
      pf is the fit result
      chi2 is the chi square
      pe are the errors on pf
          Without a yerr given, or with a yerr and errors=False,
          it does the neede correction to make chiNornm==1.
          With a yerr given and errors=True: it takes into account
          of the yerr and does not consider chiNorm at all.

      extras is chiNorm, sigmaCorr, s, covar, nfev
       chiNorm is the normalized chi2 (divided by the degree of freedom)
               When the yerr are properly given (and errrors=True), it should
               statistically tend to 1.
       sigmaCorr is the correction factor to give to yerr, or the yerr themselves
                 (if yerr is not given) thats makes chiNornm==1
       s are the errors. It is either yerr, when they are given (and errors=True)
         or the estimated yerr assuming chiNornm==1
       nfev is the number of functions calls
    """
    do_corr = not errors
    if yerr == None:
        yerr = 1.
        do_corr = True
    f = lambda p, x, y, yerr: (y-func(x, *p, **extra))/yerr
    p, cov_x, infodict, mesg, ier = leastsq(f, p0, args=(x, y, yerr), full_output=True, **kwarg)
    if ier not in [1, 2, 3, 4]:
        print 'Problems fitting:', mesg
    chi2 = np.sum(f(p, x, y, yerr)**2)
    Ndof = len(x)- len(p)
    chiNorm = chi2/Ndof
    sigmaCorr = np.sqrt(chiNorm)
    if cov_x != None:
        pe = np.sqrt(cov_x.diagonal())
        pei = 1./pe
        covar =  cov_x*pei[None,:]*pei[:,None]
    else: # can happen when with a singular matrix (very flat curvature in some direction)
        pe = p*0. -1 # same shape as p but with -1
        covar = None
    s = yerr
    if do_corr:
        pe *= sigmaCorr
        s = yerr*sigmaCorr
    extras = dict(mesg=mesg, ier=ier, chiNorm=chiNorm, sigmaCorr=sigmaCorr, s=s, covar=covar, nfev=infodict['nfev'])
    return p, chi2, pe, extras


def fitplot(func, x, y, p0, yerr=None, extra={}, errors=True, fig=None, skip=False, **kwarg):
    """
    This does the same as fitcurve (see its documentation)
    but also plots the data, the fit on the top panel and
    the difference between the fit and the data on the bottom panel.

    fig selects which figure to use. By default it uses the currently active one.
    skip when True, prevents the fitting. This is useful when trying out initial
         parameters for the fit. In this case, the returned values are
         (chi2, chiNorm)
    """
    if fig:
        fig=plt.figure(fig)
    else:
        fig=plt.gcf()
    plt.clf()
    fig, (ax1, ax2) = plt.subplots(2,1, sharex=True, num=fig.number)
    ax1.set_position([.125, .3, .85, .6])
    ax2.set_position([.125, .05, .85, .2])
    plt.sca(ax1)
    plt.errorbar(x, y, yerr=yerr, fmt='.', label='data')
    xx= np.linspace(x.min(), x.max(), 1000)
    pl = plt.plot(xx, func(xx, *p0, **extra), 'r-')[0]
    plt.sca(ax2)
    plt.cla()
    plt.errorbar(x, y-func(x, *p0, **extra), yerr=yerr, fmt='.')
    plt.draw()
    if not skip:
        p, resids, pe, extras = fitcurve(func, x, y, p0, yerr=yerr, extra=extra, **kwarg)
        #xx.set_ydata(func(xx, *p, **extra))
        plt.sca(ax1)
        plt.cla()
        plt.errorbar(x, y, yerr=extras['s'], fmt='.', label='data')
        plt.plot(xx, func(xx, *p, **extra), 'r-')
        plt.sca(ax2)
        plt.cla()
        plt.errorbar(x, y-func(x, *p, **extra), yerr=extras['s'], fmt='.')
        try:
            plt.sca(ax1)
            plt.title(func.display_str)
        except AttributeError: # No display_str
            pass
        plt.draw()
        return p, resids, pe, extras
    else:
        if yerr==None:
            yerr=1
        f = lambda p, x, y, yerr: (y-func(x, *p, **extra))/yerr
        chi2 = np.sum(f(p0, x, y, yerr)**2)
        Ndof = len(x)- len(p0)
        chiNorm = chi2/Ndof
        return chi2, chiNorm

if __name__ == "__main__":
    import gen_poly
    N = 200
    x = np.linspace(-0.22e-3, 0.21e-3, N)
    y = noiseRFfit(x, 0.069, -.22e-3, 8., 0.113e-3, f=20e9, R=70., N=100)
    y += np.random.randn(N) * 1e-5
    res = fitcurve(noiseRFfit, x, y,[0.05, -.003,4.,.01e-3], extra=dict(N=10,f=20e9))
    fitplot(noiseRFfit, x, y,[.05, -.003,4.,.01e-3], extra=dict(N=10,f=20e9),skip=1, fig=1)
    res2 = fitplot(noiseRFfit, x, y,[.05, -.003,4.,.01e-3], extra=dict(N=10,f=20e9), fig=2)
    res3 = fitplot(noiseRFfit, x, y,[.05, -.003,4.,.01e-3], extra=dict(N=10,f=20e9), yerr=1e-5, fig=3)
    res4 = fitplot(noiseRFfit, x, y,[.05, -.003,4.,.01e-3], extra=dict(N=10,f=20e9), yerr=1e-6, fig=4)
    print '-----------------------------------------'
    print ' Comparison with poly fit'
    linfunc = lambda x, b, m, c:   c*x**2 + m*x + b
    yl = linfunc(x, 1.e-3,2,3.e3)
    yl += np.random.randn(N) * 2e-5
    yerr = 2e-5
    #yerr = 1e-4
    #yerr = None
    resnl = fitcurve(linfunc, x, yl,[1,1,1], yerr=yerr)
    fitplot(linfunc, x, yl,[1e-3,2.,3.e3],fig=5, yerr=yerr, skip=True)
    print resnl
    resp = gen_poly.gen_polyfit(x, yl, 3, s=yerr)
    print resp
    print '-----------------------------------------'
    plt.show()
