#include "selfdrive/ui/qt/util.h"

#include <QDateTime>
#include <QDebug>
#include <QLayout>
#include <QLayoutItem>
#include <QMouseEvent>
#include <QPainter>
#include <QStyleOption>

void configFont(QPainter &p, const QString &family, int size, const QString &style) {
  QFont f(family);
  f.setPixelSize(size);
  f.setStyleName(style);
  p.setFont(f);
}

void clearLayout(QLayout* layout) {
  while (QLayoutItem* item = layout->takeAt(0)) {
    if (QWidget* widget = item->widget()) {
      widget->deleteLater();
    }
    if (QLayout* childLayout = item->layout()) {
      clearLayout(childLayout);
    }
    delete item;
  }
}

QString timeAgo(const QDateTime &date) {
  int diff = date.secsTo(QDateTime::currentDateTimeUtc());

  QString s;
  if (diff < 60) {
    s = "now";
  } else if (diff < 60 * 60) {
    int minutes = diff / 60;
    s = QString("%1 minute%2 ago").arg(minutes).arg(minutes > 1 ? "s" : "");
  } else if (diff < 60 * 60 * 24) {
    int hours = diff / (60 * 60);
    s = QString("%1 hour%2 ago").arg(hours).arg(hours > 1 ? "s" : "");
  } else if (diff < 3600 * 24 * 7) {
    int days = diff / (60 * 60 * 24);
    s = QString("%1 day%2 ago").arg(days).arg(days > 1 ? "s" : "");
  } else {
    s = date.date().toString();
  }

  return s;
}


ClickableWidget::ClickableWidget(QWidget *parent) : QWidget(parent) { }

void ClickableWidget::mouseReleaseEvent(QMouseEvent *event) {
  emit clicked();
}


// Fix stylesheets
void ClickableWidget::paintEvent(QPaintEvent *)  {
    QStyleOption opt;
    opt.init(this);
    QPainter p(this);
    style()->drawPrimitive(QStyle::PE_Widget, &opt, &p, this);
}
