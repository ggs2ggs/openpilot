#pragma once

#include <optional>

#include <QComboBox>
#include <QDialog>
#include <QLineEdit>
#include <QPushButton>
#include <QSpinBox>

#include "selfdrive/ui/qt/widgets/controls.h"

#include "tools/cabana/canmessages.h"
#include "tools/cabana/dbcmanager.h"

class SignalForm : public QWidget {
  Q_OBJECT

public:
  SignalForm(const Signal &sig, QWidget *parent);
  std::optional<Signal> getSignal();

  QLineEdit *name, *unit, *comment, *val_desc;
  QSpinBox *size, *msb, *lsb, *factor, *offset, *min_val, *max_val;
  QComboBox *sign, *endianness;
};

class SignalEdit : public QWidget {
  Q_OBJECT

public:
  SignalEdit(int index, const QString &id, const Signal &sig, const QString &color, QWidget *parent = nullptr);
  void save();

signals:
  void showChart(const QString &msg_id, const QString &sig_name);

protected:
  void remove();

  QString id;
  QString name_;
  QPushButton *plot_btn;
  ElidedLabel *title;
  SignalForm *form;
  QWidget *edit_container;
  QPushButton *remove_btn;
};

class AddSignalDialog : public QDialog {
  Q_OBJECT

public:
  AddSignalDialog(const QString &id, QWidget *parent);
};
