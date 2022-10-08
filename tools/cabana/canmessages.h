#pragma once

#include <atomic>
#include <map>

#include <QApplication>
#include <QHash>
#include <QObject>


#include "tools/replay/replay.h"

const int FPS = 20;
const static int CAN_MSG_LOG_SIZE = 50;

struct CanData {
  QString id;
  double ts;
  uint32_t address;
  uint16_t bus_time;
  uint8_t source;
  uint64_t count;
  QByteArray dat;
};

class CANMessages : public QObject {
  Q_OBJECT

public:
  CANMessages(QObject *parent);
  ~CANMessages();
  bool loadRoute(const QString &route, const QString &data_dir, bool use_qcam);
  void seekTo(double ts);
  void resetRange();
  void setRange(double min, double max);
  bool eventFilter(const Event *event);

  inline std::pair<double, double> range() const { return {begin_sec, end_sec}; }
  inline double totalSeconds() const { return replay->totalSeconds(); }
  inline double routeStartTime() const { return replay->routeStartTime() / (double)1e9; }
  inline double currentSec() const { return current_sec; }
  inline bool isZoomed() const { return is_zoomed; }
  inline const QList<CanData> &messages(const QString &id) { return can_msgs[id]; }
  inline const CanData &lastMessage(const QString &id) { return can_msgs[id].back(); }

  inline const std::vector<Event *> *events() const { return replay->events(); }
  inline void setSpeed(float speed) { replay->setSpeed(speed); }
  inline bool isPaused() const { return replay->isPaused(); }
  inline void pause(bool pause) { replay->pause(pause); }
  inline const std::vector<std::tuple<int, int, TimelineType>> getTimeline() { return replay->getTimeline(); }

signals:
  void eventsMerged();
  void rangeChanged(double min, double max);
  void updated();
  void received(std::vector<CanData> can);

public:
  std::map<QString, QList<CanData>> can_msgs;

protected:
  void process(std::vector<CanData> can);
  void segmentsMerged();

  std::atomic<double> current_sec = 0.;
  std::atomic<bool> seeking = false;
  QHash<QString, uint64_t> counters;
  double begin_sec = 0;
  double end_sec = 0;
  double event_begin_sec = 0;
  double event_end_sec = 0;
  bool is_zoomed = false;
  std::vector<CanData> msgs_buf;
  Replay *replay = nullptr;
};

inline QString toHex(const QByteArray &dat) {
  return dat.toHex(' ').toUpper();
}

// A global pointer referring to the unique CANMessages object
extern CANMessages *can;
