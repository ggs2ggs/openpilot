#!/usr/bin/env python3
import re
from cereal import car
import unittest
from collections import defaultdict

from cereal import car
from selfdrive.car.fw_versions import build_fw_dict
# from selfdrive.car.hyundai.values import CAMERA_SCC_CAR, CANFD_CAR, CAN_GEARS, CAR, CHECKSUM, DATE_FW_ECUS, \
#                                          EV_CAR, FW_QUERY_CONFIG, FW_VERSIONS, LEGACY_SAFETY_MODE_CAR, \
#                                          PLATFORM_CODE_ECUS, get_platform_codes
from selfdrive.car.toyota.values import TSS2_CAR, ANGLE_CONTROL_CAR, FW_VERSIONS, FW_QUERY_CONFIG, EV_HYBRID_CAR, \
                                        FW_PATTERN, FW_LEN_CODE, FW_PATTERN_V3, get_platform_codes
from openpilot.selfdrive.car.toyota.values import CAR, DBC, TSS2_CAR, ANGLE_CONTROL_CAR, RADAR_ACC_CAR, FW_VERSIONS

Ecu = car.CarParams.Ecu

ECU_NAME = {v: k for k, v in Ecu.schema.enumerants.items()}


class TestToyotaInterfaces(unittest.TestCase):
  def test_car_sets(self):
    self.assertTrue(len(ANGLE_CONTROL_CAR - TSS2_CAR) == 0)
    self.assertTrue(len(RADAR_ACC_CAR - TSS2_CAR) == 0)

  def test_tss2_dbc(self):
    # We make some assumptions about TSS2 platforms,
    # like looking up certain signals only in this DBC
    for car_model, dbc in DBC.items():
      if car_model in TSS2_CAR:
        self.assertEqual(dbc["pt"], "toyota_nodsu_pt_generated")

  def test_essential_ecus(self):
    # Asserts standard ECUs exist for each platform
    common_ecus = {Ecu.fwdRadar, Ecu.fwdCamera}
    for car_model, ecus in FW_VERSIONS.items():
      with self.subTest(car_model=car_model):
        present_ecus = {ecu[0] for ecu in ecus}
        missing_ecus = common_ecus - present_ecus
        self.assertEqual(len(missing_ecus), 0)

        # Some exceptions for other common ECUs
        if car_model not in (CAR.ALPHARD_TSS2,):
          self.assertIn(Ecu.abs, present_ecus)

        if car_model not in (CAR.MIRAI,):
          self.assertIn(Ecu.engine, present_ecus)

        if car_model not in (CAR.PRIUS_V, CAR.LEXUS_CTH):
          self.assertIn(Ecu.eps, present_ecus)


class TestToyotaFingerprint(unittest.TestCase):
  def test_fw_pattern(self):
    for car_model, ecus in FW_VERSIONS.items():
      # print()
      # print(car_model)

      for ecu, fws in ecus.items():
        for fw in fws:

          print('\ninput', fw)
          get_platform_codes([fw])
          continue
          match = FW_PATTERN.search(fw)
          length = FW_LEN_CODE.search(fw)
          if ecu[0] in (Ecu.fwdRadar, Ecu.fwdCamera):
            assert (length is None) == (car_model not in TSS2_CAR), (car_model, ecu, fw)
          if ecu[0] in (Ecu.engine,):
            assert length is not None
          # assert match is not None, (ecu, fw, match)
          # print(fw, match)

  # def test_fw_debugging(self):
  #   for car_model, ecus in FW_VERSIONS.items():
  #     print()
  #     print(car_model)
  #     cam_len_code = False
  #     eng_len_code = False
  #
  #     for ecu, fws in ecus.items():
  #       if ecu[0] in (Ecu.fwdRadar, Ecu.fwdCamera):
  #         cam_len_code |= all(f[0] < 4 for f in fws)
  #       if ecu[0] in (Ecu.engine, Ecu.abs):
  #         eng_len_code |= all(1 < f[0] < 4 for f in fws)
  #         print(ecu, eng_len_code)
  #
  #     if (car_model in TSS2_CAR) != cam_len_code:
  #       print(car_model, car_model in TSS2_CAR, cam_len_code)
  #
  #     if (car_model in EV_HYBRID_CAR) != eng_len_code:
  #       print('MISMATCH', car_model, car_model in EV_HYBRID_CAR, eng_len_code)

  def test_shared_fw(self):
    return
    all_fw = defaultdict(set)
    for car_model, ecus in FW_VERSIONS.items():
      # print()
      # print(car_model)

      for ecu, fws in ecus.items():
        parts = set()
        for fw in fws:
          length, part = FW_PATTERN_V3.search(fw).groups()
          parts.add(part)

          all_fw[(ecu[1], fw)].add(car_model)
        if len(parts) > 1:
          print('uoh' ,car_model, ecu, parts)

    # print(all_fw)

    # shared abs (or whatever is in the continue statement)
    shared = defaultdict(set)

    for car_model, ecus in FW_VERSIONS.items():
      # print()
      # print(car_model)

      for ecu, fws in ecus.items():
        if ecu[0] != Ecu.abs:
          continue
        for fw in fws:
          if len(all_fw[ecu[1], fw]) > 1:
            shared[car_model] |= all_fw[ecu[1], fw]
          # print(car_model, all_fw[ecu[1], fw])
          # # all_fw[(ecu[1], fw)].add(car_model)

    print(shared)
    print(len(shared))


  # Tests for platform codes, part numbers, and FW dates which Hyundai will use to fuzzy
  # fingerprint in the absence of full FW matches:
  # def test_platform_code_ecus_available(self):
  #   # TODO: add queries for these non-CAN FD cars to get EPS
  #   no_eps_platforms = CANFD_CAR | {CAR.KIA_SORENTO, CAR.KIA_OPTIMA_G4, CAR.KIA_OPTIMA_G4_FL,
  #                                   CAR.SONATA_LF, CAR.TUCSON, CAR.GENESIS_G90, CAR.GENESIS_G80}
  #
  #   # Asserts ECU keys essential for fuzzy fingerprinting are available on all platforms
  #   for car_model, ecus in FW_VERSIONS.items():
  #     with self.subTest(car_model=car_model):
  #       for platform_code_ecu in PLATFORM_CODE_ECUS:
  #         if platform_code_ecu in (Ecu.fwdRadar, Ecu.eps) and car_model == CAR.HYUNDAI_GENESIS:
  #           continue
  #         if platform_code_ecu == Ecu.eps and car_model in no_eps_platforms:
  #           continue
  #         self.assertIn(platform_code_ecu, [e[0] for e in ecus])
  #
  # def test_fw_format(self):
  #   # Asserts:
  #   # - every supported ECU FW version returns one platform code
  #   # - every supported ECU FW version has a part number
  #   # - expected parsing of ECU FW dates
  #
  #   for car_model, ecus in FW_VERSIONS.items():
  #     with self.subTest(car_model=car_model):
  #       for ecu, fws in ecus.items():
  #         if ecu[0] not in PLATFORM_CODE_ECUS:
  #           continue
  #
  #         codes = set()
  #         for fw in fws:
  #           result = get_platform_codes([fw])
  #           self.assertEqual(1, len(result), f"Unable to parse FW: {fw}")
  #           codes |= result
  #
  #         if ecu[0] not in DATE_FW_ECUS or car_model in NO_DATES_PLATFORMS:
  #           self.assertTrue(all({date is None for _, date in codes}))
  #         else:
  #           self.assertTrue(all({date is not None for _, date in codes}))
  #
  #         if car_model == CAR.HYUNDAI_GENESIS:
  #           raise unittest.SkipTest("No part numbers for car model")
  #
  #         # Hyundai places the ECU part number in their FW versions, assert all parsable
  #         # Some examples of valid formats: b"56310-L0010", b"56310L0010", b"56310/M6300"
  #         self.assertTrue(all({b"-" in code for code, _ in codes}),
  #                         f"FW does not have part number: {fw}")
  #
  # def test_platform_codes_spot_check(self):
  #   # Asserts basic platform code parsing behavior for a few cases
  #   results = get_platform_codes([b"\xf1\x00DH LKAS 1.1 -150210"])
  #   self.assertEqual(results, {(b"DH", b"150210")})
  #
  #   # Some cameras and all radars do not have dates
  #   results = get_platform_codes([b"\xf1\x00AEhe SCC H-CUP      1.01 1.01 96400-G2000         "])
  #   self.assertEqual(results, {(b"AEhe-G2000", None)})
  #
  #   results = get_platform_codes([b"\xf1\x00CV1_ RDR -----      1.00 1.01 99110-CV000         "])
  #   self.assertEqual(results, {(b"CV1-CV000", None)})
  #
  #   results = get_platform_codes([
  #     b"\xf1\x00DH LKAS 1.1 -150210",
  #     b"\xf1\x00AEhe SCC H-CUP      1.01 1.01 96400-G2000         ",
  #     b"\xf1\x00CV1_ RDR -----      1.00 1.01 99110-CV000         ",
  #   ])
  #   self.assertEqual(results, {(b"DH", b"150210"), (b"AEhe-G2000", None), (b"CV1-CV000", None)})
  #
  #   results = get_platform_codes([
  #     b"\xf1\x00LX2 MFC  AT USA LHD 1.00 1.07 99211-S8100 220222",
  #     b"\xf1\x00LX2 MFC  AT USA LHD 1.00 1.08 99211-S8100 211103",
  #     b"\xf1\x00ON  MFC  AT USA LHD 1.00 1.01 99211-S9100 190405",
  #     b"\xf1\x00ON  MFC  AT USA LHD 1.00 1.03 99211-S9100 190720",
  #   ])
  #   self.assertEqual(results, {(b"LX2-S8100", b"220222"), (b"LX2-S8100", b"211103"),
  #                              (b"ON-S9100", b"190405"), (b"ON-S9100", b"190720")})
  #
  # def test_fuzzy_excluded_platforms(self):
  #   # Asserts a list of platforms that will not fuzzy fingerprint with platform codes due to them being shared.
  #   # This list can be shrunk as we combine platforms and detect features
  #   excluded_platforms = {
  #     CAR.GENESIS_G70,            # shared platform code, part number, and date
  #     CAR.GENESIS_G70_2020,
  #     CAR.TUCSON_4TH_GEN,         # shared platform code and part number
  #     CAR.TUCSON_HYBRID_4TH_GEN,
  #   }
  #   excluded_platforms |= CANFD_CAR - EV_CAR  # shared platform codes
  #   excluded_platforms |= NO_DATES_PLATFORMS  # date codes are required to match
  #
  #   platforms_with_shared_codes = set()
  #   for platform, fw_by_addr in FW_VERSIONS.items():
  #     car_fw = []
  #     for ecu, fw_versions in fw_by_addr.items():
  #       ecu_name, addr, sub_addr = ecu
  #       for fw in fw_versions:
  #         car_fw.append({"ecu": ecu_name, "fwVersion": fw, "address": addr,
  #                        "subAddress": 0 if sub_addr is None else sub_addr})
  #
  #     CP = car.CarParams.new_message(carFw=car_fw)
  #     matches = FW_QUERY_CONFIG.match_fw_to_car_fuzzy(build_fw_dict(CP.carFw))
  #     if len(matches) == 1:
  #       self.assertEqual(list(matches)[0], platform)
  #     else:
  #       platforms_with_shared_codes.add(platform)
  #
  #   self.assertEqual(platforms_with_shared_codes, excluded_platforms)


if __name__ == "__main__":
  unittest.main()
