#include <sys/resource.h>

#include <QApplication>
#include <QSoundEffect>
#include <QString>
#include <QThread>
#include <map>

#include "cereal/messaging/messaging.h"
#include "selfdrive/common/util.h"
#include "selfdrive/hardware/hw.h"
#include "selfdrive/ui/ui.h"

const std::tuple<AudibleAlert, QString, bool> sound_list[] = {
    {AudibleAlert::CHIME_DISENGAGE, "disengaged.wav", false},
    {AudibleAlert::CHIME_ENGAGE, "engaged.wav", false},
    {AudibleAlert::CHIME_WARNING1, "warning_1.wav", false},
    {AudibleAlert::CHIME_WARNING2, "warning_2.wav", false},
    {AudibleAlert::CHIME_WARNING2_REPEAT, "warning_2.wav", true},
    {AudibleAlert::CHIME_WARNING_REPEAT, "warning_repeat.wav", true},
    {AudibleAlert::CHIME_ERROR, "error.wav", false},
    {AudibleAlert::CHIME_PROMPT, "error.wav", false},
};

class Sound : public QObject {
public:
  explicit Sound(QObject *parent = 0);
  void update();
  void setAlert(const QString &alert_type, AudibleAlert sound);

 protected:
  AudibleAlert current_sound = AudibleAlert::NONE;
  QString current_alert_type;
  float current_volume = Hardware::MIN_VOLUME;

  QMap<AudibleAlert, QPair<QSoundEffect *, int>> sounds;
  SubMaster sm;
};
