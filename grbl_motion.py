# grbl_motion.py
# Motion control utilities for GRBL

import grbl_serial
import inkex

class GrblMotion(object):
  def __init__(self, port, stepsPerInch, penUpPosition, penDownPosition):
    self.port = port
    self.stepsPerInch = stepsPerInch
    self.penUpPosition = penUpPosition
    self.penDownPosition = penDownPosition
    
  def IsPausePressed(self):
    if (self.port is not None):
      return False; # TODO

  def sendPenUp(self, PenDelay, fSpeed):
    if (self.port is not None):
      strOutput = 'M3 S' + str(self.penUpPosition) + '\r'
      self.port.command(strOutput)
      if not fSpeed is None:
        strOutput = 'G4 P0' + '\r'
        self.port.command(strOutput)
        strOutput = f'$110={fSpeed}' + '\r'
        self.port.command(strOutput)
        strOutput = f'$111={fSpeed}' + '\r'
        self.port.command(strOutput)
      strOutput = 'G4 P' + str(PenDelay/1000.0) + '\r'
      self.port.command(strOutput)

  def sendPenDown(self, PenDelay, fSpeed):
    if (self.port is not None):
      if not fSpeed is None:
          strOutput = 'G4 P0' + '\r'
          self.port.command(strOutput)
          strOutput = f'$110={fSpeed}' + '\r'
          self.port.command(strOutput)
          strOutput = f'$111={fSpeed}' + '\r'
          self.port.command(strOutput)
      strOutput = 'M3 S' + str(self.penDownPosition) + '\r'
      self.port.command(strOutput)
      strOutput = 'G4 P' + str(PenDelay/1000.0) + '\r'
      self.port.command(strOutput)

  def doAbsoluteMove(self, x, y):
    if (self.port is not None):
      strOutput = 'G1 F5000 X'+str(round(25.4*x, 4)) + ' Y'+str(round(25.4*y, 4)) + '\r'
      self.port.command(strOutput)
      
