#!/usr/bin/python3
# coding: utf8

'''
A class providing an interface for accessing header, interferogram and spectrum data blocks from a Fourier-Transform Infrared Spectrometer (FTS).
'''

from __future__ import print_function, division
import os, struct, io, time
import numpy as np

class ftsreader():
    '''Python class to interact with FTS files.\n\n
    Version 2019-08-15\n\n
    Usage:
        ftsreaderobject = ftsreader(path, verbose=False, getspc=False, getifg=False)

    returns an instance of this class, with access to the header and data blocks of the file.

    Example:

        import matplotlib.pyplot as plt

        ftsreaderobject = ftsreader(path, verbose=False, getspc=True)

        ftsreaderobject.print_header()

        if ftsreaderobject.has_block('Data Block SpSm'):
            plt.figure()
            plt.title('Spectrum of '+ftsreaderobject.filename)
            plt.plot(ftsreaderobject.spcwvn, ftsreaderobject.spc, 'k-')
            plt.show()
    '''

    def search_header_par(self, par):
        '''search the header for parameter <par> and return datablock designation '''
        pars = []
        for i in list(self.header.keys()):
            for j in list(self.header[i].keys()):
                if par == j:
                    pars.append(i)
        if len(pars)==1:
            return pars[0]
        elif len(pars)>1:
            if self.verbose: print('Found parameter in multiple datablocks')
            return pars
        else:
            if self.verbose: print('Parameter', par, 'not found in header!')
            return None

    def get_header_par(self, par):
        try:
            return self.header[self.search_header_par(par)][par]
        except:
            print('Parameter not found in header ...')
            return None

    def read_structure(self):
        #t = time.time()
        '''Read the structure of the file and write to ftsreader.fs'''
        # known blocks so far, there is always a block zero, that is still unidentified
        self.__blocknames =    {'160': 'Sample Parameters',
                        '23': 'Data Parameters',
                        '96': 'Optic Parameters',
                        '64': 'FT Parameters',
                        '48': 'Acquisition Parameters',
                        '32': 'Instrument Parameters',
                        '7':  'Data Block',
                        '0':  'something'}
        self.__blocknames2 = {'132': ' ScSm', # another declaration to differentiate blocks between ifg, spc, etc.
                        '4': ' SpSm',
                        '8': ' IgSm',
                        '20': ' TrSm',
                        '12': ' PhSm',
                        b'\x84': ' SpSm/2.Chn.', # some weird stuff going on with python3 decoding here, use binary representation
                        b'\x88': ' IgSm/2.Chn.'}
        self.fs = {}
        fi = self.getfileobject()
        with fi as f: #open(self.path, 'rb') as f:
            f.seek(0)
            self.log.append('Reading structure of file')
            # read beginning of file to assert magic number, total number of blocks and first offset
            # some unidentified numbers in between, do not seem to be necessary for header, spc or ifg blocks
            (magic, something, something, offset1, something, numberofblocks) = struct.unpack('6i', f.read(struct.calcsize('6i')))
            f.seek(offset1) # start at first offset
            for i in range(numberofblocks): # go through all blocks and save all found blocks in self.fs
                s = f.read(struct.calcsize('2BH2i'))
                #read beginning of block, with infos on block types, something yet unidentified/unimportant of size 'H' for now, length and gobal offset of the block
                (blocktype, blocktype2, something, length, offset2) = struct.unpack('2BH2i',s)
                blocktype = str(blocktype)
                blocktype2 = str(blocktype2)
                if blocktype in self.__blocknames.keys():
                    hdrblockname = self.__blocknames[blocktype]
                else:
                    hdrblockname = '[unknown block '+blocktype+']'
                if blocktype2 in self.__blocknames2.keys():
                    hdrblockname += self.__blocknames2[blocktype2]
                else: pass
                self.log.append('Found block '+str(blocktype)+', '+str(blocktype2)+' and identified as '+hdrblockname)
                if blocktype == '0' or blocktype not in self.__blocknames.keys():
                    hdrblockname += ' len %3i' % (length)
                else:
                    pass
                #print(hdrblockname, type(hdrblockname))
                self.fs[hdrblockname] = {'blocktype': blocktype, 'blocktype2': blocktype2, 'length': length, 'offset': offset2}
        fi.close
        #print('read structure\t%1.5f'%(time.time()-t))

    def getfileobject(self):
        # this is used for in-memory-only fts file objects
        if self.filemode == 'hdd':
            fi = open(self.path, 'rb')
        elif self.filemode == 'bytesfromfile':
            with open(self.path, 'rb') as f:
                data = f.read(17428)
            fi = io.BytesIO(data)
        elif self.filemode == 'mem':
            fi = io.BytesIO(self.streamdata)
        else:
            exit('filemode', self.filemode, ' not supported')
        return fi

    def getparamsfromblock(self, offset, length, full=False):
        '''Read all parameters in a block at binary <length> and <offset> and return as dictionary. On request also include binary length and offset of that parameter.'''
        #tt = time.time()
        params = {}
        i=0
        test = True
        fullblock = []
        with open(self.path, 'rb') as f:
            while test:
                f.seek(offset+i) # goto block offset
                s = f.read(8) # read 8 bytes
                para, thistype, length = struct.unpack('4s2H', s) # unpack to get info on how to unpack block
                if full:
                    fullblocktmp = [para, thistype, length, offset+i]
                i+=8
                if struct.unpack('4c', para)[-1]==b'\x00': #get null terminating string
                    para=para[:-1]
                else: pass
                if para[:3] != b'END' and length>0: # if not empty block
                    f.seek(offset+i)
                    data = f.read(2*length)
                    i+=2*length
                    try:
                        if thistype == 0:
                            val = struct.unpack('%1ii'%(len(data)/4), data)[0]
                        elif thistype == 1:
                            val = struct.unpack('%1id'%(len(data)/8), data)[0]
                        elif thistype >= 2 and thistype <=4:
                            t = struct.unpack('%1is'%(2*length), data)[0].decode('ISO-8859-1')
                            t2 = ''
                            for ji in t: # deal with zeros in byte array
                                if ji!='\x00' and type(ji)==str: # in python2 you might want to add ... or type(ji)=='unicode'):
                                    t2 += ji
                                else:
                                    break
                            val=t2
                        else:
                            val= '[read error]'
                        params[para.decode()] = val
                        if full:
                            fullblocktmp.append(val)
                            fullblock.append(fullblocktmp)
                    except Exception as e:
                        print('Exception in getparamsfromblock')
                        self.log.append(e)
                        print (e)
                else:
                    test = False
        #print('getparamsfromblock\t%1.5f'%(time.time()-tt))
        if full:
            return fullblock
        else:
            return params

    def read_header(self):
        '''Read the header and return as a dictionary.'''
        #t = time.time()
        self.log.append('Reading Header ...')
        self.read_structure()
        self.header = {}
        for block in self.fs.keys():
            if block[:10]!='Data Block' and self.fs[block]['length']>0: # if not data block and not empty, try reading header info
                if 'unknown' in block or 'something' in block:
                    pass
                else:
                    try:
                        self.log.append('Reading Header Block: '+block)
                        self.header[block] = self.getparamsfromblock(self.fs[block]['offset'], self.fs[block]['length'], full=False)
                    except Exception as e:
                        print(e)
                        self.log.append(e)
            else: pass
        #print('read_header\t%1.5f'%(time.time()-t))
        return 0

    def fwdifg(self):
        if self.header['Instrument Parameters']['GFW']==1:
            return self.ifg[:len(self.ifg)/2]
        else:
            return None

    def bwdifg(self):
        if self.header['Instrument Parameters']['GBW']==1:
            return self.ifg[len(self.ifg)/2:][::-1]
        else:
            return None

    def print_header(self, getlist=False):
        '''Print a nice representation of the header including the names assigned to the header parameters (not complete). Return list of this if requested via <getlist=True>.'''
        headernames = {'Data Parameters': {
            'DPF': 'Data Point Format',
            'FXV': 'Frequency of First Point',
            'LXV': 'Frequency of Last Point',
            'DAT': 'Date of Measurement',
            'TIM': 'Time of Measurement'},
        'Acquisition Parameters': {
            'AQM': 'Acquisition Mode',
            'HFW': 'Wanted High Frequency Limit',
            'LFW': 'Wanted Low Frequency Limit',
            'NSS': 'Sample Scans',
            'RES': 'Resolution'},
        'FT Parameters': {
            'APF': 'Apodization Function',
            'PHR': 'Phase Resolution',
            'ZFF': 'Zero Filling Factor'},
        'Optic Parameters': {
            'APT': 'Aperture Setting',
            'BMS': 'Beamsplitter Setting',
            'CHN': 'Measurement Channel',
            'DTC': 'Detector Setting',
            'HPF': 'High Pass Filter',
            'LPF': 'Low Pass Filter',
            'OPF': 'Optical Filter Setting',
            'PGN': 'Preamplifier Gain',
            'SRC': 'Source Setting',
            'VEL': 'Scanner Velocity'},
        'Sample Parameters': {},
        'Instrument Parameters': {
            'HFL': 'High Folding Limit',
            'LFL': 'Low Folding Limit',
            'LWN': 'Laser Wavenumber',
            'GFW': 'Number of Good FW Scans',
            'GBW': 'Number of Good BW Scans',
            'BFW': 'Number of Bad FW Scans',
            'BBW': 'Number of Bad BW Scans',
            'PKA': 'Peak Amplitude',
            'PKL': 'Peak Location'},
        }
        headerlist = []
        for i in self.header.keys():
            print(i)
            for j in self.header[i].keys():
                if i in headernames.keys() and j in headernames[i].keys():
                    print('  %3s %030s %030s'%(j, headernames[i][j], self.header[i][j]))
                    headerlist.append((i, j, headernames[i][j], self.header[i][j]))
                else:
                    print('  %3s '%(j)+' '*30+'%030s'%(self.header[i][j]))
                    headerlist.append((i, j, ' ', self.header[i][j]))
        if getlist:
            return headerlist
        else: pass

    def get_block(self, pointer, length):
        '''Get data block from ftsreader.path at <pointer> with length <length>.'''
        #t = time.time()
        self.log.append('Getting data block at '+str(pointer)+' with length '+str(length))
        with open(self.path, 'rb') as f:
            f.seek(pointer)
            dat = np.array(struct.unpack('%1if'%(length), f.read(length*4)))
        #print('get_block\t%1.5f'%(time.time()-t))
        return dat

    def get_datablocks(self, block):
        '''Read a datablock named <block> and retrieve x- and y-axis np.arrays from it.'''
        #t = time.time()
        self.log.append('Getting data blocks')
        yax = np.array(self.get_block(self.search_block(block)['offset'], self.search_block(block)['length']))
        #print(block)
        if block == 'Data Block IgSm' or block == 'Data Block':
            self.log.append('Getting ifg data block')
            # crude estimate of opd axis, only for illustratiion purposes, zpd's not included in calculation, and triangular apod. assumption -> 0.9
            xax = np.linspace(0,2*0.9/float(self.header['Acquisition Parameters']['RES']), len(yax))
        if block == 'Data Block SpSm':
            self.log.append('Getting spc data block')
            # calculate wavenumber axis for spectrum from frequencies of first and last point stored in header
            xax = np.linspace(self.header['Data Parameters SpSm']['FXV'], self.header['Data Parameters SpSm']['LXV'], len(yax))
        if block == 'Data Block ScSm':
            self.log.append('Getting spc data block')
            xax = np.linspace(self.header['Data Parameters ScSm']['FXV'], self.header['Data Parameters ScSm']['LXV'], len(yax))
        if block == 'Data Block TrSm':
            self.log.append('Getting trm data block')
            xax = np.linspace(self.header['Data Parameters TrSm']['FXV'], self.header['Data Parameters TrSm']['LXV'], len(yax))
        if block == 'Data Block PhSm':
            self.log.append('Getting pha data block')
            xax = np.linspace(self.header['Data Parameters PhSm']['FXV'], self.header['Data Parameters PhSm']['LXV'], len(yax))
        #print('get_datablocks\t%1.5f'%(time.time()-t))
        return xax, yax

    def get_slices(self, path):
        '''First attempt to implement concatinated slices from automated measurement routines. Probably only works for Uni Bremen setup currently.'''
        self.slices = {}
        self.slices_headers = {}
        slice_list = os.listdir(os.path.join(self.path, 'scan'))
        slice_list.sort()
        good_slice_list = []
        for i in slice_list:
            if i[-5:]!='.info':
                try:
                    self.filename = i
                    self.folder = os.path.join(path, 'scan')
                    self.path = os.path.join(path, 'scan', i)
                    #print('testing file', i)
                    self.test_if_ftsfile()
                    if self.status:
                        #print('read header', self.path)
                        self.read_header()
                        if self.has_block('Data Block IgSm'):
                            opd, ifg = self.get_datablocks('Data Block IgSm')
                            self.read_header()
                            self.slices_headers[i[1:9]+'_header'] = self.header
                            self.slices[i[1:9]] = ifg
                            good_slice_list.append(i)
                        else: pass
                    else: pass
                except: pass
            else: pass
        if len(good_slice_list)>0:
            #print(self.slices.keys())
            self.filename = good_slice_list[0]
            self.folder = os.path.join(self.path, 'scan')
            self.path = os.path.join(path, 'scan', good_slice_list[0])
            self.read_header()
            ifg = np.array([])
            for i in good_slice_list:
                if i[-5:]!='.info' and i[1:9] in self.slices.keys():
                    ifg = np.concatenate([ifg, self.slices[i[1:9]]])
                else: pass
            self.ifg = ifg
            self.opd = np.linspace(0,2*0.9/float(self.header['Acquisition Parameters']['RES']), len(self.ifg))
        else:
            print('Error loading slices from ', path)
            self.status = False
        return 0

    def test_if_ftsfile(self):
        '''Check the initialized filename for FTS magic number.'''
        #t = time.time()
        self.log.append('testing if FTS file')
        # same 4-byte binary representation found on all valid FTS files ... must be magic
        ftsmagicval = b'\n\n\xfe\xfe'
        try:
            with open(self.path, 'rb') as f:
                f.seek(0)
                magic = f.read(4)
            if magic==ftsmagicval:
                if self.verbose:
                    self.log.append('Identified '+self.path+' as FTS file ...')
                self.status=True
                self.isftsfile = True
            else:
                self.log.append('Bad Magic found in '+self.path)
                print('Bad Magic in ', self.path)
                self.status=False
                self.isftsfile = False
        except Exception as e:
            self.log.append(e)
            self.status=False
            self.isftsfile = False
        #print('test_if_ftsfile\t%1.5f'%(time.time()-t))

    def search_block(self, blockname):
        '''Searches a <blockname> within the identifies FTS file structure. Returns dictionary entry of the block <blockname>.'''
        #ipdb.set_trace()
        #t = time.time()
        if blockname in list(self.fs.keys()):
            #print(blockname)
            #print('search_block\t%1.5f'%(time.time()-t))
            return self.fs[blockname]
        else:
            self.log.append('Could not find '+str(blockname)+' in self.fs.keys()')

    def print_fs(self):
        '''Printing the structure of the FTS file. This includes found data blocks, their binary lengths and offsets.'''
        for i in self.fs.keys():
            print(i, '\n\toffset =', self.fs[i]['offset'], '\n\tlength =', self.fs[i]['length'])

    def print_log(self):
        '''Printing the log of everything that has happened to the class object to std out'''
        for i in self.log:
            print(i)

    def compare_fts_header(self, header2, verbose=True):
        '''Compare this instances header with another <header2>. If <verbose=False> only differences are shown.'''
        S = ' this header           the other header \n'
        for i in self.header.keys():
            if i in header2.keys():
                if verbose:
                    S += '\n'+str(i)+'\n'
                else: pass
                for j in self.header[i].keys():
                    try:
                        a, b = self.header[i][j], header2[i][j]
                        if a==b and verbose:
                            s = j+' '*67+'\n'
                            s = s[:21]+'identical'+s[30:]
                        elif a!=b:
                            s = j+' '*67+'\n'
                            s = s[:8]+str(a)+s[8+len(str(a)):]
                            s = s[:32]+str(b)+s[32+len(str(b)):]
                        else:
                            s = ''
                    except:
                        s = j+' '*67+'\n'
                        s = s[:18]+'problem with key'+s[34:]
                    S += s
            else:
                S += '\n'+str(i)+' missing in other header \n'
        return S

    def has_block(self, blockname):
        '''Check if <blockname> is present in ftsreader.fs'''
        if blockname in self.fs.keys():
            return True
        else:
            return False

    def __init__(self, path, verbose=False, getspc=False, getifg=False, getdoubleifg=False, gettrm=False, getpha=False, getslices=False, filemode='hdd', streamdata=None):
        t1 = time.time()
        self.log = []
        self.status = True
        self.verbose = verbose
        self.path = path
        self.filemode = filemode
        self.streamdata = streamdata
        if self.verbose:
            print('Initializing ...')
        self.log.append('Initializing')
        try:
            if path.rfind('/')>0:
                self.folder = path[:path.rfind('/')]
                self.filename = path[path.rfind('/')+1:]
            else:
                self.folder = './'
                self.filename = path
            if not getslices:
                self.test_if_ftsfile()
            if self.status:
                if not getslices:
                    self.read_header()
                else: pass
                # get spc if requested
                if getspc and self.has_block('Data Block SpSm'):
                    self.spcwvn, self.spc = self.get_datablocks('Data Block SpSm')
                elif getspc and self.has_block('Data Block ScSm'):
                    self.log.append('Setting self.spc tp ScSm instead of SpSm')
                    self.spcwvn, self.spc = self.get_datablocks('Data Block ScSm')
                else:
                    self.log.append('No Spectrum requested or not found ... skipping.')
                # get transmission spc if requested
                if gettrm and self.has_block('Data Block TrSm'):
                    self.trmwvn, self.trm = self.get_datablocks('Data Block TrSm')
                else:
                    self.log.append('No Transmissionspectrum requested or not found ... skipping.')
                # get ifg if requested
                if getpha and self.has_block('Data Block PhSm'):
                    self.phawvn, self.pha = self.get_datablocks('Data Block PhSm')
                else:
                    self.log.append('No Phasespectrum requested or not found ... skipping.')
                # get ifg if requested
                if getifg and self.has_block('Data Block IgSm'):
                    self.ifgopd, self.ifg = self.get_datablocks('Data Block IgSm')
                else:
                    self.log.append('No Interferogram requested or not found ... skipping.')
                # get two ifgs if requested
                if getdoubleifg and (self.has_block('Data Block IgSm') and self.has_block('Data Block')):
                    self.ifgopd, self.ifg = self.get_datablocks('Data Block IgSm')
                    self.ifgopd2, self.ifg2 = self.get_datablocks('Data Block')
                else:
                    self.log.append('No double interferogram requested or not found ... skipping.')
                # try getting slices if requested
                if getslices:
                    self.get_slices(path)
                else: self.log.append('No slices requested or not found ... skipping.')
                if self.verbose and self.status:
                    self.log.append('Finished initializing FTS object.\n\n')
                    print('\n\tFinished initializing ftsreader object.')
            else: raise(ValueError('Does not seem to be an FTS file ... skipping'))
            if self.verbose and not self.status:
                self.log.append('An error occured.')
                print('An error occured.')
        except Exception as e:
            self.log.append('Problem with '+str(e))
            print('Error while processing '+path+' ... check self.log or do self.print_log()')
        #print('init\t%1.5f'%(time.time()-t1))




if __name__ == '__main__':
    import matplotlib.pyplot as plt
    import sys
    #ttt = time.time()
    s = ftsreader(sys.argv[1], verbose=True, getspc=True, getifg=True)
    #s = ftsreader(sys.argv[1], verbose=True)#, getslices=True)
    #print(len(s.spc), len(s.ifg))
    #print('total\t%1.5f'%(time.time()-ttt))
    s.print_log()
    s.print_header()
    #print(s.get_header_par('RES'))
    #print(s.fs)
    #fig, (ax1, ax2) = plt.subplots(2)
    fig, ax1 = plt.subplots(1)
    #try:
    #    ax1.plot(s.ifg)
    #except: pass
    try:
        ax1.plot(s.spcwvn, s.spc)
    except: pass
    #try:
    #    ax2.plot(s.ifg)
    #except: pass
    plt.show()
