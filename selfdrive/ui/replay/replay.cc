#include "selfdrive/ui/replay/replay.h"

#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <regex>

#include "cereal/services.h"
#include "selfdrive/camerad/cameras/camera_common.h"
#include "selfdrive/common/timing.h"
#include "selfdrive/hardware/hw.h"

const int SEGMENT_LENGTH = 60;  // 60s
const int FORWARD_SEGS = 2;
const int BACKWARD_SEGS = 2;
const std::string LOG_ROOT =
    Hardware::PC() ? util::getenv_default("HOME", "/.comma/media/0/realdata", "/data/media/0/realdata")
                   : "/data/media/0/realdata";

int getch() {
  int ch;
  struct termios oldt;
  struct termios newt;

  tcgetattr(STDIN_FILENO, &oldt);
  newt = oldt;
  newt.c_lflag &= ~(ICANON | ECHO);

  tcsetattr(STDIN_FILENO, TCSANOW, &newt);
  ch = getchar();
  tcsetattr(STDIN_FILENO, TCSANOW, &oldt);

  return ch;
}

Replay::Replay(const QString &route, SubMaster *sm, QObject *parent) : route_(route), sm_(sm), QObject(parent) {
  QStringList block = QString(getenv("BLOCK")).split(",");
  qDebug() << "blocklist" << block;

  QStringList allow = QString(getenv("ALLOW")).split(",");
  qDebug() << "allowlist" << allow;

  std::vector<const char *> s;
  for (const auto &it : services) {
    if ((allow[0].size() == 0 || allow.contains(it.name)) &&
        !block.contains(it.name)) {
      s.push_back(it.name);
      socks_.insert(it.name);
    }
  }
  qDebug() << "services " << s;

  if (sm_ == nullptr) {
    pm_ = new PubMaster(s);
  }

  device_id_ = cl_get_device_id(CL_DEVICE_TYPE_DEFAULT);
  context_ = CL_CHECK_ERR(clCreateContext(NULL, 1, &device_id_, NULL, NULL, &err));
}

Replay::~Replay() {
  clear();
  delete pm_;
  delete vipc_server_;
  CL_CHECK(clReleaseContext(context_));
}

void Replay::clear() {
  segments_.clear();
  segment_paths_.clear();
  for (int i = 0; i < std::size(frame_queues_); ++i) {
    delete frame_queues_[i];
    frame_queues_[i] = nullptr;
  }

  current_ts_ = 0;
  seek_ts_ = 0;
  current_segment_ = seek_ts_ = 0;
}

void Replay::load() {
  if (!loadFromLocal()) {
    loadFromServer();
  }
}

void Replay::loadFromServer() {
  const QString url = "https://api.commadotai.com/v1/route/" + route_ + "/files";
  HttpRequest *http = new HttpRequest(this, url, "", !Hardware::PC());
  QObject::connect(http, &HttpRequest::receivedResponse, [=](const QString json) {
    loadFromJson(json);
    http->deleteLater();
  });
}

bool Replay::loadFromLocal() {
  QStringList list = route_.split('|');
  if (list.size() != 2) return false;

  QDir log_root(LOG_ROOT.c_str());
  QStringList folders = log_root.entryList(QStringList() << list[1] + "*", QDir::Dirs | QDir::NoDot, QDir::NoSort);
  if (folders.isEmpty()) return false;

  QMap<int, QMap<QString, QString>> segment_paths;
  for (auto folder : folders) {
    const int seg_id = folder.split("--")[2].toInt();
    auto &paths = segment_paths[seg_id];

    QDir segment(log_root.filePath(folder));
    for (auto f : segment.entryList(QDir::Files)) {
      const QString file_path = "file://" + segment.filePath(f);
      if (f.startsWith("fcamera")) {
        paths["cameras"] = file_path;
      } else if (f.startsWith("dcamera")) {
        paths["dcameras"] = file_path;
      } else if (f.startsWith("ecamera")) {
        paths["ecameras"] = file_path;
      } else if (f.startsWith("qcamera")) {
        paths["qcameras"] = file_path;
      } else if (f.startsWith("rlog")) {
        paths["logs"] = file_path;
      } else if (f.startsWith("qlog")) {
        paths["qlogs"] = file_path;
      }
    }
  }
  return loadSegments(segment_paths);
}

bool Replay::loadFromJson(const QString &json) {
  QJsonDocument doc = QJsonDocument::fromJson(json.trimmed().toUtf8());
  if (doc.isNull()) {
    qInfo() << "JSON Parse failed";
    return false;
  }
  std::regex regexp(R"(^(.*?)\/(\d+)\/(.*?))");
  QMap<int, QMap<QString, QString>> segment_paths;

  QJsonObject obj = doc.object();
  for (const QString &key : obj.keys()) {
    for (const auto &p : obj[key].toArray()) {
      std::string path = p.toString().toStdString();
      if (std::smatch match; std::regex_match(path, match, regexp)) {
        const int seg_id = std::stoi(match[2].str());
        segment_paths[seg_id][key] = p.toString();
      }
    }
  }
  return loadSegments(segment_paths);
}

bool Replay::loadSegments(const QMap<int, QMap<QString, QString>> &segment_paths) {
  // clear previous segments.
  clear();

  QString cam_file_key = "cameras";
  for (const auto &paths : segment_paths) {
    if (!paths.contains("cameras")) {
      // fallback to qcameras
      cam_file_key = "qcameras";
      break;
    }
  }

  for (int seg_id : segment_paths.keys()) {
    auto &paths = segment_paths[seg_id];
    auto log_file = paths.value("logs");
    if (log_file.isEmpty()) {
      // fallback to qlog
      log_file = paths.value("qlogs");
    }
    if (log_file.isEmpty()) continue;

    SegmentFiles &files = segment_paths_[seg_id];
    files.log_file = log_file;
    files.cam_file = paths.value(cam_file_key);
    files.dcam_file = paths.value("dcameras");
    files.wcam_file = paths.value("ecameras");
  }

  if (segment_paths_.isEmpty()) {
    qInfo() << "can't find files for " << route_;
    return false;
  }

  qInfo() << "replay route " << route_ << ", total segments:" << segment_paths_.size();
  typedef void (Replay::*threadFunc)();
  threadFunc thread_func[] = {&Replay::segmentQueueThread, &Replay::keyboardThread, &Replay::streamThread};
  for (int i = 0; i < std::size(thread_func); ++i) {
    QThread *t = QThread::create(thread_func[i], this);
    connect(t, &QThread::finished, t, &QThread::deleteLater);
    t->start();
  }
  return true;
}

// return nullptr if segment is not loaded
std::shared_ptr<Segment> Replay::getSegment(int n) {
  std::unique_lock lk(segment_lock_);
  auto it = segments_.find(n);
  return (it != segments_.end() && !it->second->loading) ? it->second : nullptr;
}

void Replay::startVipcServer(const Segment *seg) {
  VisionStreamType stream_types[] = {
      [RoadCam] = VISION_STREAM_RGB_BACK,
      [DriverCam] = VISION_STREAM_RGB_FRONT,
      [WideRoadCam] = VISION_STREAM_RGB_WIDE,
  };

  for (auto cam_type : ALL_CAMERAS) {
    const FrameReader *fr = seg->frames[cam_type];
    if (!fr || !fr->valid()) continue;

    if (!vipc_server_) {
      vipc_server_ = new VisionIpcServer("camerad", device_id_, context_);
    }

    vipc_server_->create_buffers(stream_types[cam_type], UI_BUF_COUNT, true, fr->width, fr->height);
    frame_queues_[cam_type] = new SafeQueue<const EncodeIdx *>();
    QThread *t = QThread::create(&Replay::cameraThread, this, cam_type, stream_types[cam_type]);
    connect(t, &QThread::finished, t, &QThread::deleteLater);
    t->start();
  }

  if (vipc_server_) {
    vipc_server_->start_listener();
    qDebug() << "start vipc server";
  }
}

void Replay::seekTime(int ts) {
  ts = std::clamp(ts, 0, segment_paths_.lastKey() * SEGMENT_LENGTH);
  int segment = ts / SEGMENT_LENGTH;
  while (segment <= segment_paths_.lastKey()) {
    if (segment_paths_.contains(segment)) {
      break;
    }
    ++segment;
  }
  qInfo() << "seeking to " << ts;

  seek_ts_ = ts;
  current_segment_ = ts / SEGMENT_LENGTH;
}

void Replay::pushFrame(CameraType cam_type, int seg_id, uint32_t frame_id) {
  // do nothing if no video stream for this type
  if (!frame_queues_[cam_type]) return;

  // find encodeIdx in adjacent segments_.
  const EncodeIdx *eidx = nullptr;
  int search_in[] = {seg_id, seg_id - 1, seg_id + 1};
  for (auto idx : search_in) {
    auto seg = getSegment(idx);
    if (seg && (eidx = seg->log->getFrameEncodeIdx(cam_type, frame_id))) {
      frame_queues_[cam_type]->push(eidx);
      return;
    }
  }
  qDebug() << "failed to find eidx for frame " << frame_id << " in segment " << seg_id;
}

// threads

void Replay::segmentQueueThread() {
  // maintain the segment window
  while (!exit_) {
    for (auto it = segment_paths_.begin(); it != segment_paths_.end(); ++it) {
      const int start_idx = std::max(current_segment_ - BACKWARD_SEGS, 0);
      const int end_idx = std::min(current_segment_ + FORWARD_SEGS, segment_paths_.lastKey());
      const int idx = it.key();
      std::unique_lock lk(segment_lock_);
      if (idx >= start_idx && idx <= end_idx) {
        // add segment
        if (segments_.find(idx) == segments_.end()) {
          segments_[idx] = std::make_shared<Segment>(idx, it.value());
        }
      } else {
        // remove segment
        segments_.erase(idx);
      }
    }
    QThread::msleep(100);
  }
}

void Replay::cameraThread(CameraType cam_type, VisionStreamType stream_type) {
  while (!exit_) {
    const EncodeIdx *eidx = nullptr;
    if (!frame_queues_[cam_type]->try_pop(eidx, 50)) continue;

    std::shared_ptr<Segment> seg = getSegment(eidx->segmentNum);
    if (!seg) continue;

    FrameReader *frm = seg->frames[cam_type];
    if (uint8_t *data = frm->get(eidx->segmentId)) {
      VisionIpcBufExtra extra = {};
      VisionBuf *buf = vipc_server_->get_buffer(stream_type);
      memcpy(buf->addr, data, frm->getRGBSize());
      vipc_server_->send(buf, &extra, false);
    }
  }
}

void Replay::keyboardThread() {
  char c;
  while (!exit_) {
    c = getch();
    if (c == '\n') {
      printf("Enter seek request: ");
      std::string r;
      std::cin >> r;

      try {
        if (r[0] == '#') {
          r.erase(0, 1);
          seekTime(std::stoi(r) * 60);
        } else {
          seekTime(std::stoi(r));
        }
      } catch (std::invalid_argument) {
        qDebug() << "invalid argument";
      }
      getch();  // remove \n from entering seek
    } else if (c == 'm') {
      seekTime(current_ts_ + 60);
    } else if (c == 'M') {
      seekTime(current_ts_ - 60);
    } else if (c == 's') {
      seekTime(current_ts_ + 10);
    } else if (c == 'S') {
      seekTime(current_ts_ - 10);
    } else if (c == 'G') {
      seekTime(0);
    }
  }
}

void Replay::streamThread() {
  QElapsedTimer timer;
  timer.start();

  seekTime(0);
  uint64_t route_start_ts = 0;
  int64_t last_print = 0;
  while (!exit_) {
    std::shared_ptr<Segment> seg = getSegment(current_segment_);
    if (!seg) {
      qDebug() << "waiting for events";
      QThread::msleep(100);
      continue;
    }

    if (vipc_server_ == nullptr) {
      startVipcServer(seg.get());
    }
    const Events &events = seg->log->events();

    // TODO: use initData's logMonoTime
    if (route_start_ts == 0) {
      route_start_ts = events.firstKey();
    }

    uint64_t t0 = route_start_ts + (seek_ts_ * 1e9);
    qDebug() << "unlogging at" << (t0 - route_start_ts) / 1e9;

    auto eit = events.lowerBound(t0);
    uint64_t t0r = timer.nsecsElapsed();
    int current_seek_ts_ = seek_ts_;
    while (!exit_ && current_seek_ts_ == seek_ts_ && eit != events.end()) {
      cereal::Event::Reader e = (*eit)->event();
      std::string type;
      KJ_IF_MAYBE(e_, static_cast<capnp::DynamicStruct::Reader>(e).which()) {
        type = e_->getProto().getName();
      }

      uint64_t tm = e.getLogMonoTime();
      current_ts_ = std::max(tm - route_start_ts, (unsigned long)0) / 1e9;

      if (socks_.find(type) != socks_.end()) {
        if (std::abs(current_ts_ - last_print) > 5.0) {
          last_print = current_ts_;
          qInfo() << "at " << last_print << "| segment:" << seg->id;
        }

        // keep time
        long etime = tm - t0;
        long rtime = timer.nsecsElapsed() - t0r;
        long us_behind = ((etime - rtime) * 1e-3) + 0.5;
        if (us_behind > 0 && us_behind < 1e6) {
          QThread::usleep(us_behind);
          //qDebug() << "sleeping" << us_behind << etime << timer.nsecsElapsed();
        }

        // publish frames
        if (e.which() == cereal::Event::ROAD_CAMERA_STATE) {
          pushFrame(RoadCam, seg->id, e.getRoadCameraState().getFrameId());
        } else if (e.which() == cereal::Event::DRIVER_CAMERA_STATE) {
          pushFrame(DriverCam, seg->id, e.getDriverCameraState().getFrameId());
        } else if (e.which() == cereal::Event::WIDE_ROAD_CAMERA_STATE) {
          pushFrame(WideRoadCam, seg->id, e.getWideRoadCameraState().getFrameId());
        }

        // publish msg
        if (sm_ == nullptr) {
          auto bytes = (*eit)->bytes();
          pm_->send(type.c_str(), (capnp::byte *)bytes.begin(), bytes.size());
        } else {
          // TODO: subMaster is not thread safe. are we sure we need to do this?
          sm_->update_msgs(nanos_since_boot(), {{type, e}});
        }
      }

      ++eit;
    }

    if (current_seek_ts_ == seek_ts_ && eit == events.end()) {
      // move to the next segment
      current_segment_ += 1;
      qDebug() << "move to next segment " << current_segment_;
      seek_ts_ = current_ts_.load();
    }
  }
}

// class Segment

Segment::Segment(int seg_id, const SegmentFiles &files) : id(seg_id) {
  // start logreader thread
  loading = 1;
  log = new LogReader(files.log_file);
  QObject::connect(log, &LogReader::finished, [=](bool success) { --loading; });

  // start framereader threads
  auto read_cam_frames = [=](CameraType type, const QString &file) {
    if (!file.isEmpty()) {
      loading += 1;
      FrameReader *fr = frames[type] = new FrameReader(file.toStdString());
      QObject::connect(fr, &FrameReader::finished, [=](bool success) { --loading; });
      fr->start();
    }
  };

  read_cam_frames(RoadCam, files.cam_file);
  read_cam_frames(DriverCam, files.dcam_file);
  read_cam_frames(WideRoadCam, files.wcam_file);
}

Segment::~Segment() {
  qDebug() << QString("remove segment %1").arg(id);
  delete log;
  for (auto f : frames) delete f;
}
