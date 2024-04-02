#!/usr/bin/env python3
import capnp
import contextlib
import io
import shutil
import tempfile
import os
import unittest
import pytest
import requests

from parameterized import parameterized
from unittest import mock

from cereal import log as capnp_log
from openpilot.tools.lib.logreader import (LogIterable, LogReader, comma_api_source, parse_indirect, ReadMode, InternalUnavailableException,
                                           auto_source, apply_strategy)
from openpilot.tools.lib.route import SegmentRange
from openpilot.tools.lib.url_file import URLFileException

NUM_SEGS = 17  # number of segments in the test route
ALL_SEGS = list(range(NUM_SEGS))
TEST_ROUTE = "344c5c15b34f2d8a/2024-01-03--09-37-12"
QLOG_FILE = "https://commadataci.blob.core.windows.net/openpilotci/0375fdf7b1ce594d/2019-06-13--08-32-25/3/qlog.bz2"


def noop(segment: LogIterable):
  return segment


@contextlib.contextmanager
def setup_source_scenario(is_internal=False):
  with (
    mock.patch("openpilot.tools.lib.logreader.internal_source") as internal_source_mock,
    mock.patch("openpilot.tools.lib.logreader.openpilotci_source") as openpilotci_source_mock,
    mock.patch("openpilot.tools.lib.logreader.comma_api_source") as comma_api_source_mock,
  ):
    if is_internal:
      internal_source_mock.return_value = [QLOG_FILE]
    else:
      internal_source_mock.side_effect = InternalUnavailableException

    openpilotci_source_mock.return_value = [None]
    comma_api_source_mock.return_value = [QLOG_FILE]

    yield


class TestLogReader(unittest.TestCase):
  @parameterized.expand([
    (f"{TEST_ROUTE}", ALL_SEGS),
    (f"{TEST_ROUTE.replace('/', '|')}", ALL_SEGS),
    (f"{TEST_ROUTE}--0", [0]),
    (f"{TEST_ROUTE}--5", [5]),
    (f"{TEST_ROUTE}/0", [0]),
    (f"{TEST_ROUTE}/5", [5]),
    (f"{TEST_ROUTE}/0:10", ALL_SEGS[0:10]),
    (f"{TEST_ROUTE}/0:0", []),
    (f"{TEST_ROUTE}/4:6", ALL_SEGS[4:6]),
    (f"{TEST_ROUTE}/0:-1", ALL_SEGS[0:-1]),
    (f"{TEST_ROUTE}/:5", ALL_SEGS[:5]),
    (f"{TEST_ROUTE}/2:", ALL_SEGS[2:]),
    (f"{TEST_ROUTE}/2:-1", ALL_SEGS[2:-1]),
    (f"{TEST_ROUTE}/-1", [ALL_SEGS[-1]]),
    (f"{TEST_ROUTE}/-2", [ALL_SEGS[-2]]),
    (f"{TEST_ROUTE}/-2:-1", ALL_SEGS[-2:-1]),
    (f"{TEST_ROUTE}/-4:-2", ALL_SEGS[-4:-2]),
    (f"{TEST_ROUTE}/:10:2", ALL_SEGS[:10:2]),
    (f"{TEST_ROUTE}/5::2", ALL_SEGS[5::2]),
    (f"https://useradmin.comma.ai/?onebox={TEST_ROUTE}", ALL_SEGS),
    (f"https://useradmin.comma.ai/?onebox={TEST_ROUTE.replace('/', '|')}", ALL_SEGS),
    (f"https://useradmin.comma.ai/?onebox={TEST_ROUTE.replace('/', '%7C')}", ALL_SEGS),
    (f"https://cabana.comma.ai/?route={TEST_ROUTE}", ALL_SEGS),
  ])
  def test_indirect_parsing(self, identifier, expected):
    parsed, _, _ = parse_indirect(identifier)
    sr = SegmentRange(parsed)
    self.assertListEqual(list(sr.seg_idxs), expected, identifier)

  @parameterized.expand([
    (f"{TEST_ROUTE}", f"{TEST_ROUTE}"),
    (f"{TEST_ROUTE.replace('/', '|')}", f"{TEST_ROUTE}"),
    (f"{TEST_ROUTE}--5", f"{TEST_ROUTE}/5"),
    (f"{TEST_ROUTE}/0/q", f"{TEST_ROUTE}/0/q"),
    (f"{TEST_ROUTE}/5:6/r", f"{TEST_ROUTE}/5:6/r"),
    (f"{TEST_ROUTE}/5", f"{TEST_ROUTE}/5"),
  ])
  def test_canonical_name(self, identifier, expected):
    sr = SegmentRange(identifier)
    self.assertEqual(str(sr), expected)

  @parameterized.expand([(True,), (False,)])
  @mock.patch("openpilot.tools.lib.logreader.file_exists")
  def test_direct_parsing(self, cache_enabled, file_exists_mock):
    os.environ["FILEREADER_CACHE"] = "1" if cache_enabled else "0"
    qlog = tempfile.NamedTemporaryFile(mode='wb', delete=False)

    with requests.get(QLOG_FILE, stream=True) as r:
      with qlog as f:
        shutil.copyfileobj(r.raw, f)

    for f in [QLOG_FILE, qlog.name]:
      l = len(list(LogReader(f)))
      self.assertGreater(l, 100)

    with self.assertRaises(URLFileException) if not cache_enabled else self.assertRaises(AssertionError):
      l = len(list(LogReader(QLOG_FILE.replace("/3/", "/200/"))))

    # file_exists should not be called for direct files
    self.assertEqual(file_exists_mock.call_count, 0)

  @parameterized.expand([
    (f"{TEST_ROUTE}///",),
    (f"{TEST_ROUTE}---",),
    (f"{TEST_ROUTE}/-4:--2",),
    (f"{TEST_ROUTE}/-a",),
    (f"{TEST_ROUTE}/j",),
    (f"{TEST_ROUTE}/0:1:2:3",),
    (f"{TEST_ROUTE}/:::3",),
    (f"{TEST_ROUTE}3",),
    (f"{TEST_ROUTE}-3",),
    (f"{TEST_ROUTE}--3a",),
  ])
  def test_bad_ranges(self, segment_range):
    with self.assertRaises(AssertionError):
      _ = SegmentRange(segment_range).seg_idxs

  @parameterized.expand([
    (f"{TEST_ROUTE}/0", False),
    (f"{TEST_ROUTE}/:2", False),
    (f"{TEST_ROUTE}/0:", True),
    (f"{TEST_ROUTE}/-1", True),
    (f"{TEST_ROUTE}", True),
  ])
  def test_slicing_api_call(self, segment_range, api_call):
    with mock.patch("openpilot.tools.lib.route.get_max_seg_number_cached") as max_seg_mock:
      max_seg_mock.return_value = NUM_SEGS
      _ = SegmentRange(segment_range).seg_idxs
      self.assertEqual(api_call, max_seg_mock.called)

  @pytest.mark.slow
  def test_modes(self):
    qlog_len = len(list(LogReader(f"{TEST_ROUTE}/0", ReadMode.QLOG)))
    rlog_len = len(list(LogReader(f"{TEST_ROUTE}/0", ReadMode.RLOG)))

    self.assertLess(qlog_len * 6, rlog_len)

  @pytest.mark.slow
  def test_modes_from_name(self):
    qlog_len = len(list(LogReader(f"{TEST_ROUTE}/0/q")))
    rlog_len = len(list(LogReader(f"{TEST_ROUTE}/0/r")))

    self.assertLess(qlog_len * 6, rlog_len)

  @pytest.mark.slow
  def test_list(self):
    qlog_len = len(list(LogReader(f"{TEST_ROUTE}/0/q")))
    qlog_len_2 = len(list(LogReader([f"{TEST_ROUTE}/0/q", f"{TEST_ROUTE}/0/q"])))

    self.assertEqual(qlog_len * 2, qlog_len_2)

  @pytest.mark.slow
  @mock.patch("openpilot.tools.lib.logreader._LogFileReader")
  def test_multiple_iterations(self, init_mock):
    lr = LogReader(f"{TEST_ROUTE}/0/q")
    qlog_len1 = len(list(lr))
    qlog_len2 = len(list(lr))

    # ensure we don't create multiple instances of _LogFileReader, which means downloading the files twice
    self.assertEqual(init_mock.call_count, 1)

    self.assertEqual(qlog_len1, qlog_len2)

  @pytest.mark.slow
  def test_helpers(self):
    lr = LogReader(f"{TEST_ROUTE}/0/q")
    self.assertEqual(lr.first("carParams").carFingerprint, "SUBARU OUTBACK 6TH GEN")
    self.assertTrue(0 < len(list(lr.filter("carParams"))) < len(list(lr)))

  @parameterized.expand([(True,), (False,)])
  @pytest.mark.slow
  def test_run_across_segments(self, cache_enabled):
    os.environ["FILEREADER_CACHE"] = "1" if cache_enabled else "0"
    lr = LogReader(f"{TEST_ROUTE}/0:4")
    self.assertEqual(len(lr.run_across_segments(4, noop)), len(list(lr)))

  @pytest.mark.slow
  def test_auto_mode(self):
    lr = LogReader(f"{TEST_ROUTE}/0/q")
    qlog_len = len(list(lr))
    with mock.patch("openpilot.tools.lib.route.Route.log_paths") as log_paths_mock:
      log_paths_mock.return_value = [None] * NUM_SEGS
      # Should fall back to qlogs since rlogs are not available

      with self.subTest("interactive_yes"):
        with mock.patch("sys.stdin", new=io.StringIO("y\n")):
          lr = LogReader(f"{TEST_ROUTE}/0", default_mode=ReadMode.AUTO_INTERACTIVE, default_source=comma_api_source)
          log_len = len(list(lr))
        self.assertEqual(qlog_len, log_len)

      with self.subTest("interactive_no"):
        with mock.patch("sys.stdin", new=io.StringIO("n\n")):
          with self.assertRaises(AssertionError):
            lr = LogReader(f"{TEST_ROUTE}/0", default_mode=ReadMode.AUTO_INTERACTIVE, default_source=comma_api_source)

      with self.subTest("non_interactive"):
        lr = LogReader(f"{TEST_ROUTE}/0", default_mode=ReadMode.AUTO, default_source=comma_api_source)
        log_len = len(list(lr))
        self.assertEqual(qlog_len, log_len)

  @parameterized.expand([(True,), (False,)])
  @pytest.mark.slow
  def test_auto_source_scenarios(self, is_internal):
    lr = LogReader(QLOG_FILE)
    qlog_len = len(list(lr))

    with setup_source_scenario(is_internal=is_internal):
      lr = LogReader(f"{TEST_ROUTE}/0/q")
      log_len = len(list(lr))
      self.assertEqual(qlog_len, log_len)

  @pytest.mark.slow
  def test_sort_by_time(self):
    msgs = list(LogReader(f"{TEST_ROUTE}/0/q"))
    self.assertNotEqual(msgs, sorted(msgs, key=lambda m: m.logMonoTime))

    msgs = list(LogReader(f"{TEST_ROUTE}/0/q", sort_by_time=True))
    self.assertEqual(msgs, sorted(msgs, key=lambda m: m.logMonoTime))

  def test_only_union_types(self):
    with tempfile.NamedTemporaryFile() as qlog:
      # write valid Event messages
      num_msgs = 100
      with open(qlog.name, "wb") as f:
        f.write(b"".join(capnp_log.Event.new_message().to_bytes() for _ in range(num_msgs)))

      msgs = list(LogReader(qlog.name))
      self.assertEqual(len(msgs), num_msgs)
      [m.which() for m in msgs]

      # append non-union Event message
      event_msg = capnp_log.Event.new_message()
      non_union_bytes = bytearray(event_msg.to_bytes())
      non_union_bytes[event_msg.total_size.word_count * 8] = 0xff  # set discriminant value out of range using Event word offset
      with open(qlog.name, "ab") as f:
        f.write(non_union_bytes)

      # ensure new message is added, but is not a union type
      msgs = list(LogReader(qlog.name))
      self.assertEqual(len(msgs), num_msgs + 1)
      with self.assertRaises(capnp.KjException):
        [m.which() for m in msgs]

      # should not be added when only_union_types=True
      msgs = list(LogReader(qlog.name, only_union_types=True))
      self.assertEqual(len(msgs), num_msgs)
      [m.which() for m in msgs]

  @mock.patch("openpilot.tools.lib.logreader.check_source")
  def test_source_no_logs_available(self, check_source):
    check_source.return_value = []
    exceptions = []

    modes = [ReadMode.RLOG, ReadMode.QLOG, ReadMode.AUTO]

    for mode in modes:
      try:
          auto_source(SegmentRange(TEST_ROUTE), mode)
      except Exception as e:
          exceptions.append(e)
          exceptions.append(mode)

    for i in range(0, len(exceptions), 2):
      if(str(exceptions[i + 1]) == modes[i//2]):
        self.assertEqual(str(exceptions[i]), "auto_source could not find any valid source, exceptions for sources: []")
      else:
        raise Exception("Wrong mode while an exception is raised!")

  @mock.patch("openpilot.tools.lib.logreader.check_source")
  def test_source_rlogs_not_available_qlogs_available(self, check_source):
    rlog_paths = []
    qlog_paths = ['cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/0/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/1/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/2/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/3/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/4/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/5/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/6/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/7/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/8/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/9/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/10/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/11/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/12/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/13/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/14/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/15/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/16/qlog.bz2']

    exceptions = []
    modes = [ReadMode.RLOG, ReadMode.QLOG, ReadMode.AUTO]

    for mode in modes:
      try:
        check_source.return_value = apply_strategy(mode, rlog_paths, qlog_paths)
        result = auto_source(SegmentRange(TEST_ROUTE), mode)
        if(result):
          self.assertEqual(result, qlog_paths)
      except Exception as e:
        exceptions.append(e)
        exceptions.append(mode)

    for i in range(0, len(exceptions), 2):
      if(str(exceptions[i + 1]) == modes[i]):
        self.assertEqual(str(exceptions[i]), "auto_source could not find any valid source, exceptions for sources: []")
      else:
        raise Exception("Wrong mode while an exception is raised!")


  @mock.patch("openpilot.tools.lib.logreader.check_source")
  def test_source_rlogs_segments_qlogs_rest(self, check_source):
    rlog_paths = ['cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/0/rlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/1/rlog.bz2']
    qlog_paths = ['cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/2/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/3/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/4/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/5/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/6/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/7/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/8/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/9/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/10/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/11/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/12/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/13/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/14/qlog.bz2', 'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/15/qlog.bz2',
                  'cd:/344c5c15b34f2d8a/2024-01-03--09-37-12/16/qlog.bz2']

    exceptions = []
    modes = [ReadMode.RLOG, ReadMode.AUTO]

    for mode in modes:
      try:
        check_source.return_value = apply_strategy(mode, rlog_paths, qlog_paths)
        result = auto_source(SegmentRange(TEST_ROUTE), mode)
        if(result):
          self.assertEqual(result, rlog_paths)
      except Exception as e:
        exceptions.append(e)
        exceptions.append(mode)

    for i in range(0, len(exceptions), 2):
      if(str(exceptions[i + 1]) == modes[i + 1]):
        self.assertNotEqual(str(exceptions[i]), "Exception not equal!")
      else:
        raise Exception("Wrong mode while an exception is raised!")

  @mock.patch("openpilot.tools.lib.logreader.internal_source")
  @mock.patch("openpilot.tools.lib.logreader.openpilotci_source")
  @mock.patch("openpilot.tools.lib.logreader.comma_api_source")
  @mock.patch("openpilot.tools.lib.logreader.comma_car_segments_source")
  def test_source_rlogs_not_available_commaapi(self, mock_comma_car_segments_source, mock_comma_api_source, mock_openpilotci_source, mock_internal_source):

    exceptions = []
    mock_internal_source.return_value = Exception("Internal source not available")
    mock_openpilotci_source.return_value = ['https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/0/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/1/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/2/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/3/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/4/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/5/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/6/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/7/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/8/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/9/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/10/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/11/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/12/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/13/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/14/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/15/rlog.bz2',
                                            'https://commadataci.blob.core.windows.net/openpilotci/344c5c15b34f2d8a/2024-01-03--09-37-12/16/rlog.bz2']
    mock_comma_api_source.return_value = []
    mock_comma_car_segments_source.return_value = ['https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/0/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--0--rlog.bz2&sig=R6AJ1Aj/UWxQpQx9TyOFNK0YnQs1HGDa4pkhsr2taoI%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/1/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--1--rlog.bz2&sig=sckFM2tIW6ts9CPeQwGzSQ/GlNT5kkHSyikNYVvrcfM%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/2/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--2--rlog.bz2&sig=LygCcLHR3y6ZgZa/5Cbbhv/K0aWfwd4pnqcKnzO6KUs%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/3/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--3--rlog.bz2&sig=VcnlpeM/AYXzZ8IghzAqGI6NJD8sKq2Hq8QrVU0eBZc%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/4/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--4--rlog.bz2&sig=KukNiBfoyjsUYqY%2BFqFYv3NzZnxrJvKKr2h07u/Zmw8%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/5/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--5--rlog.bz2&sig=8lP0NPSm0GDxWRUHw/BmTUJ8CUD3bBGxilgGt590ubY%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/6/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--6--rlog.bz2&sig=S7kflt8G1ApHwdIyZzNZQ8sqW58%2BSVz7bFQbR4/0BwM%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/7/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--7--rlog.bz2&sig=zDX0orxvFsTYLdgyb1z0t80DxpOT/fh8JM7e7ukfVNE%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/8/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--8--rlog.bz2&sig=eYvztxp2lAE9K1e0XnZcIRUp%2BNMmS%2Bw5TeIyZe/QqCE%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/9/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--9--rlog.bz2&sig=1nRVw1ZmTvOJOLraboX9WAkeZn6mFvxexRte1y7lyL8%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/10/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--10--rlog.bz2&sig=myN6AS1xYoO1vWjn/ujvUXNBo/3CLz%2BWU5oN3Cm%2BgnM%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/11/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--11--rlog.bz2&sig=KzmqkCGO1fOJVeTc58QC0XoOaZiP5S%2Be1D13FzWo9BA%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/12/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--12--rlog.bz2&sig=cPxA0Zyz2nVOwwwOXq4FMWYDcb8HNNVIsi/w7E4cT44%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/13/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--13--rlog.bz2&sig=zmnSMpfz217seH/Pmv3038qCCNUrRGhb42r6XzdYQk0%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/14/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--14--rlog.bz2&sig=xoqthrJuFpjyaTm/GnViHgkB%2BELSc7JjDkYAxpNnnno%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/15/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--15--rlog.bz2&sig=i0f/jpzJdBd8BT2rNCpkJsNrJ7nu8bRdEfqzmVTGyZA%3D',
                                                   'https://commadata2.blob.core.windows.net/commadata2/344c5c15b34f2d8a/2024-01-03--09-37-12/16/rlog.bz2?se=2024-03-28T09%3A36%3A11Z&sp=r&sv=2018-03-28&sr=b&rscd=attachment%3B%20filename%3D344c5c15b34f2d8a_2024-01-03--09-37-12--16--rlog.bz2&sig=WABf2DpveKtVuVcKga24q5eN0kdm5smOw3TVDDq9HrY%3D']

    try:
      result = auto_source(SegmentRange(TEST_ROUTE), ReadMode.RLOG)
    except Exception as e:
      exceptions.append(e)
      exceptions.append(ReadMode.RLOG)

    self.assertEqual(result, [])


if __name__ == "__main__":
  unittest.main()
