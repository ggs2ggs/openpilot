#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
ROOT="$(cd $DIR/../ && pwd)"

# NOTE: this is used in a docker build, so do not run any scripts here.

# Install packages present in all supported versions of Ubuntu
function install_ubuntu_common_requirements() {
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends \
    autoconf \
    build-essential \
    ca-certificates \
    clang \
    cmake \
    make \
    cppcheck \
    libtool \
    gcc-arm-none-eabi \
    bzip2 \
    liblzma-dev \
    libarchive-dev \
    libbz2-dev \
    capnproto \
    libcapnp-dev \
    curl \
    libcurl4-openssl-dev \
    git \
    git-lfs \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libeigen3-dev \
    libffi-dev \
    libglew-dev \
    libgles2-mesa-dev \
    libglfw3-dev \
    libglib2.0-0 \
    libomp-dev \
    libopencv-dev \
    libpng16-16 \
    libssl-dev \
    libsqlite3-dev \
    libusb-1.0-0-dev \
    libzmq3-dev \
    libsystemd-dev \
    locales \
    opencl-headers \
    ocl-icd-libopencl1 \
    ocl-icd-opencl-dev \
    clinfo \
    qml-module-qtquick2 \
    qtmultimedia5-dev \
    qtlocation5-dev \
    qtpositioning5-dev \
    libqt5sql5-sqlite \
    libqt5svg5-dev \
    libqt5x11extras5-dev \
    libreadline-dev \
    libdw1 \
    valgrind
}

# Install Ubuntu 22.04 packages
function install_ubuntu_2204_requirements() {
  install_ubuntu_common_requirements

  sudo apt-get install -y --no-install-recommends \
    python-dev-is-python3
}

# Install Ubuntu 21.10 packages
function install_ubuntu_2110_requirements() {
  install_ubuntu_common_requirements

  sudo apt-get install -y --no-install-recommends \
    python-dev \
    qtbase5-dev \
    qtchooser \
    qt5-qmake \
    qtbase5-dev-tools
}

# Install Ubuntu 20.04 packages
function install_ubuntu_lts_requirements() {
  install_ubuntu_common_requirements

  sudo apt-get install -y --no-install-recommends \
    python-dev \
    libavresample-dev \
    qt5-default
}

# Detect OS using /etc/os-release file
if [ -f "/etc/os-release" ]; then
  source /etc/os-release
  case "$ID $VERSION_ID" in
    "ubuntu 22.04")
      install_ubuntu_2204_requirements
      ;;
    "ubuntu 21.10")
      install_ubuntu_2110_requirements
      ;;
    "ubuntu 20.04")
      install_ubuntu_lts_requirements
      ;;
    *)
      echo "$ID $VERSION_ID is unsupported. This setup script is written for Ubuntu 20.04."
      read -p "Would you like to attempt installation anyway? " -n 1 -r
      echo ""
      if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
      fi
      install_ubuntu_lts_requirements
  esac
else
  echo "No /etc/os-release in the system"
  exit 1
fi


# install python dependencies
$ROOT/update_requirements.sh

source ~/.bashrc
if [ -z "$OPENPILOT_ENV" ]; then
  printf "\nsource %s/tools/openpilot_env.sh" "$ROOT" >> ~/.bashrc
  source ~/.bashrc
  echo "added openpilot_env to bashrc"
fi

echo
echo "----   OPENPILOT SETUP DONE   ----"
echo "Open a new shell or configure your active shell env by running:"
echo "source ~/.bashrc"
