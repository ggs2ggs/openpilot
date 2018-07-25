from selfdrive.car.hyundai.values import CAR, DBC
from selfdrive.can.parser import CANParser
from selfdrive.config import Conversions as CV

def get_can_parser2(CP):

  signals = [
    ("Byte0", "LKAS11", 0),
    ("Byte1", "LKAS11", 0),
    ("Byte2", "LKAS11", 0),
    ("Byte3", "LKAS11", 0),
    ("Byte4", "LKAS11", 0),
    ("Byte5", "LKAS11", 0),
    ("Byte6", "LKAS11", 0), # Checksum
    ("Byte7", "LKAS11", 0),

    ("Byte0", "LKAS12", 0),
    ("Byte1", "LKAS12", 0),
    ("Byte2", "LKAS12", 0),
    ("Byte3", "LKAS12", 0),
    ("Byte4", "LKAS12", 0),
    ("Byte5", "LKAS12", 0)
  ]

  checks = [
    ("LKAS11", 100),
    ("LKAS12", 10)
  ]

  return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, 1)


class CamState(object):
  def __init__(self, CP):
    self.CP = CP
    
    # initialize can parser
    self.car_fingerprint = CP.carFingerprint


  def update(self, cp):
    # copy can_valid
    self.can_valid = cp.can_valid

    self.lkas11_b0 = cp.vl["LKAS11"]['Byte0']
    self.lkas11_b1 = cp.vl["LKAS11"]['Byte1']
    self.lkas11_b2 = cp.vl["LKAS11"]['Byte2']
    self.lkas11_b3 = cp.vl["LKAS11"]['Byte3']
    self.lkas11_b4 = cp.vl["LKAS11"]['Byte4']
    self.lkas11_b5 = cp.vl["LKAS11"]['Byte5']
    self.lkas11_b6 = cp.vl["LKAS11"]['Byte6']
    self.lkas11_b7 = cp.vl["LKAS11"]['Byte7']
    
    self.lkas12_b0 = cp.vl["LKAS12"]['Byte0']
    self.lkas12_b1 = cp.vl["LKAS12"]['Byte1']
    self.lkas12_b2 = cp.vl["LKAS12"]['Byte2']
    self.lkas12_b3 = cp.vl["LKAS12"]['Byte3']
    self.lkas12_b4 = cp.vl["LKAS12"]['Byte4']
    self.lkas12_b5 = cp.vl["LKAS12"]['Byte5']