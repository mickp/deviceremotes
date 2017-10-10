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

"""Class for Alpao deformable mirror.

Exceptions:
  May throw an OSError during import if the alpao SDK is not available.
"""

import ctypes

import numpy

from microscope.devices import TriggerType
from microscope.devices import DeformableMirror
from microscope.devices import TriggerTargetMixIn

import microscope._wrappers.asdk as asdk

def _normalize_patterns(self, patterns):
  ## Alpao SDK expects values in the [-1 1] range, so we normalize
  ## them from the [0 1] range we expect in our interface.
  patterns = (patterns * 2) -1
  return patterns


class AlpaoDeformableMirror(TriggerTargetMixIn, DeformableMirror):
  ## The length of the buffer given to Alpao SDK to write error
  ## messages.
  _err_msg_len = 64

  _TriggerType_to_asdkTriggerIn = {
    TriggerType.SOFTWARE : 0,
    TriggerType.RISING_EDGE : 1,
    TriggerType.FALLING_EDGE : 2,
  }

  def _find_error_str(self):
    """Get an error string from the Alpao SDK error stack.

    Returns
    -------
      A string.  Will be empty if there was no error on the stack.
    """
    ## asdkGetLastError should write a null-terminated string but
    ## doesn't seem like it (at least CannotOpenCfg does not ends in
    ## null) so we empty the buffer ourselves before using it.  Note
    ## that even when there are no errors, we need to empty the buffer
    ## because the buffer has the message 'No error in stack'.
    ##
    ## TODO: report this upstream to Alpao and clean our code.
    self._err_msg[0:self._err_msg_len] = b'\x00' * self._err_msg_len

    err = ctypes.pointer(asdk.UInt(0))
    status = asdk.GetLastError(err, self._err_msg, self._err_msg_len)
    if status == asdk.SUCCESS:
      msg = self._err_msg.value
      if len(msg) > self._err_msg_len:
        msg = msg + "..."
      msg += "(error %i)" % (err.contents.value)
      return msg
    else:
      return ""

  def _raise_if_error(self, status, exception_cls=Exception):
    if status != asdk.SUCCESS:
      msg = self._find_error_str()
      if msg:
        raise exception_cls(msg)


  def __init__(self, serial_number, *args, **kwargs):
    """
    Parameters
    ----------
    serial_number: string
      The serial number of the deformable mirror, something like "BIL103".
    """
    super(AlpaoDeformableMirror, self).__init__(*args, **kwargs)

    ## We need to constantly check for errors and need a buffer to
    ## have the message written to.  To avoid creating a new buffer
    ## each time, have a buffer per instance.
    self._err_msg = ctypes.create_string_buffer(self._err_msg_len)

    self._dm = asdk.Init(serial_number.encode("utf-8"))
    if not self._dm:
      raise Exception("Failed to initialise connection: don't know why")
    ## In theory, asdkInit should return a NULL pointer in case of
    ## failure and that should be enough to check.  However, at least
    ## in the case of a missing configuration file it still returns a
    ## DM pointer so we still need to check for errors on the stack.
    self._raise_if_error(asdk.FAILURE)

    value = asdk.Scalar_p(asdk.Scalar())
    status = asdk.Get(self._dm, "NbOfActuator".encode("utf-8"), value)
    self._raise_if_error(status)
    self.n_actuators = int(value.contents.value)

  def apply_pattern(self, pattern):
    self._validate_patterns(pattern)
    pattern = _normalize_patterns(pattern)
    data_pointer = pattern.ctypes.data_as(ctypes.POINTER(asdk.Scalar_p))
    status = asdk.Send(self._dm, data_pointer)
    self._raise_if_error(status)

  def set_trigger_type(self, ttype):
    try:
      value = self._TriggerType_to_asdkTriggerIn[ttype]
    except KeyError:
      raise Exception("unsupported trigger of type '%s' for Alpao Mirrors"
                      % ttype.name)
    status = asdk.Set(self._dm, "TriggerIn".encode("utf-8"), value)
    self._raise_if_error(status)

  def queue_patterns(self, patterns):
    if self.trigger_type == TriggerType.SOFTWARE:
      super(AlpaoDeformableMirror, self).queue_patterns(patterns)
    else:
      self._validate_patterns(patterns)
      patterns = numpy.atleast_2d(patterns)
      n_patterns = patterns.shape[0]
      ## There is an issue with Alpao SDK in that they don't really
      ## support hardware trigger.  Instead, an hardware trigger will
      ## signal the mirror to apply all the patterns as quickly as
      ## possible.  We received a modified version from Alpao that does
      ## what we want --- each trigger applies the next pattern --- but
      ## that requires nPatt and nRepeat to have the same value, hence
      ## the last two arguments here being 'n_patterns, n_patterns'.
      data_pointer = patterns.ctypes.data_as(ctypes.POINTER(asdk.Scalar_p))
      status = asdk.SendPattern(self._dm, data_pointer
                                n_patterns, n_patterns)
      self._raise_if_error(status)

  def next_pattern(self):
    if self.trigger_type == TriggerType.SOFTWARE:
      super(AlpaoDeformableMirror, self).queue_patterns(patterns)
    else:
      raise Exception("software trigger received when set for hardware trigger")

  def zero(self):
    status = asdk.Reset(self._dm)
    self._raise_if_error(status)

  def __del__(self):
    status = asdk.Release(self._dm)
    if status != asdk.SUCCESS:
      msg = self._find_error_str()
      warnings.warn(msg)
    super(AlpaoDeformableMirror, self).__del__()
