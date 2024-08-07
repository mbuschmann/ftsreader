#!/usr/bin/python3
# coding: utf8

'''
A class providing an interface for accessing header, interferogram and spectrum data blocks from a Fourier-Transform Infrared Spectrometer (FTS).
'''

from __future__ import print_function, division
import os, sys, struct, io, time
import numpy as np
import matplotlib.pyplot as plt


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
            return pars[0]
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
                        '31': 'Data Parameters',
                        '32': 'Instrument Parameters',
                        '15': 'Data Block',
                        '7':  'Data Block',
                        '0':  'something'}
        self.__blocknames2 = {'132': ' ScSm', # another declaration to differentiate blocks between ifg, spc, etc.
                        '4': ' SpSm',
                        '8': ' IgSm',
                        '136': ' IgSm/2.Chn.',
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

    def get_single_param_from_block(self, par):
        '''Retrieve a single parameter from self.header, including binary length and offset. This is needed to repack and replace a header parameter later.'''
        block = self.search_block(self.search_header_par(par))
        ll = self.getparamsfromblock(block['offset'], block['length'], full=True)
        #print(ll)
        for l in ll:
            if l[0][:len(par)].decode('utf8')==par:
                return l
            else: pass

    def change_header_pars(self, pars, newvals):
        '''Change a list of header parameters with their associated values and write in a buffered copy of the raw data.'''
        # get content of original file
        if self.newfilebuffer == None:
            with open(self.path, 'rb') as f:
                self.newfilebuffer = f.read()
        else: 
            pass
        for i, par in enumerate(pars):
            try:
                parline = self.get_single_param_from_block(par)
                #print(par, parline)
                (pn, mtype, leng, offset, val) = parline
                if mtype == 0:
                    dat = struct.pack('i', newvals[i])
                elif mtype == 1:
                    dat = struct.pack('d', newvals[i])
                elif mtype >= 2 and mtype <=4:
                    dat = struct.pack('%1is'%(2*leng), newvals[i].encode())
                dat = struct.pack('4s2H', *(pn, mtype, leng))+dat
                self.newfilebuffer = self.newfilebuffer[:offset]+dat+self.newfilebuffer[offset+len(dat):]
                self.log.append('Replaced header parameter '+par+' in newfilebuffer.')
            except Exception as e:
                self.log.append('Error while replacing header parameter '+par+' in newfilebuffer: '+str(e))
        
    def replace_datablock(self, blockname, newdatablock):
        '''Replace the data block <blockname> with data in <newdatablock>.'''
        #locate spectrum data block
        self.log.append('Replacing datablock'+blockname+' in newfilebuffer')
        pointer = self.fs[blockname]['offset']
        olddatablocklen = self.fs[blockname]['length']
        newdatablocklen = len(newdatablock)
        if olddatablocklen!=newdatablocklen:
            self.log.append('Old and new datablocks have different size not doing anything ...')
            print('Old and new datablocks have different sizes:', olddatablocklen, newdatablocklen, '     not doing anything ...')
        else:
            # format new spectrum data
            newdatablock_packed = struct.pack(str(newdatablocklen)+'f', *newdatablock)
            # get content of original file
            if self.newfilebuffer == None:
                with open(self.path, 'rb') as f:
                    self.newfilebuffer = f.read()
            # write original file until spc-data-block, write new block, write rest of orig. file
            self.newfilebuffer = self.newfilebuffer[:pointer]+newdatablock_packed+self.newfilebuffer[pointer+4*newdatablocklen:]
            self.log.append('Replaced data block in newfilebuffer')

    def save_changed_file(self, outputfilename):
        self.log.append('Writing '+outputfilename)
        if os.path.exists(outputfilename):
            print('File already exists: ', outputfilename, ' not doing anything ...')
            self.log.append('File already exists: '+outputfilename+' not doing anything ...')
        else:
            with open(outputfilename, 'wb') as f:
                f.write(self.newfilebuffer)
            print('wrote', outputfilename)

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
        datablocktype = block.split(' ')[-1]
        self.log.append('Getting '+datablocktype+' data block')
        # sometimes the number of points defined by the block length is different from the NPT reported in header
        # looks like in this case the data block should be limited to NPT
        npt = self.header['Data Parameters '+datablocktype]['NPT']
        yax = self.get_block(self.search_block(block)['offset'], self.search_block(block)['length'])[:npt]
        if datablocktype == 'IgSm':
            xax = None
        else:
            xax = np.linspace(self.header['Data Parameters '+datablocktype]['FXV'], self.header['Data Parameters '+datablocktype]['LXV'], self.header['Data Parameters '+datablocktype]['NPT'])
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
    
    
    def set_FT_params(
            self,
            laser_wvn=None,
            zpd=(None, None), 
            zpd_search_mode='absolute maximum', 
            zero_filling=2, 
            phase_correction_mode='Mertz', 
            phase_ifg_length=None, 
            phase_threshold=(0.0, 0.0), 
            use_stored_phase=False,
            max_opd=None,
            lfq=None,
            hfq=None):
        
        self.FT_params = {}
        if laser_wvn==None:
            self.FT_params['laser_wvn'] = self.header['Instrument Parameters']['LWN']
        else:
            self.FT_params['laser_wvn'] = laser_wvn
        self.FT_params['zpd'] = zpd
        self.FT_params['zpd_search_mode'] = zpd_search_mode
        self.FT_params['zero_filling'] = zero_filling
        self.FT_params['phase_correction_mode'] = phase_correction_mode
        self.FT_params['phase_ifg_length'] = phase_ifg_length
        self.FT_params['phase_threshold'] = phase_threshold
        self.FT_params['use_stored_phase'] = use_stored_phase
        self.FT_params['max_opd'] = max_opd
        self.FT_params['lfq'] = lfq
        self.FT_params['hfq'] = hfq
    
    def init_FT(self, stored_phase=(None, None)):
        if self.header['Acquisition Parameters']['AQM']=='SD':
            self._ifg_fw = self._normalize_ifg(self.ifg[:int(len(self.ifg)/2)])
            self._ifg_bw = self._normalize_ifg(self.ifg[int(len(self.ifg)/2):][::-1])
        
        self._zpd_fw = self._get_zpd(self._ifg_fw, self.FT_params['zpd'][0], self.FT_params['zpd_search_mode'])
        self._zpd_bw = self._get_zpd(self._ifg_bw, self.FT_params['zpd'][1], self.FT_params['zpd_search_mode'])
        
        if self.FT_params['max_opd']:
            self._ifg_fw = self._ifg_fw[:int(np.ceil(self._zpd_fw) + 2*self.FT_params['laser_wvn']*self.FT_params['max_opd'])]
            self._ifg_bw = self._ifg_bw[:int(np.ceil(self._zpd_bw) + 2*self.FT_params['laser_wvn']*self.FT_params['max_opd'])]

        if self.FT_params['phase_ifg_length'] is None:
            self.FT_params['phase_ifg_length'] = int(np.min([self._zpd_fw, self._zpd_bw], axis=0) - 1)

        def next_higher_power_of_two(x):
            return int(2 ** np.ceil(np.log2(x)))

        self._ifg_array_length = next_higher_power_of_two(len(self._ifg_fw)) * self.FT_params['zero_filling']
        self.spcwvn2 = np.fft.fftfreq(self._ifg_array_length, 0.5/self.FT_params['laser_wvn'])[:int(self._ifg_array_length/2)]

        if self.FT_params['use_stored_phase']:
            self._phase_fw = stored_phase[0]
            self._phase_bw = stored_phase[1]
            self.phase = np.mean([self._phase_fw, self._phase_bw], axis=0)
            
    def _normalize_ifg(self, ifg):
        # watch out for odd NPT, there might be rounding issues here
        ifg -= np.mean(ifg[int(len(ifg)/2):])
        return ifg
    
    def _get_zpd(self, ifg, zpd, zpd_search_mode):
        if zpd_search_mode == 'use given zpd':
            return zpd  
        elif zpd_search_mode == 'absolute maximum':
            return np.argmax(np.abs(ifg)) 
        elif zpd_search_mode == 'parabola fit':
            zpd_absmax = np.argmax(np.abs(ifg))
            return self._calc_parabola(
                zpd_absmax - 1, ifg[zpd_absmax - 1],
                zpd_absmax, ifg[zpd_absmax],
                zpd_absmax + 1, ifg[zpd_absmax + 1],
            )
        elif zpd_search_mode == 'ifg symmetry':
            return self._calc_symmetry_zpd(ifg)
        else:
            print('No ZPD can be determined, please choose ZPD calculation method or give ZPD value directly!')

    def _calc_parabola(self, x1, y1, x2, y2, x3, y3):
        denom = (x1 - x2) * (x1 - x3) * (x2 - x3)
        A = (x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)) / denom
        B = (x3 * x3 * (y1 - y2) + x2 * x2 * (y3 - y1) + x1 * x1 * (y2 - y3)) / denom
        C = (
            x2 * x3 * (x2 - x3) * y1
            + x3 * x1 * (x3 - x1) * y2
            + x1 * x2 * (x1 - x2) * y3
        ) / denom
        parabola = -B / (2 * A)
        return parabola
    
    
    def _calc_symmetry_zpd(self, ifg):
        kmax, kmin, ybar, ymax, ymin = np.argmax(ifg), np.argmin(ifg), np.mean(ifg), np.max(ifg), np.min(ifg)
        if np.abs(ymax-ybar) > np.abs(ymin-ybar):
            pinl=kmax
        else:
            pinl=kmin
            
        def symmetry(ac_igram, lpco):
            sasumi=0.0
            sadeli=0.0
            sasump=0.0
            sadelp=0.0
            q = np.pi/float(lpco)
            for x in np.arange(int(lpco/2)):
                ww = (5.0*np.cos(q*x)+np.cos(3.0*q*x))/6.0
                sasumi = sasumi + ww*np.abs(ac_igram[-x]+ac_igram[x])
                sadeli = sadeli + ww*np.abs(ac_igram[-x]-ac_igram[x])
                sasump = sasump + ww*np.abs(ac_igram[-x+1]+ac_igram[x])
                sadelp = sadelp + ww*np.abs(ac_igram[-x+1]-ac_igram[x])
            symmi=(sasumi-sadeli)/(sasumi+sadeli)
            symmp=(sasump-sadelp)/(sasump+sadelp)
            return symmi, symmp
        
        def bestzpd(ac_igram, nburst, lpco):
            eps=1e-37
            smax=-999.0
            best=0.0
            symiw=0.0
            sympw=0.0
            for i in range(2*nburst):
                ac_igrami = ac_igram[i:-2*nburst+i]
                symmi, symmp = symmetry(ac_igrami, lpco)
                if sympw>smax:
                    smax=sympw
                    denom=eps+4.0*np.abs(2.0*sympw-symiw-symmi)
                    best=float(i)-0.5+(-symiw+symmi)/denom
                if symmi>smax:
                    smax=symmi
                    denom=eps+4.0*np.abs(2.0*symmi-sympw-symmp)
                    best=float(i)+(-sympw+symmp)/denom
                symiw=symmi
                sympw=symmp
            return best-nburst

        lpco = 1024
        nburst = 15
        ac_igram = ifg[int(pinl-nburst-lpco/2):int(pinl+nburst+lpco/2)] 
        best = bestzpd(ac_igram, nburst, lpco)
        zpdl = pinl+best
        izpd = int(np.round(zpdl,0))
        return zpdl

    def determine_phase(self):
        if self.FT_params['use_stored_phase']:
            print('Stored phase will be replaced!')
        phase_fw, self._phase_spc_fw = self._lowres_phase(self._ifg_fw, self.FT_params['phase_ifg_length'], self._zpd_fw)
        phase_bw, self._phase_spc_bw = self._lowres_phase(self._ifg_bw, self.FT_params['phase_ifg_length'], self._zpd_bw)
        self._phase_fw = self._interpolate_phase(self.FT_params['phase_threshold'][0], self._phase_spc_fw, phase_fw)
        self._phase_bw = self._interpolate_phase(self.FT_params['phase_threshold'][0], self._phase_spc_bw, phase_bw)
        self.phase = np.mean([self._phase_fw, self._phase_bw], axis=0)
        self.phase_spc = np.mean([self._phase_spc_fw, self._phase_spc_bw], axis=0)
    
    def _interpolate_phase(self, threshold, phase_spc, phase):
        def thresh_helpher(phase_spc):
            return np.abs(phase_spc) < threshold, lambda z: z.nonzero()[0]

        below_thresh, index_function = thresh_helpher(phase_spc)
        phase[below_thresh] = np.interp(index_function(below_thresh), index_function(~below_thresh), phase[~below_thresh])    
        return phase
    
    def _lowres_phase(self, ifg, phase_ifg_length, zpd):
        phase_ifg = self._create_phase_ifg(ifg, phase_ifg_length, zpd)
        phase_spc = self._ftir_fft(phase_ifg, zpd)
        phase = self._phase_of_spc(phase_spc)
        return phase, phase_spc
    
    def _create_phase_ifg(self, ifg, phase_ifg_length, zpd):
        phase_ifg_truncated = np.zeros_like(ifg)
        phase_ifg_truncated[
            int(np.ceil(zpd) - phase_ifg_length):int(np.ceil(zpd) + phase_ifg_length)
        ] = ifg[
            int(np.ceil(zpd) - phase_ifg_length):int(np.ceil(zpd) + phase_ifg_length)
        ]

        def generate_cosine_square_bell(ifg_length, zpd_apo, phase_ifg_length):
            array = np.zeros(ifg_length)
            for i in range(ifg_length):
                distance = abs(i - zpd_apo)
                if distance <= phase_ifg_length:
                    cosine_value = np.cos(0.5 * np.pi * distance / phase_ifg_length)
                    square_cosine_value = cosine_value ** 2
                    array[i] = square_cosine_value
            return array

        phase_ifg = phase_ifg_truncated * generate_cosine_square_bell(len(phase_ifg_truncated), zpd, phase_ifg_length)
        return phase_ifg

    def _ftir_fft(self, ifg, zpd):
        ifg_packed = self._pack_ifg(ifg, zpd)
        spc = np.fft.ifft(ifg_packed)[:int(len(ifg_packed)/2)]
        return spc

    def _pack_ifg(self, ifg, zpd):
        ifg_packed = np.zeros(self._ifg_array_length)
        ifg_packed[:int(len(ifg) - np.ceil(zpd))] = ifg[int(np.ceil(zpd)):]
        ifg_packed[-int(np.ceil(zpd)):] = ifg[:int(np.ceil(zpd))]
        return ifg_packed

    def _phase_of_spc(self, spc):
        return np.angle(spc) + np.pi   

    def ifg_to_spc(self):
        self._spc_uncorr_fw = self._ftir_fft(self._ramp_ifg(self._ifg_fw, self._zpd_fw), self._zpd_fw)
        self._spc_uncorr_bw = self._ftir_fft(self._ramp_ifg(self._ifg_bw, self._zpd_bw), self._zpd_bw)
        self._phase_highres_fw = self._phase_of_spc(self._spc_uncorr_fw)
        self._phase_highres_bw = self._phase_of_spc(self._spc_uncorr_bw)
        if self.FT_params['phase_correction_mode'] == 'Mertz':
            self._spc2_fw, self._spc2_imag_fw, self._spc2_complex_fw = self._mertz_correction(self._spc_uncorr_fw, self._phase_highres_fw, self._phase_fw)
            self._spc2_bw, self._spc2_imag_bw, self._spc2_complex_bw = self._mertz_correction(self._spc_uncorr_bw, self._phase_highres_bw, self._phase_bw)
            self.spc2 = np.mean([self._spc2_fw, self._spc2_bw], axis=0)
            self.spc2_complex = np.mean([self._spc2_complex_fw, self._spc2_complex_bw], axis=0)
            print('Created: self.spc2, self.spc2_complex, etc.')

    def _ramp_ifg(self, ifg, zpd):
        def generate_ramp(ifg_length, zpd_ramp):
            ramp_length = 2 * zpd_ramp
            ramp_array = np.zeros(ifg_length)
            slope = 1. / ramp_length
            for i in range(ifg_length):
                if i <= ramp_length:
                    ramp_array[i] = i * slope
                else:
                    ramp_array[i] = 1
            return ramp_array

        ifg_ramped = ifg * generate_ramp(len(ifg), zpd)
        return ifg_ramped        

    def _mertz_correction(self, spc_uncorr, phase_highres, phase):
        spc = np.abs(spc_uncorr) * np.cos(-phase + phase_highres)
        spc_imag = np.abs(spc_uncorr) * np.sin(-phase + phase_highres)
        spc_complex = spc_uncorr * np.exp(-1j * phase)
        return spc, spc_imag, spc_complex
    
    def apply_frequency_limits(self):
        if self.FT_params['lfq']==None or self.FT_params['hfq']==None:
            try:
                wvn_diff = self.spcwvn[1] - self.spcwvn[0]
                wvn_min = self.spcwvn[0] - wvn_diff/2
                wvn_max = self.spcwvn[-1] + wvn_diff/2
                #hfq = self.header['FT Parameters']['HFQ']
                #lfq = self.header['FT Parameters']['LFQ']
                #selection = (self.spcwvn2>lfq) & (self.spcwvn2<hfq)
                #selection = (self.spcwvn2>=np.min(self.spcwvn)) & (self.spcwvn2<=np.max(self.spcwvn))
                selection = (self.spcwvn2>wvn_min) & (self.spcwvn2<wvn_max)
                print('Frequency limits not found in FT_params. Using limits of original wavenumber axis.')
                self.spc2 = self.spc2[np.where(selection)]
                self.spcwvn2 = self.spcwvn2[np.where(selection)]
            except Exception:
                print('Tried to apply frequency limits, but not specified in FT_params and no original wvn axis present.')
        else:
            print('Using frequency limits from FT_params')
            selection = (self.spcwvn2>self.FT_params['lfq']) & (self.spcwvn2<self.FT_params['hfq'])
            self.spc2 = self.spc2[selection]
            self.spcwvn2 = self.spcwvn2[selection]
    
    def calculate_spectrum(self):
        ''' Wrapper function to calculate spectrum with Mertz phase correction and standard parameters.\n
        If more control is needed adjust parameters and follow these steps:
            fts_obj = ftsreader('path/to/ifg', getifg=True)
            fts_obj.set_FT_params(laser_wvn=None,
                                  zpd=(None, None),
                                  zpd_search_mode='absolute maximum',
                                  zero_filling=2,
                                  phase_correction_mode='Mertz',
                                  phase_ifg_length=None,
                                  phase_threshold=(0.0, 0.0),
                                  use_stored_phase=False,
                                  max_opd=None,
                                  lfq=None,
                                  hfq=None
                                  )
            fts_obj.init_FT(stored_phase=(None, None))
            fts_obj.determine_phase()
            fts_obj.ifg_to_spc()'''
        self.set_FT_params()
        self.init_FT()
        self.determine_phase()
        self.ifg_to_spc()
        self.apply_frequency_limits()
    
    def spc_figure(self, plot_calculated_spc=False):
        """Returning a figure with one panel: SPC
        if plot_calculated=True then self.spc2 will be plotted."""
        fig, ax1 = plt.subplots(1)
        ax1.set_xlabel('Wavenumber [cm$^{-1}$]')
        ax1.set_title('Spectrum: '+self.filename)
        if plot_calculated_spc:
            ax1.plot(self.spcwvn2, self.spc2, 'k-')
        else:
            ax1.plot(self.spcwvn, self.spc, 'k-')
        return fig

    def ifg_figure(self):
        """Returning a figure with one panel: IFG"""
        fig, ax1 = plt.subplots(1)
        ax1.set_title('Interferogram: '+self.filename)
        ax1.set_xlabel('Interferogram points')
        ax1.plot(self.ifg, 'k-')
        return fig

    def ifg_spc_figure(self):
        """Returning a figure with two panels: IFG and SPC"""
        fig, (ax1, ax2) = plt.subplots(2)
        ax1.set_title(self.filename)
        ax1.set_xlabel('Interferogram points')
        ax2.set_xlabel('Wavenumber [cm$^{-1}$]')
        ax1.set_ylabel('Interferogram')
        ax2.set_ylabel('Spectrum')
        ax1.plot(self.ifg, 'k-')
        ax2.plot(self.spcwvn, self.spc, 'k-')
        return fig
    
    def __init__(self, path, verbose=False, getspc=False, getifg=False, getdoubleifg=False, gettrm=False, getpha=False, getslices=False, filemode='hdd', streamdata=None):
        t1 = time.time()
        self.log = []
        self.status = True
        self.verbose = verbose
        self.path = path
        self.filemode = filemode
        self.streamdata = streamdata
        self.newfilebuffer = None
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
                    self.has_spc = True
                elif getspc and self.has_block('Data Block ScSm'):
                    self.log.append('Setting self.spc tp ScSm instead of SpSm')
                    self.spcwvn, self.spc = self.get_datablocks('Data Block ScSm')
                    self.has_spc = True
                else:
                    self.log.append('No Spectrum requested or not found ... skipping.')
                    self.has_spc = False
                # get transmission spc if requested
                if gettrm and self.has_block('Data Block TrSm'):
                    self.trmwvn, self.trm = self.get_datablocks('Data Block TrSm')
                    self.has_trm = True
                else:
                    self.log.append('No Transmissionspectrum requested or not found ... skipping.')
                    self.has_trm = False
                # get ifg if requested
                if getpha and self.has_block('Data Block PhSm'):
                    self.phawvn, self.pha = self.get_datablocks('Data Block PhSm')
                else:
                    self.log.append('No Phasespectrum requested or not found ... skipping.')
                # get ifg if requested
                if getifg and self.has_block('Data Block IgSm'):
                    self.ifgopd, self.ifg = self.get_datablocks('Data Block IgSm')
                    self.has_ifg = True
                else:
                    self.log.append('No Interferogram requested or not found ... skipping.')
                    self.has_ifg = False
                # get two ifgs if requested
                if getdoubleifg and (self.has_block('Data Block IgSm/2.Chn.') and self.has_block('Data Block IgSm/2.Chn.')):
                    self.ifgopd, self.ifg = self.get_datablocks('Data Block IgSm')
                    self.ifgopd2, self.ifg2 = self.get_datablocks('Data Block IgSm/2.Chn.')
                    self.has_difg = True
                else:
                    self.log.append('No double interferogram requested or not found ... skipping.')
                    self.has_difg = False
                # try getting slices if requested
                if getslices:
                    self.get_slices(path)
                    self.has_slices = True
                else: 
                    self.log.append('No slices requested or not found ... skipping.')
                    self.has_slices = False
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
    try:
        s = ftsreader(sys.argv[1], verbose=True, getspc=True, getifg=True)
        s.print_log()
        s.print_header()
        if s.has_ifg and s.has_spc:
            fig = s.ifg_spc_figure()
            plt.show()
        elif s.has_ifg:
            fig = s.ifg_figure()
            plt.show()
        elif s.has_spc:
            fig = s.spc_figure()
            plt.show()
        else:
            pass
    except Exception as e:
        print(e)
