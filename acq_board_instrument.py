# -*- coding: utf-8 -*-
"""
Created on Fri Dec 09 13:39:09 2011

@author: blas2310
"""

# system import
import socket
import select
import threading
import math
import numpy as np

# user made import
import instrument

class acq_bool(object):
    def __call__(self, input_str):
        if input_str == 'False':
            return False
        elif input_str == 'True':
            return True
        else:
            return None
    def _tostr(self, val):
        if val == None:
            raise ValueError, 'acq_bool should not be None'
        return repr(val)

class acq_device(instrument.scpiDevice):
    def __init__(self, *arg, **kwarg):
        super(type(self), self).__init__(*arg, **kwarg)
        self._event_flag = threading.Event()
        self._event_flag.set()
        self._rcv_val = None
    def getdev(self):
        if self._getdev == None:
           raise NotImplementedError, self.perror('This device does not handle getdev')
        self._event_flag.clear()
        self.instr.write(self._getdev)
        instrument.wait_on_event(self._event_flag)
        return self._fromstr(self._rcv_val)

class Listen_thread(threading.Thread):
    def __init__(self, acq_instr):
        super(type(self), self).__init__()
        self.daemon = True
        self._stop = False
        self.acq_instr = acq_instr
    def run(self):
        select_list = [self.acq_instr.s]
        socket_timeout = 0.1
        old_stuff = ''
        bin_mode = False
        block_length = 0
        total_byte = 0
        acq = self.acq_instr
        while not self._stop:
            try:
                r, _, _ = select.select(select_list, [], [], socket_timeout)
                if not bool(r):
                    continue
            except socket.error:
                break
            if bin_mode:
                if len(old_stuff) != 0:
                    new_stuff = acq.s.recv(block_length-len(old_stuff))
                    new_stuff = old_stuff+new_stuff
                    old_stuff = ''
                else:
                    new_stuff = acq.s.recv(block_length)
                total_byte -= len(new_stuff)
                if total_byte < 0:
                    old_stuff = new_stuff[total_byte:]
                    new_stuff = new_stuff[:total_byte]
                if acq.fetch._dump_file != None:
                    acq.fetch._dump_file.write(new_stuff)
                    acq.fetch._rcv_val = None
                else:
                    acq.fetch._rcv_val += new_stuff
                if total_byte <= 0:
                    bin_mode = False
                    acq.fetch._event_flag.set()
                continue
            new_stuff = acq.s.recv(128)
            old_stuff += new_stuff
            trames = old_stuff.split('\n', 1)
            old_stuff = trames.pop()
            while trames != []:
                trame = trames[0]
                if trame[0] != '@' and trame[0] != '#':
                    continue
                if trame[0] == '@':
                    trame = trame[1:]
                    head, val = trame.split(' ', 1)
                    if head.startswith('ERROR:'):
                        if head == 'ERROR:STD':
                            acq._errors_list.append('STD: '+val)
                            print 'Error: ', val
                        elif head == 'ERROR:CRITICAL':
                            acq._errors_list.append('CRITICAL: '+val)
                            print '!!!!!!!!!!!\n!!!!!CRITICAL ERROR!!!!!: ', val,'\n!!!!!!!!!!!!!'
                        else:
                            acq._errors_list.append('Unknown: '+val)
                            print 'Unkown error', head, val
                    else:
                        obj = acq._objdict.get(head, None)
                        if obj == None:
                            acq._errors_list.append('Unknown @'+head+' val:'+val)
                            print 'Listen Thread: unknown @header:',head, 'val=', val
                        else:
                            obj._rcv_val = val
                            obj._event_flag.set()
                else: # trame[0]=='#'
                    trame = trame[1:]
                    head, val = trame.split(' ', 1)
                    location, typ, val = val.split(' ', 2)
                    if location == 'Local':
                        filename = val
                        acq.fetch._rcv_val = None
                        acq.fetch._event_flag.set()
                        #TODO: handle
                    else: # location == 'Remote'
                        acq.fetch._rcv_val = ''
                        bin_mode = True
                        block_length, total_byte = val.split(' ')
                        block_length = int(block_length)
                        total_byte = int(total_byte)
                        break;
                trames = old_stuff.split('\n', 1)
                old_stuff = trames.pop()
    def cancel(self):
        self._stop = True
    def wait(self, timeout=None):
        self.join(timeout)
        return not self.is_alive()


class Acq_Board_Instrument(instrument.visaInstrument):
    
    def __init__(self, ip_adress, port_nb):
        self._listen_thread = None
        self._errors_list = []
        
        # init the server member
        self.host = ip_adress
        self.port = port_nb
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # maximum value
        self.max_sampling_adc8 = 3000
        self.min_sampling_adc8 = 1000
        self.max_sampling_adc14 = 400
        self.min_sampling_adc14 = 20
        self.min_usb_clock_freq = 200
        self.min_nb_Msample = 32
        self.max_nb_Msample = 4294967295
        
        
        # try connect to the server
        self.s.connect((self.host, self.port))

        # status and flag
        self.board_type = None
        self.Get_Board_Type()
        if not self.board_type in ['ADC8', 'ADC14']:
            raise ValueError, 'Invalid board_type'
        self.visa_addr = self.board_type

        self._listen_thread = Listen_thread(self)
        self._listen_thread.start()     
        
        # init the parent class
        instrument.BaseInstrument.__init__(self)

    def _idn(self):
        return 'Acq card,,SERIAL#'
    def _get_error(self):
        if self._errors_list == []:
            return 'No more errors'
        return self._errors_list.pop()
    def _set_timeout(self):
        pass
    def __del__(self):
        if self._listen_thread:
            self._listen_thread.cancel()
            self._listen_thread.wait()
        self.s.close()
    
    def init(self,full = False):
        if full == True:
            self._objdict = {}
            for devname, obj in self.devs_iter():
                if isinstance(obj, acq_device):
                    name = obj._getdev[:-1]
                    self._objdict[name] = obj
        # if full = true do one time
        # get the board type and porgram state
        self.board_serial.get()
        self.board_status.get()
        self.result_available.get()        

    def fetch_getformat(self, filename=None):
        self.fetch._format.update(file=True)
        return instrument.BaseDevice.getformat(self.fetch)
    def fetch_getdev(self, filename=None, ch=[1]):
        self.fetch._event_flag.clear()
        mode = self.op_mode.getcache()
        self.fetch._dump_file = None
        if mode == 'Hist':
            s = 'DATA:HIST:DATA?'
            if filename != None:
                s += ' '+filename
            self.write(s)
            instrument.wait_on_event(self.fetch._event_flag)
            if self.fetch._rcv_val == None:
                return None
            return np.fromstring(self.fetch._rcv_val, np.uint64)
        #device member
    def create_devs(self):

        # choices string and number
        op_mode_str = ['Acq', 'Corr', 'Cust', 'Hist', 'Net', 'Osc', 'Spec']
        clock_source_str = ['Internal', 'External', 'USB']
        chan_mode_str = ['Single','Dual']
        osc_slope_str = ['Rising','Falling']
        format_location_str = ['Local','Remote']
        format_type_str = ['Default','ASCII','NPZ']
        
        #device init
        # Configuration
        self.op_mode = acq_device('CONFIG:OP_MODE', str_type=str, choices=op_mode_str)
        
        if self.board_type == 'ADC8':
            self.sampling_rate = acq_device('CONFIG:SAMPLING_RATE', str_type=float,  min=self.min_sampling_adc8, max=self.max_sampling_adc8)
        elif self.board_type == 'ADC14':
            self.sampling_rate = acq_device('CONFIG:SAMPLING_RATE', str_type=float,  min=self.min_sampling_adc14, max=self.max_sampling_adc14)
        
        self.test_mode = acq_device('CONFIG:TEST_MODE', str_type=acq_bool())
        self.clock_source = acq_device('CONFIG:CLOCK_SOURCE', str_type=str, choices=clock_source_str)
        self.nb_Msample = acq_device('CONFIG:NB_MSAMPLE', str_type=int,  min=self.min_nb_Msample, max=self.max_nb_Msample)
        self.chan_mode = acq_device('CONFIG:CHAN_MODE', str_type=str, choices=chan_mode_str)
        self.chan_nb = acq_device('CONFIG:CHAN_NB', str_type=int,  min=1, max=2)
        self.trigger_invert = acq_device('CONFIG:TRIGGER_INVERT', str_type=acq_bool())
        self.trigger_edge_en = acq_device('CONFIG:TRIGGER_EDGE_EN', str_type=acq_bool())
        self.trigger_await = acq_device('CONFIG:TRIGGER_AWAIT', str_type=acq_bool())
        self.trigger_create = acq_device('CONFIG:TRIGGER_CREATE', str_type=acq_bool())
        
        if self.board_type == 'ADC8':
            self.osc_trigger_level = acq_device('CONFIG:OSC_TRIGGER_LEVEL', str_type=float,  min=-0.35, max=0.35)
        elif self.board_type == 'ADC14':
            self.osc_trigger_level = acq_device('CONFIG:OSC_TRIGGER_LEVEL', str_type=float,  min=-0.375, max=0.375)
        
        self.osc_slope = acq_device('CONFIG:OSC_SLOPE', str_type=str, choices=osc_slope_str) 
        self.osc_nb_sample = acq_device('CONFIG:OSC_NB_SAMPLE', str_type=int,  min=1, max= ((8192*1024*1024)-1)) # max 8Go
        self.osc_hori_offset = acq_device('CONFIG:OSC_HORI_OFFSET', str_type=int,  min=0, max= ((8192*1024*1024)-1)) # max 8Go
        self.osc_trig_source = acq_device('CONFIG:OSC_TRIG_SOURCE', str_type=int,  min=1, max=2)
        
        if self.board_type == 'ADC8':
            self.net_signal_freq = acq_device('CONFIG:NET_SIGNAL_FREQ', str_type=float,  min=0, max=375000000)
        elif self.board_type == 'ADC14':
            self.net_signal_freq = acq_device('CONFIG:NET_SIGNAL_FREQ', str_type=float,  min=0, max=50000000)
        
        self.lock_in_square = acq_device('CONFIG:LOCK_IN_SQUARE', str_type=acq_bool()) 
        self.nb_tau = acq_device('CONFIG:NB_TAU', str_type=int,  min=0, max=50)
        self.autocorr_mode = acq_device('CONFIG:AUTOCORR_MODE', str_type=acq_bool())
        self.corr_mode = acq_device('CONFIG:CORR_MODE', str_type=acq_bool())
        self.autocorr_single_chan = acq_device('CONFIG:AUTOCORR_SINGLE_CHAN', str_type=acq_bool())
        self.fft_length = acq_device('CONFIG:FFT_LENGTH', str_type=int)
        self.cust_param1 = acq_device('CONFIG:CUST_PARAM1', str_type=float)
        self.cust_param2 = acq_device('CONFIG:CUST_PARAM2', str_type=float)
        self.cust_param3 = acq_device('CONFIG:CUST_PARAM3', str_type=float)
        self.cust_param4 = acq_device('CONFIG:CUST_PARAM4', str_type=float)
        self.cust_user_lib = acq_device('CONFIG:CUST_USER_LIB', str_type=str)
        self.board_serial = acq_device(getstr='CONFIG:BOARD_SERIAL?',str_type=int)
        self.board_status = acq_device(getstr='STATUS:STATE?',str_type=str)
        self.result_available = acq_device(getstr='STATUS:RESULT_AVAILABLE?',str_type=acq_bool())
        
        self.format_location = acq_device('CONFIG:FORMAT:LOCATION', str_type=str, choices=format_location_str)
        self.format_type = acq_device('CONFIG:FORMAT:TYPE',str_type=str, choices=format_type_str)
        self.format_block_length = acq_device('CONFIG:FORMAT:BLOCK_LENGTH',str_type = int, min=1, max=4294967296)

        # Results
        self.hist_m1 = acq_device(getstr = 'DATA:HIST:M1?', str_type = float, autoinit=False)
        self.hist_m2 = acq_device(getstr = 'DATA:HIST:M2?', str_type = float, autoinit=False)
        self.hist_m3 = acq_device(getstr = 'DATA:HIST:M3?', str_type = float, autoinit=False)
        # TODO histogram raw data
        
        #TODO correlation result
        #TODO 
        
        self.custom_result1 = acq_device(getstr = 'DATA:CUST:RESULT1?',str_type = float, autoinit=False)
        self.custom_result2 = acq_device(getstr = 'DATA:CUST:RESULT2?',str_type = float, autoinit=False)
        self.custom_result3 = acq_device(getstr = 'DATA:CUST:RESULT3?',str_type = float, autoinit=False)
        self.custom_result4 = acq_device(getstr = 'DATA:CUST:RESULT4?',str_type = float, autoinit=False)

        self.devwrap('fetch', autoinit=False)
        self.fetch._event_flag = threading.Event()
        self.fetch._rcv_val = None
        
        # This needs to be last to complete creation
        super(type(self),self).create_devs()
        
    #class methode     
    def write(self, val):
        val = '@' + val + '\n'
        self.s.send(val)

    def read(self):
        return self.s.recv(128)

    def ask(self, quest):
        self.write(quest)
        return self.read()
        
    def Get_Board_Type(self):
       res = self.ask('CONFIG:BOARD_TYPE?')
       if res[0] != '@' or res[-1] != '\n':
           raise ValueError, 'Wrong format for Get Board_Type'
       res = res[1:-1]
       base, val = res.split(' ', 1)
       if base == 'CONFIG:BOARD_TYPE':
           self.board_type = val
       elif base == 'ERROR:CRITICAL':
           raise ValueError, 'Critical Error:'+val
       else:
           raise ValueError, 'Unknow problem:'+base+' :: '+val

           
    def set_histogram(self, nb_Msample, sampling_rate, chan_nb, clock_source):
        self.op_mode.set('Hist')
        self.sampling_rate.set(sampling_rate)
        self.test_mode.set(False)
        self.clock_source.set(clock_source)
        self.nb_Msample.set(nb_Msample)
        self.chan_mode.set('Single')
        self.chan_nb.set(chan_nb)
        self.trigger_invert.set(False)
        self.trigger_edge_en.set(False)
        self.trigger_await.set(False)
        self.trigger_create.set(False)
        
        
    def run(self):
        # check if the configuration are ok
        
        # check if nb_sample fit the op_mode
        """if self.op_mode.getcache() == 'Hist' or self.op_mode.getcache() == 'Corr':
            if self.board_type == 'ADC8':
                quotien = float(self.nb_Msample.getcache())/8192
                frac = math.modf(quotien)
            
                if frac != 0.0:
                    new_nb_Msample = int(math.ceil(quotien))*8192
                    if new_nb_Msample > (self.max_nb_Msample - 8192):
                        new_nb_Msample = self.max_nb_Msample - 8192
                        self.nb_Msample.set(new_nb_Msample)
                    raise ValueError, 'Warning nb_Msample not a multiple of 8192, value corrected to nearest possible value : ' + str(new_nb_Msample)
            
            #self.board_type == 'ADC14':
                
                    
                    
                
        
        #check if clock freq is a multiple of 5 Mhz when in USB clock mode
        if self.clock_source.getcache() == 'USB':
            if self.board_type == 'ADC8':
                clock_freq = self.sampling_rate.getcache()/2
            else:
                clock_freq = self.sampling_rate.getcache()
                
            quotien = clock_freq/5.0
            
            frac = math.modf(quotien)
            
            if frac != 0.0:
                if self.board_type == 'ADC8':
                    new_sampling_rate =  2* math.ceil(quotien) * 5
                    if new_sampling_rate > self.max_sampling_adc8:
                        new_sampling_rate = self.max_sampling_adc8
                    self.sampling_rate.set(new_sampling_rate)
                else:
                    new_sampling_rate = math.ceil(quotien) * 5
                    if new_sampling_rate > self.max_sampling_adc14:
                        new_sampling_rate = self.max_sampling_adc14
                    elif new_sampling_rate < self.min_usb_clock_freq:
                        new_sampling_rate = self.min_usb_clock_freq
                    self.sampling_rate.set(new_sampling_rate)
                raise ValueError, 'Warning sampling_rate not a multiple of 5, value corrected to nearest possible value : ' + str(new_sampling_rate)
                """
        self.write('STATUS:CONFIG_OK True')
        self.write('RUN')
        
        
            

           
           