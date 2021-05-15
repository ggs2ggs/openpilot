#include "selfdrive/ui/replay/replay.h"

#include <QJsonDocument>
#include <QJsonObject>

#include "cereal/services.h"
#include "selfdrive/camerad/cameras/camera_common.h"
#include "selfdrive/common/timing.h"
#include "selfdrive/hardware/hw.h"

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

Replay::Replay(QString route, SubMaster *sm_, QObject *parent) : sm(sm_), QObject(parent) {
  QStringList block = QString(getenv("BLOCK")).split(",");
  qDebug() << "blocklist" << block;

  QStringList allow = QString(getenv("ALLOW")).split(",");
  qDebug() << "allowlist" << allow;

  if (sm == nullptr) {
    ctx = Context::create();
    for (const auto &it : services) {
      std::string name = it.name;
      if ((allow[0].size() > 0 && !allow.contains(name.c_str())) ||
          block.contains(name.c_str())) {
        continue;
      }

      PubSocket *sock = PubSocket::create(ctx, name);
      if (sock == NULL) {
        qDebug() << "FAILED " << name.c_str();
        continue;
      }
      socks.insert(name, sock);
    }
  }

  const QString url = "https://api.commadotai.com/v1/route/" + route + "/files";
  http = new HttpRequest(this, url, "", Hardware::PC());
  QObject::connect(http, &HttpRequest::receivedResponse, this, &Replay::parseResponse);
}

void Replay::parseResponse(const QString &response) {
  QJsonDocument doc = QJsonDocument::fromJson(response.trimmed().toUtf8());
  if (doc.isNull()) {
    qDebug() << "JSON Parse failed";
    return;
  }

  camera_paths = doc["cameras"].toArray();
  log_paths = doc["logs"].toArray();

  seekTime(0);
}

void Replay::addSegment(int n) {
  assert((n >= 0) && (n < log_paths.size()) && (n < camera_paths.size()));
  if (lrs.find(n) != lrs.end()) {
    return;
  }

  QThread *t = new QThread;
  lrs.insert(n, new LogReader(log_paths.at(n).toString(), &events, &events_lock, &eidx));

  lrs[n]->moveToThread(t);
  QObject::connect(t, &QThread::started, lrs[n], &LogReader::process);
  t->start();

  frs.insert(n, new FrameReader(qPrintable(camera_paths.at(n).toString())));
}

void Replay::removeSegment(int n) {
  if (lrs.contains(n)) {
    auto lr = lrs.take(n);
    delete lr;
  }
  if (frs.contains(n)) {
    auto fr = frs.take(n);
    delete fr;
  }

  // TODO: add this back
  /*
  events_lock.lockForWrite();
  auto eit = events.begin();
  while (eit != events.end()) {
    if(std::abs(eit.key()/1e9 - getCurrentTime()/1e9) > 60.0){
      eit = events.erase(eit);
      continue;
    }
    eit++;
  }
  events_lock.unlock();
  */
}

void Replay::start(){
  thread = new QThread;
  QObject::connect(thread, &QThread::started, [=](){
    stream();
  });
  thread->start();

  kb_thread = new QThread;
  QObject::connect(kb_thread, &QThread::started, [=](){
    keyboardThread();
  });
  kb_thread->start();

  queue_thread = new QThread;
  QObject::connect(queue_thread, &QThread::started, [=](){
    segmentQueueThread();
  });
  queue_thread->start();
}

void Replay::seekTime(int ts){
  qInfo() << "seeking to " << ts;
  current_ts = ts;
  current_segment = ts/60;
}

void Replay::segmentQueueThread() {
  // maintain the segment window
  while (true) {
    for (int i = 0; i < log_paths.size(); i++) {
      int start_idx = std::max(current_segment - BACKWARD_SEGS, 0);
      int end_idx = std::min(current_segment + FORWARD_SEGS, log_paths.size());
      if (i >= start_idx && i <= end_idx) {
        addSegment(i);
      } else {
        removeSegment(i);
      }
    }
    QThread::msleep(100);
  }
}

void Replay::keyboardThread() {
  char c;
  while (true) {
    c = getch();
    if(c == '\n'){
      printf("Enter seek request: ");
      std::string r;
      std::cin >> r;

      if(r[0] == '#') {
        r.erase(0, 1);
        seekTime(std::stoi(r)*60);
      } else {
        seekTime(std::stoi(r));
      }
      getch(); // remove \n from entering seek
    } else if (c == 'm') {
      //seek_queue.enqueue({true, 60});
    } else if (c == 'M') {
      //seek_queue.enqueue({true, -60});
    } else if (c == 's') {
      //seek_queue.enqueue({true, 10});
    } else if (c == 'S') {
      //seek_queue.enqueue({true, -10});
    } else if (c == 'G') {
      //seek_queue.clear();
      //seek_queue.enqueue({false, 0});
    }
  }
}

void Replay::stream() {
  QElapsedTimer timer;
  timer.start();

  route_start_ts = 0;
  while (true) {
    if (events.size() == 0) {
      qDebug() << "waiting for events";
      QThread::msleep(100);
      continue;
    }

    // TODO: use initData's logMonoTime
    if (route_start_ts == 0) {
      route_start_ts = events.firstKey();
    }

    uint64_t t0 = seek_ts * 1e9;
    qDebug() << "unlogging at" << (t0 - route_start_ts) / 1e9;

    // wait for future events to be ready?
    auto eit = events.lowerBound(t0);
    while (eit.key() - t0 > 1e9) {
      eit = events.lowerBound(t0);
    }

    uint64_t t0r = timer.nsecsElapsed();
    while ((eit != events.end()) && seek_ts == 0) {
      cereal::Event::Reader e = (*eit);
      std::string type;
      KJ_IF_MAYBE(e_, static_cast<capnp::DynamicStruct::Reader>(e).which()) {
        type = e_->getProto().getName();
      }

      uint64_t tm = e.getLogMonoTime();
      current_ts = tm / 1e9;

      auto it = socks.find(type);
      if (it != socks.end()) {
        long etime = tm-t0;

        float timestamp = (tm - route_start_ts)/1e9;
        if(std::abs(timestamp-last_print) > 5.0){
          last_print = timestamp;
          qInfo() << "at " << last_print;
        }

        long rtime = timer.nsecsElapsed() - t0r;
        long us_behind = ((etime-rtime)*1e-3)+0.5;
        if (us_behind > 0 && us_behind < 1e6) {
          QThread::usleep(us_behind);
          //qDebug() << "sleeping" << us_behind << etime << timer.nsecsElapsed();
        }

        // publish frame
        // TODO: publish all frames
        if (type == "roadCameraState") {
          auto fr = e.getRoadCameraState();

          auto it_ = eidx.find(fr.getFrameId());
          if (it_ != eidx.end()) {
            auto pp = *it_;
            if (frs.find(pp.first) != frs.end()) {
              auto frm = frs[pp.first];
              auto data = frm->get(pp.second);

              if (vipc_server == nullptr) {
                cl_device_id device_id = cl_get_device_id(CL_DEVICE_TYPE_DEFAULT);
                cl_context context = CL_CHECK_ERR(clCreateContext(NULL, 1, &device_id, NULL, NULL, &err));

                vipc_server = new VisionIpcServer("camerad", device_id, context);
                vipc_server->create_buffers(VisionStreamType::VISION_STREAM_RGB_BACK, UI_BUF_COUNT, true, frm->width, frm->height);

                vipc_server->start_listener();
              }

              VisionBuf *buf = vipc_server->get_buffer(VisionStreamType::VISION_STREAM_RGB_BACK);
              memcpy(buf->addr, data, frm->getRGBSize());
              VisionIpcBufExtra extra = {};

              vipc_server->send(buf, &extra, false);
            }
          }
        }

        // publish msg
        if (sm == nullptr){
          capnp::MallocMessageBuilder msg;
          msg.setRoot(e);
          auto words = capnp::messageToFlatArray(msg);
          auto bytes = words.asBytes();

          (*it)->send((char*)bytes.begin(), bytes.size());
        } else{
          std::vector<std::pair<std::string, cereal::Event::Reader>> messages;
          messages.push_back({type, e});
          sm->update_msgs(nanos_since_boot(), messages);
        }
      }

      ++eit;
    }
  }
}
