from ftsreader import ftsreader
import numpy as np

def average(flist, av_spc=False, av_ifg=False):
    # flist list of all files which are to be averaged
    # av_spc, av_ifg average spectra and interfergrams respectively.
    # create list with e.g.
    # list(map(lambda x: flt.match(x) != None and flt.match(x).group(0), os.listdir(ppath)))

    if not av_spc and not av_ifg:
        print('Nothing to be averaged?')
        return(-1)
    
    sp = ftsreader(flist[0], getspc=av_spc, getifg=av_ifg)
    if av_spc:
        spcwvn=sp.spcwvn.copy()
        spc = sp.spc.copy()
        nr = 1
        
    for ff in flist:
        sp = ftsreader(ff, getspc=av_spc, getifg=av_ifg)
        if np.any (spcwvn != sp.spcwvn):
            print('Different wavenumbers')
            return(-1)
        spc += sp.spc
        nr += 1


    spc /= nr
    print (np.std(spc[100:]))

    return(np.vstack((spcwvn,spc)).T)
        
def divide_spectra(spec1, spec2, interpolate=False, normalise=True):
    # calculates spec1/spec2
    # spec = [wavenumber, spectrum]
    # if interpolate = True, spec2 gets interpolated to the wavenumber of spec1
    # if mormailze = True, normailise the spectrum to be between 0 and 1

    if interpolate:
        spec2_ip = spec1.copy()
        spec2_ip[:,1] = np.interp(spec1[:,0], spec2[:,0], spec2[:,1]).copy()
    else:
        spec2_ip = spec2
        
    spec = spec1.copy()

    print(spec1[:,1])
    spec [:,1] = (spec1[:,1]/spec2_ip[:,1]).copy()

    if normalise:
        spec[:,1] /= np.mean(spec[:,1])
    
    return(spec)

def save_spectrum(spec, filename):
    # saves the spectrum in spec to file <filename>
    np.savetxt(filename, spec, delimiter=' ')
