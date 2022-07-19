from cereal import car
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Union, no_type_check

TACO_TORQUE_THRESHOLD = 2.5  # m/s^2
GREAT_TORQUE_THRESHOLD = 1.4  # m/s^2
GOOD_TORQUE_THRESHOLD = 1.0  # m/s^2


class Tier(Enum):
  GOLD = 0
  SILVER = 1
  BRONZE = 2


class Column(Enum):
  MAKE = "Make"
  MODEL = "Model"
  PACKAGE = "Supported Package"
  LONGITUDINAL = "openpilot ACC"
  FSR_LONGITUDINAL = "Stop and Go"
  FSR_STEERING = "Steer to 0"
  STEERING_TORQUE = "Steering Torque"


class Star(Enum):
  FULL = "full"
  HALF = "half"
  EMPTY = "empty"


StarColumns = list(Column)[3:]
TierColumns = (Column.FSR_LONGITUDINAL, Column.FSR_STEERING, Column.STEERING_TORQUE)
CarFootnote = namedtuple("CarFootnote", ["text", "column", "star"], defaults=[None])


def get_year_string(years: Set[int]) -> str:
  # TODO: surely this can be simplified
  consecutive_years = []
  for year in years:
    close = {y for y in years if abs(y - year) == 1}
    for group in consecutive_years:
      if len(close.intersection(group)):
        group |= close
        break
    else:
      consecutive_years.append({year, *close})

  builder = []
  for years in consecutive_years:
    if len(years) > 1:
      builder.append(f"{min(years)}-{str(max(years))[-2:]}")
    else:
      builder.append(str(list(years)[0]))

  return ', '.join(builder)


def get_footnote(footnotes: Optional[List[Enum]], column: Column) -> Optional[Enum]:
  # Returns applicable footnote given current column
  if footnotes is not None:
    for fn in footnotes:
      if fn.value.column == column:
        return fn
  return None


@dataclass
class CarInfo:
  name: str
  package: str
  video_link: Optional[str] = None
  # TODO: make required once all cars are moved over
  years: Set[int] = field(default_factory=lambda: set())
  footnotes: Optional[List[Enum]] = None
  min_steer_speed: Optional[float] = None
  min_enable_speed: Optional[float] = None
  harness: Optional[Enum] = None

  def init(self, CP: car.CarParams, non_tested_cars: List[str], all_footnotes: Dict[Enum, int]):
    # TODO: set all the min steer speeds in carParams and remove this
    min_steer_speed = CP.minSteerSpeed
    if self.min_steer_speed is not None:
      min_steer_speed = self.min_steer_speed
      assert CP.minSteerSpeed == 0, f"{CP.carFingerprint}: Minimum steer speed set in both CarInfo and CarParams"

    assert self.harness is not None, f"{CP.carFingerprint}: Need to specify car harness"

    # TODO: set all the min enable speeds in carParams correctly and remove this
    min_enable_speed = CP.minEnableSpeed
    if self.min_enable_speed is not None:
      min_enable_speed = self.min_enable_speed

    self.car_name = CP.carName
    self.car_fingerprint = CP.carFingerprint
    self.make, self.model = self.name.split(' ', 1)
    self.year_string = get_year_string(self.years)
    self.row = {
      Column.MAKE: self.make,
      Column.MODEL: self.model,
      Column.PACKAGE: self.package,
      # StarColumns
      Column.LONGITUDINAL: Star.FULL if CP.openpilotLongitudinalControl and not CP.radarOffCan else Star.EMPTY,
      Column.FSR_LONGITUDINAL: Star.FULL if min_enable_speed <= 0. else Star.EMPTY,
      Column.FSR_STEERING: Star.FULL if min_steer_speed <= 0. else Star.EMPTY,
      # Column.STEERING_TORQUE set below
    }

    # Set steering torque star from max lateral acceleration
    assert CP.maxLateralAccel > 0.1
    if CP.maxLateralAccel >= GOOD_TORQUE_THRESHOLD:
      self.row[Column.STEERING_TORQUE] = Star.FULL
    else:
      self.row[Column.STEERING_TORQUE] = Star.EMPTY

    if CP.notCar:
      for col in StarColumns:
        self.row[col] = Star.FULL

    self.all_footnotes = all_footnotes
    for column in StarColumns:
      # Demote if footnote specifies a star
      footnote = get_footnote(self.footnotes, column)
      if footnote is not None and footnote.value.star is not None:
        self.row[column] = footnote.value.star

    # openpilot ACC star doesn't count for tiers
    full_stars = [s for col, s in self.row.items() if col in TierColumns].count(Star.FULL)
    if full_stars == len(TierColumns):
      self.tier = Tier.GOLD
    elif full_stars == (len(TierColumns)-1):
      self.tier = Tier.SILVER
    else:
      self.tier = Tier.BRONZE

    return self

  @no_type_check
  def get_column(self, column: Column, star_icon: str, footnote_tag: str, add_years: bool = True) -> str:
    item: Union[str, Star] = self.row[column]
    if column in StarColumns:
      item = star_icon.format(item.value)
    # TODO: new webpage might not use get_column, not needed?
    elif column == Column.MODEL and add_years:
      item += f" {self.year_string}"

    footnote = get_footnote(self.footnotes, column)
    if footnote is not None:
      item += footnote_tag.format(self.all_footnotes[footnote])

    return item


class Harness(Enum):
  nidec = "Honda Nidec"
  bosch_a = "Honda Bosch A"
  bosch_b = "Honda Bosch B"
  toyota = "Toyota"
  subaru = "Subaru"
  fca = "FCA"
  vw = "VW"
  j533 = "J533"
  hyundai_a = "Hyundai A"
  hyundai_b = "Hyundai B"
  hyundai_c = "Hyundai C"
  hyundai_d = "Hyundai D"
  hyundai_e = "Hyundai E"
  hyundai_f = "Hyundai F"
  hyundai_g = "Hyundai G"
  hyundai_h = "Hyundai H"
  hyundai_i = "Hyundai I"
  hyundai_j = "Hyundai J"
  hyundai_k = "Hyundai K"
  hyundai_l = "Hyundai L"
  hyundai_m = "Hyundai M"
  hyundai_n = "Hyundai N"
  hyundai_o = "Hyundai O"
  hyundai_p = "Hyundai P"
  custom = "Developer"
  obd_ii = "OBD-II"
  nissan_a = "Nissan A"
  nissan_b = "Nissan B"
  mazda = "Mazda"
  none = "None"


STAR_DESCRIPTIONS = {
  "Gas & Brakes": {  # icon and row name
    Column.FSR_LONGITUDINAL.value: [
      [Star.FULL.value, "Adaptive Cruise Control (ACC) operates down to 0 mph."],
      [Star.EMPTY.value, "Adaptive Cruise Control (ACC) available only above certain speeds. See your car's manual for the minimum speed."],
    ],
  },
  "Steering": {
    Column.FSR_STEERING.value: [
      [Star.FULL.value, "openpilot can control the steering wheel down to 0 mph."],
      [Star.EMPTY.value, "No steering control below certain speeds."],
    ],
    Column.STEERING_TORQUE.value: [
      [Star.FULL.value, "Car has enough steering torque to take tight turns."],
      [Star.EMPTY.value, "Limited ability to make turns."],
    ],
  },
}
