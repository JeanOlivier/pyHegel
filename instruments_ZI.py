# -*- coding: utf-8 -*-
# vim: set autoindent shiftwidth=4 softtabstop=4 expandtab:

import numpy as np
import zhinst.ziPython as zi
import zhinst.utils as ziu

from instruments_base import BaseInstrument,\
                            BaseDevice, scpiDevice, InvalidAutoArgument,\
                            MemoryDevice, ReadvalDev,\
                            ChoiceBase, _general_check, _fromstr_helper, _tostr_helper,\
                            ChoiceStrings, ChoiceMultiple, ChoiceMultipleDep, Dict_SubDevice,\
                            _decode_block_base, make_choice_list,\
                            sleep, locked_calling

def _tostr_helper(val, t):
    # This function converts from pyHegel val to ZI val (on set/write)
    if t == None:
        return val
    if t == bool:
        return int(val)
    if t == float:
        return float(val)
    if t == int:
        return int(val)
    if type(t) == type and issubclass(t, basestring):
        return t(val)
    return t.tostr(val)

def _fromstr_helper(valstr, t):
    # This function converts from ZI val to pyHegel (on get/ask)
    if t == None:
        return valstr
    if t == bool:
        return bool(valstr)
    if t == float:
        return float(valstr)
    if t == int:
        return int(valstr)
    if type(t) == type and issubclass(t, basestring):
        return t(valstr)
    return t(valstr)


class ziDev(scpiDevice):
    _autoset_val_str = ''
    def __init__(self, setstr=None, getstr=None, autoget=True, insert_dev=True, input_sel=0, input_repeat=None, **kwarg):
        """
        input_sel can be None: then it returns the whole thing
        input_repeat is an iterable that will be passed to set/getstr
                     as rpt_i
        The _tostr and _fromstr converter no longer need to convert to and from
        str, but to and from the device representation

        str_type available (pyHegel, zi):
                  None (no conversion)
                  bool (bool, 'int')
                  float(float, 'double')
                  int(int, 'int')
                  int(int, 'int')
                  str(str, 'byte')
                  unicode(unicode, 'byte')
        """
        self._input_sel = input_sel
        self._input_repeat = input_repeat
        if autoget:
            getstr = setstr
        insert_dev_pre = '/{{dev}}/'
        if insert_dev:
            if getstr:
                getstr = insert_dev_pre+getstr
            if setstr:
                setstr = insert_dev_pre+setstr
        super(ziDev, self).__init__(setstr, getstr, **kwarg)
    def _tostr(self, val):
        # This function converts from val to a str for the command
        t = self.type
        return _tostr_helper(val, t)
    def _fromstr(self, valstr):
        # This function converts from the query result to a value
        t = self.type
        return _fromstr_helper(valstr, t)
    def _apply_sel(self, val):
        if self._input_sel != None:
            return val[self._input_sel]
        return val
    def _setdev(self, val, **kwarg):
        if self._setdev_p == None:
            raise NotImplementedError, self.perror('This device does not handle _setdev')
        options = self._combine_options(**kwarg)
        command = self._setdev_p
        repeat = self._input_repeat
        if repeat == None:
            repeat = [1]
            val = [val]
        for i, rpt_i in enumerate(repeat):
            options['rpt_i'] = rpt_i
            cmd = command.format(**options)
            v = self._tostr(val[i])
            self.instr.write(cmd, v, **self._ask_write_opt)
    def _getdev(self, **kwarg):
        if self._getdev_p == None:
            raise NotImplementedError, self.perror('This device does not handle _getdev')
        try:
            options = self._combine_options(**kwarg)
        except InvalidAutoArgument:
            self.setcache(None)
            raise
        command = self._getdev_p
        ret = []
        repeat = self._input_repeat
        if repeat == None:
            repeat = [1]
        for i in repeat:
            options['rpt_i'] = i
            cmd = command.format(**options)
            reti = self.instr.ask(cmd, **self._ask_write_opt)
            reti = self._fromstr(reti)
            ret.append(self._apply_sel(reti))
        if self._input_repeat == None:
            return ret[0]
        return ret



# data structure
#  dev2021
#    auxins
#      0
#    auxouts
#      0-3
#    clockbase
#    conn
#    demods
#      0-7
#    dios
#      0
#    extrefs
#      0-1
#    features
#    oscs
#      0-1
#    scopes
#      0
#    sigins
#      0-1
#    sigouts
#      0-1
#    stats
#    status
#    system
#    triggers
#  zi
#    about
#    clockbase
#    config

# sweeper structure
#  sweep/averaging/sample
#  sweep/averaging/tc
#  sweep/bandwidth
#  sweep/bandwidthcontrol
#  sweep/clearhistory
#  sweep/device
#  sweep/endless
#  sweep/fileformat
#  sweep/filename
#  sweep/gridnode
#  sweep/historylength
#  sweep/loopcount
#  sweep/phaseunwrap
#  sweep/samplecount
#  sweep/scan
#  sweep/settling/tc
#  sweep/settling/time
#  sweep/start
#  sweep/stop
#  sweep/xmapping

# record structure
#  trigger/0/bandwidth
#  trigger/0/bitmask
#  trigger/0/bits
#  trigger/0/count
#  trigger/0/delay
#  trigger/0/duration
#  trigger/0/edge
#  trigger/0/findlevel
#  trigger/0/highlevel
#  trigger/0/holdoff/count
#  trigger/0/holdoff/time
#  trigger/0/lowlevel
#  trigger/0/path
#  trigger/0/pulse/max
#  trigger/0/pulse/min
#  trigger/0/retrigger
#  trigger/0/source
#  trigger/0/type
#  trigger/buffersize
#  trigger/clearhistory
#  trigger/device
#  trigger/endless
#  trigger/filename
#  trigger/historylength
#  trigger/triggered

# zoomFFT structure
#  zoomFFT/absolute
#  zoomFFT/bit
#  zoomFFT/device
#  zoomFFT/endless
#  zoomFFT/loopcount
#  zoomFFT/mode
#  zoomFFT/overlap
#  zoomFFT/settling/tc
#  zoomFFT/settling/time

#######################################################
##    Zurich Instruments UHF (600 MHz, 1.8 GS/s lock-in amplifier)
#######################################################

class zurich_UHF(BaseInstrument):
    """
    This instrument controls a Zurich Instrument UHF lock-in amplifier
     To use this instrument, the most useful devices are probably:
       fetch
       readval
    """
    def __init__(self, zi_dev=None, host='localhost', port=8004):
        """
        By default will use the first zi device available.
        """
        # The SRQ for this intrument does not work
        # as of version 7.2.1.0
        self._zi_daq = zi.ziDAQServer(host, port)
        self._zi_record = None
        self._zi_sweep = None
        self._zi_zoomFFT = None
        self._zi_devs = ziu.devices(self._zi_daq)
        self._zi_sep = '/'
        if zi_dev == None:
            try:
                zi_dev = self._zi_devs[0]
                print 'Using zi device ', zi_dev
            except IndexError:
                raise ValueError, 'No devices are available'
        elif zi_dev not in self._zi_devs:
            raise ValueError, 'Device "%s" is not available'%zi_dev
        self._zi_dev = zi_dev
        super(zurich_UHF, self).__init__()
    def init(self, full=False):
        #self.write('Comm_HeaDeR OFF') #can be OFF, SHORT, LONG. OFF removes command echo and units
        super(zurich_UHF, self).init(full=full)
    def _current_config(self, dev_obj=None, options={}):
        return self._conf_helper('memory_size', 'trig_coupling', options)
    def _conv_command(self, comm):
        """
        comm can be a string or a list of strings
        and it replaces {dev} with the current device
        """
        sep = self._zi_sep
        if isinstance(comm, (list, tuple)):
            comm = sep+ sep.join(comm)
        comm = comm.format(dev=self._zi_dev)
        return comm
    def _select_src(self, src):
        """
        available sources are:
            'main', 'sweep', 'record' and 'zoomFFT'
        returns object and prepend string
        """
        if src == 'main':
            ret = self._zi_daq
            pre = ''
        elif src == 'sweep':
            ret = self._zi_sweep
            pre = 'sweep'
        elif src == 'record':
            ret = self._zi_record
            pre = 'trigger'
        elif src == 'zommFFT':
            ret = self._zi_zoomFFT
            pre = 'zoomFFT'
        else:
            raise ValueError, 'Invalid src'
        if ret == None:
            raise ValueError, 'Requested src is not available'
        return ret, pre
    def list_nodes(self, base='/', src='main', recursive=True, absolute=True, leafs_only=True, settings_only=False):
        """
        base = '/' unless src is not 'main' in which case
        it will be '/*'
        see _select_src for available src
        """
        flags = 0
        if base == '/' and src != 'main':
            base = '/*'
        if recursive:
            flags |= 1
        if absolute:
            flags |= (1<<1)
        if leafs_only:
            flags |= (1<<2)
        if settings_only:
            flags |= (1<<3)
        src, pre = self._select_src(src)
        return src.listNodes(pre+base, flags)
    def _flat_dict(self, in_dict):
        """
        this converts the get(str,False) or get for
        other than main object in a flat dict
        i.e.
          {'a':{'0':{'c':4, 'd':5}}}
            into
          {'a/0/c':4, 'a/0/d':5}
        """
        sep = self._zi_sep
        out_dict = {}
        for k,v in in_dict.iteritems():
            if isinstance(v, dict):
                v = self._flat_dict(v)
                for ks, vs in v:
                    out_dict[k+sep+ks] = vs
            out_dict[k] = v
        return out_dict
    @locked_calling
    def read(self, timeout_ms=0):
        """
        read currently available susbscribed data.
        """
        # timeout value of -1 disables it. poll becomes completely blocking
        # with a non negative timeout poll is blocking for the timeout duration
        # poll and pollevent use the timeout in the same way
        #  poll also has a duration.
        #   it seems to repeat pollEvent as long as duration is not finished
        #   so the duration can be rounded up by timeout if no data is available.
        return self._zi_daq.pollEvent(timeout_ms)
    @locked_calling
    def write(self, command, val, src='main', t=None):
        """
         use like:
             obj.write('/dev2021/sigins/0/on', 1, t='int')
                t can be 'byte', 'double', 'int'
             obj.write([('/dev2021/sigins/0/on', 1), ('/dev2021/sigins/1/on', 0)])
             obj.write('loopcount', 2, src='zoomFFT')
                the 'sweepFFT/' is automatically inserted
        see _select_src for available src
            it only affects t==None
            for src not 'main', the only choice is
            t==None, and to give a single val.
        """
        command = self._conv_command(command)
        if t=='byte':
            self._zi_daq.setByte(command, val)
        elif t=='double':
            self._zi_daq.setDouble(command, val)
        elif t=='int':
            self._zi_daq.setInt(command, val)
        else:
            src, pre = self._select_src(src)
            if pre == '':
                src.set(command)
            else:
                src.set(pre+'/'+command, val)
    @locked_calling
    def ask(self, question, src='main', t=None):
        """
        use like:
            obj.ask('/dev2021/sigins/0/on', t='int')
              t can be 'byte', 'double', 'int', 'sample' or 'dict'
                for demods sample data, only t='sample' works
              In which case only one value can be asked for (not * or partial tree)
              The default is to return the value of the only item
              of the dict, unless there is more than one item,
              then a dict is return
            obj.ask('/dev2021/sigins')
            obj.ask('/dev2021/sig*')
            obj.ask('averaging/tc', src='sweep')
            obj.ask('*', src='sweep')
            obj.ask('/dev2021/demods/0/sample', t='sample')
            obj.ask('/dev2021/dios/0/input', t='dio')
        """
        question = self._conv_command(question)
        if t=='byte':
            return self._zi_daq.getByte(question)
        elif t=='double':
            return self._zi_daq.getDouble(question)
        elif t=='int':
            return self._zi_daq.getInt(question)
        elif t=='sample':
            return self._zi_daq.getSample(question)
        elif t=='dio':
            return self._zi_daq.getDIO(question)
        else:
            src, pre = self._select_src(src)
            if pre == '':
                ret = src.get(question, True) # True makes it flat
            else:
                ret = self._flat_dict(src.get(pre+'/'+question))
            if t == 'dict' or len(ret) != 1:
                return ret
            return ret.values()[0]
    def timestamp_to_s(self, timestamp):
        """
        Using a timestamp from the instrument, returns
        the number of seconds since the instrument turn on.
        """
        # The timestamp just seems to be the counter of the 1.8 GHz clock
        return timestamp/1.8e9
    def idn(self):
        name = 'Zurich Instrument'
        python_ver = self._zi_daq.version()
        python_rev = str(self._zi_daq.revision())
        server_ver = self.ask('/zi/about/version')[0]
        server_rev = self.ask('/zi/about/revision')[0]
        server_fw_rev = str(self.ask('/zi/about/fwrevision')[0])
        system_devtype = self.ask('/{dev}/features/devtype')[0]
        system_serial = self.ask('/{dev}/features/serial')[0]
        system_code = self.ask('/{dev}/features/code')[0]
        system_options = self.ask('/{dev}/features/options')[0]
        system_analog_board_rev = self.ask('/{dev}/system/analogboardrevision')[0]
        system_digital_board_rev = self.ask('/{dev}/system/digitalboardrevision')[0]
        system_fpga_rev = str(self.ask('/{dev}/system/fpgarevision')[0])
        system_fw_rev = str(self.ask('/{dev}/system/fwrevision')[0])
        return '{name} {system_devtype} #{system_serial} (analog/digital/fpga/fw_rev:{system_analog_board_rev}/{system_digital_board_rev}/{system_fpga_rev}/{system_fw_rev}, code:{system_code}, opt:{system_options}  [server {server_ver}-{server_rev} fw:{server_fw_rev}] [python {python_ver}-{python_rev}])'.format(
             name=name, python_ver=python_ver, python_rev=python_rev,
             server_ver=server_ver, server_rev=server_rev, server_fw_rev=server_fw_rev,
             system_devtype=system_devtype, system_serial=system_serial,
             system_code=system_code, system_options=system_options,
             system_analog_board_rev=system_analog_board_rev, system_digital_board_rev=system_digital_board_rev,
             system_fpga_rev=system_fpga_rev, system_fw_rev=system_fw_rev)

    def _fetch_ch_helper(self, ch):
        if ch==None:
            ch = self.find_all_active_channels()
        if not isinstance(ch, (list)):
            ch = [ch]
        return ch
    def _fetch_getformat(self, **kwarg):
        xaxis = kwarg.get('xaxis', True)
        ch = kwarg.get('ch', None)
        ch = self._fetch_ch_helper(ch)
        if xaxis:
            multi = ['time(s)']
        else:
            multi = []
        for c in ch:
            multi.append('ch_%s'%c)
        fmt = self.fetch._format
        multi = tuple(multi)
        fmt.update(multi=multi, graph=[], xaxis=xaxis)
        return BaseDevice.getformat(self.fetch, **kwarg)
    def _fetch_getdev(self, ch=None, xaxis=True, raw=False):
        """
           Options available: ch, xaxis
            -ch:    a single value or a list of values for the channels to capture
                    a value of None selects all the active ones from C1 to C4.
                    If obtaining more than one channels, they should have the same xaxis
            -xaxis: Set to True (default) to return the timebase as the first colum
            -raw: Set to true to return the vertical values as raw integers, otherwise
                  they are converted floats
        """
        # TODO handle complex ffts...
        ch = self._fetch_ch_helper(ch)
        ret = []
        first = True
        for c in ch:
            data = self.data.get(ch=c)
            header = data.header
            if xaxis and first:
                first = False
                ret = [header.HORIZ_INTERVAL*np.arange(header.WAVE_ARRAY_COUNT) + header.HORIZ_OFFSET]
            if raw:
                y = data.data1
            else:
                y = data.data1*header.VERTICAL_GAIN - header.VERTICAL_OFFSET
            ret.append(y)
        ret = np.asarray(ret)
        if ret.shape[0]==1:
            ret=ret[0]
        return ret
    def _create_devs(self):
        self.mac_addr = ziDev('system/nics/mac/{rpt_i}', input_repeat=range(6))
        #self.current_channel = MemoryDevice('C1', choices=channelsF)
        #def devChannelOption(*arg, **kwarg):
        #    options = kwarg.pop('options', {}).copy()
        #    options.update(ch=self.current_channel)
        #    app = kwarg.pop('options_apply', ['ch'])
        #    kwarg.update(options=options, options_apply=app)
        #    return scpiDevice(*arg, **kwarg)
        #self.data = devChannelOption(getstr='{ch}:WaveForm? ALL', str_type=waveformdata(), autoinit=False, trig=True, raw=True)
        #self.data_header = devChannelOption(getstr='{ch}:WaveForm? DESC', str_type=waveformdata(return_only_header=True), autoinit=False, trig=True, raw=True)
        #self.trig_mode = scpiDevice('TRig_MoDe', choices=ChoiceStrings('AUTO', 'NORM', 'SINGLE', 'STOP'))
        #self._devwrap('fetch', autoinit=False, trig=True)
        #self.readval = ReadvalDev(self.fetch)
        # This needs to be last to complete creation
        super(zurich_UHF, self)._create_devs()

# Problems discovered:
#  get('*') is slow and does not return sample data (because it is slow?)
#  get of subdevices does not work like get of main device (not option to flatten)
# documentation errors: pollEvent arg2 and 3, should only have 2 arg and
#                       description of arg3 is for arg2
#  get is slow
# errors in documentation ziAPI.h
#    example description of ziAPIGetValueB talks about DIO samples...
# timeit zi.ask('/{dev}/stats/physical/digitalboard/temps/0', t='int')
#  100 loops, best of 3: 2.55 ms per loop
# timeit zi.ask('/{dev}/stats/physical/digitalboard/temps/0')
#  10 loops, best of 3: 250 ms per loop
# I don't see /dev2021/system/calib/required
# in listnodes

##################################################################
#   Direct Access to ZI C API
#    use ziAPI class
##################################################################

import ctypes
from ctypes import Structure, Union, pointer, POINTER, byref,\
                   c_int, c_longlong, c_ulonglong, c_short, c_ushort, c_uint,\
                   c_double,\
                   c_void_p, c_char_p, c_char, create_string_buffer

from instruments_lecroy import StructureImproved

ziDoubleType = c_double
ziIntegerType = c_longlong
ziTimeStampType = c_ulonglong
ziAPIDataType = c_int
ziConnection = c_void_p

MAX_PATH_LEN = 256
MAX_EVENT_SIZE = 0x400000
MAX_BINDATA_SIZE = 0x10000

class DemodSample(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('X', c_double),
                ('Y', c_double),
                ('Frequency', c_double),
                ('Phase', c_double),
                ('DIOBits', c_uint),
                ('Reserved', c_uint),
                ('AuxIn0', c_double),
                ('AuxIn1', c_double) ]

class AuxInSample(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('Ch0', c_double),
                ('Ch1', c_double) ]

class DIOSample(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('Bits', c_uint),
                ('Reserved', c_uint) ]

TREE_ACTION = {0:'removed', 1:'add', 2:'change'}
class TreeChange(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('Action', c_uint),
                ('Name', c_char*32) ]

class ByteArrayData(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('Len', c_uint),
                ('Bytes', c_char*0) ]

class ScopeWave(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('dt', c_double),
                ('ScopeChannel', c_uint),
                ('TriggerChannel', c_uint),
                ('BWLimit', c_uint),
                ('Count', c_uint),
                ('Data', c_short*0) ]

class ziDoubleTypeTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('Value', c_double) ]

class ziIntegerTypeTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('Value', c_longlong) ]

class ByteArrayDataTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('Len', c_uint),
                ('Bytes', c_char*0) ]

class ScopeWaveTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('dt', c_double),
                ('ScopeChannel', c_uint),
                ('TriggerChannel', c_uint),
                ('BWLimit', c_uint),
                ('Count', c_uint),
                ('Data', c_short*0) ]

class TreeChangeTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('Action', c_uint),
                ('Name', c_char*32) ]

# These point to the first element of DATA with the correct type.
class ziEventUnion(Union):
    _fields_ = [('Void', c_void_p),
                ('SampleDemod', POINTER(DemodSample)),
                ('SampleAuxIn', POINTER(AuxInSample)),
                ('SampleDIO', POINTER(DIOSample)),
                ('Double', POINTER(ziDoubleType)),
                ('Integer', POINTER(ziIntegerType)),
                ('Tree', POINTER(TreeChange)),
                ('ByteArray', POINTER(ByteArrayData)),
                ('ScopeWave', POINTER(ScopeWave)),
                ('SampleDemod', POINTER(DemodSample)),
                ('DoubleTS', POINTER(ziDoubleTypeTS)),
                ('IntegerTS', POINTER(ziIntegerTypeTS)),
                ('ScopeWaveTS', POINTER(ScopeWaveTS)),
                ('ByteArrayTS', POINTER(ByteArrayDataTS)),
                ('TreeTS', POINTER(TreeChangeTS)) ]

ziAPIDataType_vals = {0:'None', 1:'Double', 2:'Integer', 3:'SampleDemod', 4:'ScopeWave',
                 5:'SampleAuxIn', 6:'SampleDIO', 7:'ByteArray', 16:'Tree',
                 32:'DoubleTS', 33:'IntegerTS', 35:'ScopeWaveTS', 38:'ByteArrayTS', 48:'TreeTS'}

class ziEvent(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('Type', ziAPIDataType),
                ('Count', c_uint),
                ('Path', c_char*MAX_PATH_LEN),
                ('Val', ziEventUnion),
                ('Data', c_char*MAX_EVENT_SIZE) ]
    def __repr__(self):
        if self.Count == 0:
            return 'ziEvent(None)'
        data = getattr(self.Val, ziAPIDataType_vals[self.Type])
        return "zevent('%s', count=%i, data0=%r)"%(self.Path, self.Count, data.contents)
    def show_all(self, multiline=True, show=True):
        if self.Count == 0:
            strs = ['None']
        else:
            strs = ['Path=%s'%self.Path,'Count=%i'%self.Count]
            data = getattr(self.Val, ziAPIDataType_vals[self.Type])
            for i in range(self.Count):
                strs.append('data_%i=%r'%(i, data[i]))
        if multiline:
            ret = '%s(\n  %s\n)'%(self.__class__.__name__, '\n  '.join(strs))
        else:
            ret = '%s(%s)'%(self.__class__.__name__, ', '.join(strs))
        if show:
            print ret
        else:
            return ret


ZI_STATUS = c_int
ZI_INFO_BASE =    0x0000
ZI_WARNING_BASE = 0x4000
ZI_ERROR_BASE =   0x8000

ZIAPIVersion = c_int
zi_api_version = {1:'ziAPIv1', 3:'ziAPIv3'}

zi_status_dic = {ZI_INFO_BASE:'Success (no error)',
                 ZI_INFO_BASE+1:'Max Info',
                 ZI_WARNING_BASE:'Warning (general)',
                 ZI_WARNING_BASE+1:'FIFO Underrun',
                 ZI_WARNING_BASE+2:'FIFO Overflow',
                 ZI_WARNING_BASE+3:'NotFound',
                 ZI_WARNING_BASE+4:'Max Warning',
                 ZI_ERROR_BASE:'Error (general)',
                 ZI_ERROR_BASE+1:'USB communication failed',
                 ZI_ERROR_BASE+2:'Malloc failed',
                 ZI_ERROR_BASE+3:'mutex unable to init',
                 ZI_ERROR_BASE+4:'mutex unable to destroy',
                 ZI_ERROR_BASE+5:'mutex unable to lock',
                 ZI_ERROR_BASE+6:'mutex unable to unlock',
                 ZI_ERROR_BASE+7:'thread unable to start',
                 ZI_ERROR_BASE+8:'thread unable tojoin',
                 ZI_ERROR_BASE+9:'socket cannot init',
                 ZI_ERROR_BASE+10:'socket unable to connect',
                 ZI_ERROR_BASE+11:'hostname not found',
                 ZI_ERROR_BASE+12:'Connection invalid',
                 ZI_ERROR_BASE+13:'timed out',
                 ZI_ERROR_BASE+14:'command failed internally',
                 ZI_ERROR_BASE+15:'command failed in server',
                 ZI_ERROR_BASE+16:'provided buffer length to short',
                 ZI_ERROR_BASE+17:'unable to open or read from file',
                 ZI_ERROR_BASE+18:'Duplicate entry',
                 ZI_ERROR_BASE+19:'Max Error' }

class ziAPI(object):
    _default_host = 'localhost'
    _default_port = 8004
    def __init__(self, hostname=_default_host, port=_default_port, autoconnect=True):
        self._last_status = 0
        self._ziDll = ctypes.CDLL('/Program Files/Zurich Instruments/LabOne/API/C/lib/ziAPI-win32.dll')
        self._conn = ziConnection()
        self._makefunc('ziAPIInit', [POINTER(ziConnection)],  prepend_con=False)
        self._makefunc('ziAPIDestroy', [] )
        self._makefunc('ziAPIGetRevision', [POINTER(c_uint)], prepend_con=False )
        self._makefunc('ziAPIConnect', [c_char_p, c_ushort] )
        self._makefunc('ziAPIDisconnect', [] )
        self._makefunc('ziAPIListNodes', [c_char_p, c_char_p, c_int, c_int] )
        self._makefunc('ziAPIUpdateDevices', [] )
        self._makegetfunc('D', ziDoubleType)
        self._makegetfunc('I', ziIntegerType)
        self._makegetfunc('S', DemodSample)
        self._makegetfunc('DIO', DIOSample)
        self._makegetfunc('AuxIn', AuxInSample)
        self._makegetfunc('B', c_char_p)
        self._makefunc('ziAPISetValueD', [c_char_p, ziDoubleType] )
        self._makefunc('ziAPISetValueI', [c_char_p, ziIntegerType] )
        self._makefunc('ziAPISetValueB', [c_char_p, c_char_p, c_int] )
        self._makefunc('ziAPISyncSetValueD', [c_char_p, POINTER(ziDoubleType)] )
        self._makefunc('ziAPISyncSetValueI', [c_char_p, POINTER(ziIntegerType)] )
        self._makefunc('ziAPISyncSetValueB', [c_char_p, c_char_p, POINTER(c_int), c_int] )
        # _SecondsTimeStamp is depracated
        self._SecondsTimeStamp = self._ziDll.ziAPISecondsTimeStamp
        self._SecondsTimeStamp.restype = c_double
        self._SecondsTimeStamp.argtypes = [ziTimeStampType]
        self._makefunc('ziAPISubscribe', [c_char_p] )
        self._makefunc('ziAPIUnSubscribe', [c_char_p] )
        self._makefunc('ziAPIPollData', [POINTER(ziEvent), c_int] )
        self._makefunc('ziAPIGetValueAsPollData', [c_char_p] )
        self._makefunc('ziAPIGetError', [ZI_STATUS, POINTER(c_char_p), POINTER(c_int)] )
        self._makefunc('ziAPIStartWebServer', [] )
        self._makefunc('ziAPIAsyncSetValueD', [c_char_p, ziDoubleType] )
        self._makefunc('ziAPIAsyncSetValueI', [c_char_p, ziIntegerType] )
        self._makefunc('ziAPIAsyncSetValueB', [c_char_p, c_char_p, c_int] )
        self._makefunc('ziAPIListImplementations', [c_char_p, c_int], prepend_con=False )
        self._makefunc('ziAPIConnectEx', [c_char_p, c_ushort, ZIAPIVersion, c_char_p] )
        self._makefunc('ziAPIGetConnectionVersion', [POINTER(ZIAPIVersion)] )
        self.init()
        if autoconnect:
            self.connect_ex(hostname, port)
    def _errcheck_func(self, result, func, arg):
        self._last_status = result
        if result<ZI_WARNING_BASE:
            return
        else:
            if result<ZI_ERROR_BASE:
                raise RuntimeWarning, 'Warning: %s'%zi_status_dic[result]
            else:
                raise RuntimeError, 'ERROR: %s'%zi_status_dic[result]
    def _makefunc(self, f, argtypes, prepend_con=True):
        rr = r = getattr(self._ziDll, f)
        r.restype = ZI_STATUS
        r.errcheck = self._errcheck_func
        if prepend_con:
            argtypes = [ziConnection]+argtypes
            rr = lambda *arg, **kwarg: r(self._conn, *arg, **kwarg)
            setattr(self, '_'+f[5:] , rr) # remove 'ziAPI'
        r.argtypes = argtypes
        setattr(self, '_'+f , r)
    def _makegetfunc(self, f, argtype):
        fullname = 'ziAPIGetValue'+f
        if argtype == c_char_p:
            self._makefunc(fullname, [c_char_p, argtype, POINTER(c_uint), c_uint])
        else:
            self._makefunc(fullname, [c_char_p, POINTER(argtype)])
        def newfunc(path):
            val = argtype()
            func = getattr(self, '_GetValue'+f)
            if argtype == c_char_p:
                val = create_string_buffer(1024)
                length = c_uint()
                func(path, val, byref(length), len(val))
                return val.raw[:length.value]
            func(path, byref(val))
            if isinstance(val, Structure):
                return val
            else:
                return val.value
        setattr(self, 'get'+f, newfunc)
    def __del__(self):
        # TODO make this work. probably need some weak ref somewhere
        self.disconnect()
        self.destroy()
        print 'Runnig del on ziAPI'
    def restart(self, hostname=_default_host, port=_default_port, autoconnect=True):
        self.disconnect()
        self.destroy()
        self.init()
        if autoconnect:
            self.connect_ex(hostname, port)
    def init(self):
        self._ziAPIInit(self._conn)
    def destroy(self):
        self._Destroy()
    def connect(self, hostname=_default_host, port=_default_port):
        """
        If you want to reconnect, you need to first disconnect, then destroy
        then init, before trying connect.
        """
        self._Connect(hostname, port)
        print 'Connected'
    def disconnect(self):
        self._Disconnect()
    def get_revision(self):
        rev = c_uint()
        self._ziAPIGetRevision(byref(rev))
        return rev.value
    def connect_ex(self, hostname=_default_host, port=_default_port, version=3, implementation=None):
        self._ConnectEx(hostname, port, version, implementation)
        print 'Connected ex'
    def list_implementation(self):
        buf = create_string_buffer(1000)
        self._ziAPIListImplementations(buf, len(buf))
        return buf.value.split('\n')
    def get_connection_ver(self):
        ver = ZIAPIVersion()
        self._GetConnectionVersion(byref(ver))
        return ver.value, zi_api_version[ver.value]
    def list_nodes(self, path='/', flags=3):
        buf = create_string_buffer(102400)
        self._ListNodes(path, buf, len(buf), flags)
        return buf.value.split('\n')
    def update_devices(self):
        """
        Rescans the devices available
        """
        self._UpdateDevices()
    def subscribe(self, path):
        self._Subscribe(path)
    def unsubscribe(self, path):
        self._UnSubscribe(path)
    def poll(self, timeout_ms=0):
        ev = ziEvent()
        self._PollData(byref(ev),timeout_ms)
        return ev
    def get_as_poll(self, path):
        self._GetValueAsPollData(path)
    def get_error(self, status=None):
        """
        if status==None, uses the last returned status
        """
        if status==None:
            status = self._last_status
        buf = c_char_p()
        base = c_int()
        self._GetError(status, byref(buf), byref(base))
        print 'Message:', buf.value, '\nBase:', base.value
    def start_web_server(self):
        self._StartWebServer()
    def set(self, path, val):
        if isinstance(val, int):
            self._SetValueI(path, val)
        elif isinstance(val, float):
            self._SetValueD(path, val)
        elif isinstance(val, basestring):
            self._SetValueB(path, val, len(val))
    def set_async(self, path, val):
        if isinstance(val, int):
            self._AsyncSetValueI(path, val)
        elif isinstance(val, float):
            self._AsyncSetValueD(path, val)
        elif isinstance(val, basestring):
            self._AsyncSetValueB(path, val, len(val))
    def set_sync(self, path, val):
        if isinstance(val, int):
            self._SyncSetValueI(path, byref(val))
        elif isinstance(val, float):
            self._SyncSetValueD(path, byref(val))
        elif isinstance(val, basestring):
            l = c_uint(len(val))
            self._SyncSetValueB(path, val, byref(l), l)

# asking for /dev2021/samples quits the session (disconnect)
# In Visual studio use, Tools/Visual studio command prompt, then:
#    dumpbin /EXPORTS "\Program Files\Zurich Instruments\LabOne\API\C\lib\ziAPI-win32.dll"
