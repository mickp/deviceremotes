#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2017 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## Microscope is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## Microscope is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Microscope.  If not, see <http://www.gnu.org/licenses/>.

"""Boston MicroMachines Corporation deformable mirrors.
"""

import ctypes
import os
import warnings

import microscope.devices
#import microscope._wrappers.BMC as BMC

class BMCDeformableMirror(microscope.devices.DeformableMirror):
  def __init__(self, serial_number, *args, **kwargs):
    super(BMCDeformableMirror, self).__init__()
    self._dm = BMC.DM()

    if __debug__:
      BMC.ConfigureLog(os.devnull, BMC.LOG_ALL)
    else:
      BMC.ConfigureLog(os.devnull, BMC.LOG_OFF)

    status = BMC.Open(self._dm, serial_number.encode("utf-8"))
    if status:
      raise Exception(BMC.ErrorString(status))

    self._n_actuators = self._dm.ActCount

  def apply_pattern(self, pattern):
    self._validate_patterns(pattern)
    data_pointer = values.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    status = BMC.SetArray(self._dm, data_pointer, None)
    if status:
      raise Exception(BMC.ErrorString(status))

  def zero(self):
    BMC.ClearArray(self._dm)

  def __del__(self):
    status = BMC.Close(self._dm)
    if status:
      warnings.warn(BMC.ErrorString(status), RuntimeWarning)
    super(BMCDeformableMirror, self).__del__()
