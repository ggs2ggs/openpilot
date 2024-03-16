from openpilot.selfdrive.car import CarSpecs, PlatformConfig, Platforms


class CAR(Platforms):
  mock = PlatformConfig(
    None,
    CarSpecs(mass=1700, wheelbase=2.7, steerRatio=13),
    {}
  )
