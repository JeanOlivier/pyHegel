#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Programme principale pour remplacer Hegel
#

import numpy as np
import instrument
from time import sleep
import string

class _sweep(instrument.BaseInstrument):
    before = instrument.MemoryDevice()
    after = instrument.MemoryDevice()
    out = instrument.MemoryDevice()
    def execbefore(self):
        b = self.before.get()
        if b:
            exec(b)
    def execafter(self):
        b = self.after.get()
        if b:
            exec(b)
    def readall(self):
        l = self.out.get()
        if l == None or l==[]:
            return []
        elif isinstance(l,instrument.BaseDevice):
            l = [l]
        ret = []
        for dev in l:
            ret.append(dev.get())
        return ret
    def __call__(self, dev, start, stop, npts, rate, filename):
        """
            routine pour faire un sweep
             dev est l'objet a varier
            ....
        """
        try:
           dev.check(start)
           dev.check(stop)
        except ValueError:
           print 'Wrong start or stop values. Aborting!'
           return
        span = np.linspace(start, stop, npts)
        f = open(filename, 'w')
        #TODO get CTRL-C to work properly
        try:
            for i in span:
                self.execbefore()
                dev.set(i)
                self.execafter()
                vals=self.readall()
                vals = [i]+vals
                strs = map(repr,vals)
                f.write(string.join(strs,'\t')+'\n')
        except KeyboardInterrupt:
            print 'in here'
            pass
        f.close()

sweep = _sweep()
# sleep seems to have 0.001 s resolution on windows at least
wait = sleep

###  set overides set builtin function
def set(dev, value):
    """
       Change la valeur de dev
    """
    dev.set(value)

### get overides get the mathplotlib
def get(dev):
    """
       Obtien la valeur de get
    """
    try:
       return dev.get()
    except KeyboardInterrupt:
       print 'CTRL-C pressed!!!!!!' 

