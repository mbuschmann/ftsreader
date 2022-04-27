# FTSReader

## FTSReader class
This is a native Python class to read Fourier-Transform InfraRed (FTIR) interferograms and spectra created within the TCCON (Total Carbon Column Observing Network) and NDACC-IRWG (Network for the detection of Atmospheric Composition Change InfraRed Working Group) communities.

The data blocks are provided as NumPy arrays and the header information as a dictionary.

## GUI to view interferograms and spectra
An additional script *spc_checker.py* provides a PyQt5 graphical user interface to review the interferograms and spectra in a specific folder and to save a list of selected spectra to a file.

Usage:
    python spc_checker.py [interferograms/spectra folder] [path to textfile for saving selection list]


# tools

contains several tools to work with the spectra read by ftsreader
load: import tools

spec = average(<list of files>, av_spc, av_ifg) averages spectra or interferograms
	      	 	 x-axis must be the same
			 result is a two dimnsional array
spec = divide (spec1. spec2, interpolate) calculates spec1/spec2,
       	      	      	     if interpolate = True: spec2 is interpolated to the
       	       	      	     		       		   wavenumber-axis of spec1
		             if normailse = True: spectrum is normalised to be between 0 1nd 1