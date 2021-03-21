#include <QDebug>
#include <QJsonDocument>
#include <QJsonObject>
#include <QVBoxLayout>

#include "api.hpp"
#include "common/params.h"
#include "drive_stats.hpp"

const double MILE_TO_KM = 1.60934;

static QLayout* build_stat_layout(QLabel** metric, const QString& name) {
  QVBoxLayout* layout = new QVBoxLayout;
  layout->setMargin(0);
  *metric = new QLabel("0");
  (*metric)->setStyleSheet("font-size: 80px; font-weight: 600;");
  layout->addWidget(*metric, 0, Qt::AlignLeft);

  QLabel* label = new QLabel(name);
  label->setStyleSheet("font-size: 45px; font-weight: 500;");
  layout->addWidget(label, 0, Qt::AlignLeft);
  return layout;
}

void DriveStats::parseResponse(QString response, bool save) {
  response = response.trimmed();
  QJsonDocument doc = QJsonDocument::fromJson(response.toUtf8());
  if (doc.isNull()) {
    qDebug() << "JSON Parse failed on getting past drives statistics";
    return;
  }

  auto update = [](const QJsonObject &obj, StatsLabels& labels, bool metric) {
    labels.routes->setText(QString::number((int)obj["routes"].toDouble()));
    labels.distance->setText(QString::number(obj["distance"].toDouble() * (metric ? MILE_TO_KM : 1)));
    labels.hours->setText(QString::number((int)(obj["minutes"].toDouble() / 60)));
  };

  bool metric = Params().read_db_bool("IsMetric");
  QJsonObject json = doc.object();
  update(json["all"].toObject(), all_, metric);
  update(json["week"].toObject(), week_, metric);

  if (save) { Params().write_db_value("DriveStats", response.toStdString()); }
}

DriveStats::DriveStats(QWidget* parent) : QWidget(parent) {
  setStyleSheet("QLabel {font-size: 48px; font-weight: 500;}");

  auto add_stats_layouts = [&](QGridLayout* gl, StatsLabels& labels, int row, const char* distance_unit) {
    gl->addLayout(build_stat_layout(&labels.routes, "DRIVES"), row, 0, 3, 1);
    gl->addLayout(build_stat_layout(&labels.distance, distance_unit), row, 1, 3, 1);
    gl->addLayout(build_stat_layout(&labels.hours, "HOURS"), row, 2, 3, 1);
  };

  const char* distance_unit = Params().read_db_bool("IsMetric") ? "KM" : "MILES";
  QGridLayout* gl = new QGridLayout();
  gl->setMargin(0);
  gl->addWidget(new QLabel("ALL TIME"), 0, 0, 1, 3);
  add_stats_layouts(gl, all_, 1, distance_unit);
  gl->addWidget(new QLabel("PAST WEEK"), 6, 0, 1, 3);
  add_stats_layouts(gl, week_, 7, distance_unit);

  QVBoxLayout* vlayout = new QVBoxLayout(this);
  vlayout->addLayout(gl);

  if (std::string cached_stat = Params().get("DriveStats"); !cached_stat.empty()) {
    parseResponse(QString::fromStdString(cached_stat), false);
  }

  // TODO: do we really need to update this frequently?
  QString dongleId = QString::fromStdString(Params().get("DongleId"));
  QString url = "https://api.commadotai.com/v1.1/devices/" + dongleId + "/stats";
  RequestRepeater* repeater = new RequestRepeater(this, url, 13);
  QObject::connect(repeater, SIGNAL(receivedResponse(QString)), this, SLOT(parseResponse(QString)));
}
