#include "selfdrive/ui/replay/replay.h"

#include <QApplication>
#include <QElapsedTimer>

#include "cereal/services.h"
#include "selfdrive/camerad/cameras/camera_common.h"
#include "selfdrive/common/timing.h"
#include "selfdrive/hardware/hw.h"

Replay::Replay(QString route, QStringList allow, QStringList block, SubMaster *sm_, QObject *parent) : sm(sm_), QObject(parent) {
  std::vector<const char*> s;
  for (const auto &it : services) {
    if ((allow.size() == 0 || allow.contains(it.name)) &&
        !block.contains(it.name)) {
      s.push_back(it.name);
      socks.append(std::string(it.name));
    }
  }
  qDebug() << "services " << s;

  if (sm == nullptr) {
    pm = new PubMaster(s);
  }

  route_ = std::make_unique<Route>(route);
  // queueSegment is always executed in the main thread
  connect(this, &Replay::segmentChanged, this, &Replay::queueSegment);
}

void Replay::start(){
  // load route
  if (!route_->load() || route_->size() == 0) {
    qDebug() << "failed load route" << route_->name() << "from server";
    return;
  }
  qDebug() << "load route" << route_->name() << route_->size() << "segments";

  segments.resize(route_->size());
  setCurrentSegment(0);

  // start strema thread
  thread = new QThread;
  QObject::connect(thread, &QThread::started, [=]() { stream(); });
  thread->start();
}

void Replay::seekTo(int seconds) {
  if (segments.empty()) return;

  updating_events = true;

  std::unique_lock lk(lock);
  seconds = std::clamp(seconds, 0, (int)segments.size() * 60);
  qInfo() << "seeking to " << seconds;
  seek_ts = seconds;
  setCurrentSegment(seconds / 60);
  updating_events = false;
}

void Replay::relativeSeek(int seconds) {
  seekTo(current_ts + seconds);
}

void Replay::setCurrentSegment(int n) {
  if (current_segment.exchange(n) != n) {
    emit segmentChanged(n);
  }
}

// maintain the segment window
void Replay::queueSegment() {
  assert(QThread::currentThreadId() == qApp->thread()->currentThreadId());
  
  // fetch segments forward
  int cur_seg = current_segment.load();
  int end_idx = cur_seg;
  for (int i = cur_seg, fwd = 0; i < segments.size() && fwd <= FORWARD_SEGS; ++i) {
    if (!segments[i]) {
      segments[i] = std::make_unique<Segment>(i, route_->at(i));
      QObject::connect(segments[i].get(), &Segment::loadFinished, this, &Replay::queueSegment);
    } 
    // skip invalid segment
    fwd += segments[i]->isValid();
    end_idx = i;
  }

  // merge segments
  mergeSegments(cur_seg, end_idx);
}

void Replay::mergeSegments(int cur_seg, int end_idx) {
  // segments must be merged in sequence.
  std::vector<int> segments_need_merge;
  const int begin_idx = std::max(cur_seg - BACKWARD_SEGS, 0);
  for (int i = begin_idx; i <= end_idx; ++i) {
    if (segments[i] && segments[i]->isLoaded()) {
      segments_need_merge.push_back(i);
    } else if (i >= cur_seg) {
      // Segment is valid,but still loading. can't skip it to merge the next one.
      // Otherwise the stream thread may jump to the next segment.
      break;
    }
  }

  if (segments_need_merge != segments_merged) {
    qDebug() << "merge segments" << segments_need_merge;
    segments_merged = segments_need_merge;

    QMultiMap<uint64_t, Event *> *new_events = new QMultiMap<uint64_t, Event *>();
    std::unordered_map<uint32_t, EncodeIdx> *new_eidx = new std::unordered_map<uint32_t, EncodeIdx>[MAX_CAMERAS];
    for (int n : segments_need_merge) {
      auto &segment = segments[n];
      *new_events += segment->log->events;
      for (CameraType cam_type : ALL_CAMERAS) {
        new_eidx[cam_type].insert(segment->log->eidx[cam_type].begin(), segment->log->eidx[cam_type].end());
      }
    }

    // update logs
    // set updating_events to true to force stream thread relase the lock
    updating_events = true;
    lock.lock();
    if (route_start_ts == 0) {
      // get route_start_ts from initData
      for (Event *e : *new_events) {
        if (e->which == cereal::Event::Which::INIT_DATA) {
          route_start_ts = e->mono_time;
          break;
        }
      }
      if (route_start_ts == 0) {
        // this shound not happen
        route_start_ts = new_events->firstKey();
      }
    }

    auto prev_events = std::exchange(events, new_events);
    auto prev_eidx = std::exchange(eidx, new_eidx);
    updating_events = false;
    lock.unlock();

    // free logs
    delete prev_events;
    delete[] prev_eidx;
    for (int i = 0; i < segments.size(); i++) {
      if ((i < begin_idx || i > end_idx) && segments[i]) {
        segments[i].reset(nullptr);
      }
    }
  }
}

void Replay::stream() {
  uint64_t cur_mono_time = 0;
  bool waiting_printed = false;

  while (true) {
    std::unique_lock lk(lock);

    uint64_t evt_start_ts = seek_ts != -1 ? route_start_ts + (seek_ts * 1e9) : cur_mono_time;
    QMultiMap<uint64_t, Event *>::iterator eit;
    if (!events || (eit = events->lowerBound(evt_start_ts)) == events->end()) {
      lock.unlock();
      if (!waiting_printed) {
        qDebug() << "waiting for events...";
        waiting_printed = true;
      }
      QThread::msleep(100);
      continue;
    }
    waiting_printed = false;
    seek_ts = -1;
    qDebug() << "unlogging at" << int((evt_start_ts - route_start_ts) / 1e9);

    uint64_t loop_start_ts = nanos_since_boot();
    for (/**/; !updating_events && eit != events->end(); ++eit) {
      cereal::Event::Reader e = (*eit)->event;
      std::string type;
      KJ_IF_MAYBE(e_, static_cast<capnp::DynamicStruct::Reader>(e).which()) {
        type = e_->getProto().getName();
      }

      if (socks.contains(type)) {
        cur_mono_time = (*eit)->mono_time;
        current_ts = (cur_mono_time - route_start_ts) / 1e9;
        setCurrentSegment(current_ts / 60);
        if (std::abs(current_ts - last_print) > 5.0) {
          last_print = current_ts;
          qInfo() << "at " << int(last_print) << "s";
        }

        // keep time
        long etime = cur_mono_time - evt_start_ts;
        long rtime = nanos_since_boot() - loop_start_ts;
        long us_behind = ((etime - rtime) * 1e-3) + 0.5;
        if (us_behind > 0 && us_behind < 1e6) {
          QThread::usleep(us_behind);
          //qDebug() << "sleeping" << us_behind << etime << timer.nsecsElapsed();
        }

        // publish frame
        // TODO: publish all frames
        if (type == "roadCameraState") {
          auto fr = e.getRoadCameraState();

          auto it_ = eidx[RoadCam].find(fr.getFrameId());
          if (it_ != eidx[RoadCam].end()) {
            EncodeIdx &e = it_->second;
            auto &seg = segments[e.segmentNum]; 
            if (seg && seg->isLoaded()) {
              auto &frm = seg->frames[RoadCam];
              if (vipc_server == nullptr) {
                cl_device_id device_id = cl_get_device_id(CL_DEVICE_TYPE_DEFAULT);
                cl_context context = CL_CHECK_ERR(clCreateContext(NULL, 1, &device_id, NULL, NULL, &err));

                vipc_server = new VisionIpcServer("camerad", device_id, context);
                vipc_server->create_buffers(VisionStreamType::VISION_STREAM_RGB_BACK, UI_BUF_COUNT,
                                            true, frm->width, frm->height);
                vipc_server->start_listener();
              }

              uint8_t *dat = frm->get(e.frameEncodeId);
              if (dat) {
                VisionIpcBufExtra extra = {};
                VisionBuf *buf = vipc_server->get_buffer(VisionStreamType::VISION_STREAM_RGB_BACK);
                memcpy(buf->addr, dat, frm->getRGBSize());
                vipc_server->send(buf, &extra, false);
              }
            }
          }
        }

        // publish msg
        if (sm == nullptr) {
          auto bytes = (*eit)->bytes();
          pm->send(type.c_str(), (capnp::byte *)bytes.begin(), bytes.size());
        } else {
          std::vector<std::pair<std::string, cereal::Event::Reader>> messages;
          messages.push_back({type, e});
          sm->update_msgs(nanos_since_boot(), messages);
        }
      }
    }
    lk.unlock();
    usleep(0);
  }
}
