#include "selfdrive/boardd/usbdevice.h"

#include <map>
#include <memory>

#include "selfdrive/common/swaglog.h"

namespace {

libusb_context *init_usb_ctx() {
  libusb_context *context = nullptr;
  int err = libusb_init(&context);
  if (err != 0) {
    LOGE("libusb initialization error %d", err);
    return nullptr;
  }
#if LIBUSB_API_VERSION >= 0x01000106
  libusb_set_option(context, LIBUSB_OPTION_LOG_LEVEL, LIBUSB_LOG_LEVEL_INFO);
#else
  libusb_set_debug(context, 3);
#endif
  return context;
}

struct DeviceIterator {
  DeviceIterator(libusb_context *ctx) {
    ssize_t num_devices = libusb_get_device_list(ctx, &dev_list);
    for (ssize_t i = 0; i < num_devices; ++i) {
      libusb_device_descriptor desc = {};
      int ret = libusb_get_device_descriptor(dev_list[i], &desc);
      if (ret < 0 || desc.idVendor != USB_VID || desc.idProduct != USB_PID) continue;

      libusb_device_handle *handle = nullptr;
      if (libusb_open(dev_list[i], &handle) == 0) {
        unsigned char serial[256] = {'\0'};
        libusb_get_string_descriptor_ascii(handle, desc.iSerialNumber, serial, std::size(serial) - 1);
        devices[(const char *)serial] = dev_list[i];
        libusb_close(handle);
      }
    }
  }

  ~DeviceIterator() {
    if (dev_list) libusb_free_device_list(dev_list, 1);
  }

  std::map<std::string, libusb_device *>::iterator begin() { return devices.begin(); }
  std::map<std::string, libusb_device *>::iterator end() { return devices.end(); }
  std::map<std::string, libusb_device *> devices;
  libusb_device **dev_list = nullptr;
};

}  // namespace

bool USBDevice::open(const std::string &serial) {
  ctx = init_usb_ctx();
  if (!ctx) return false;

  for (const auto &[s, device] : DeviceIterator(ctx)) {
    if (serial.empty() || serial == s) {
      usb_serial = s;
      libusb_open(device, &dev_handle);
      break;
    }
  }
  if (!dev_handle) return false;

  if (libusb_kernel_driver_active(dev_handle, 0) == 1) {
    libusb_detach_kernel_driver(dev_handle, 0);
  }

  if (libusb_set_configuration(dev_handle, 1) != 0 ||
      libusb_claim_interface(dev_handle, 0) != 0) {
    return false;
  }

  return true;
}

USBDevice::~USBDevice() {
  if (dev_handle) {
    libusb_release_interface(dev_handle, 0);
    libusb_close(dev_handle);
  }
  if (ctx) libusb_exit(ctx);
}

std::vector<std::string> USBDevice::list() {
  std::vector<std::string> serials;
  if (libusb_context *ctx = init_usb_ctx()) {
    for (auto it : DeviceIterator(ctx)) {
      serials.push_back(it.first);
    }
    libusb_exit(ctx);
  }
  return serials;
}

int USBDevice::control_transfer(libusb_endpoint_direction dir, uint8_t bRequest, uint16_t wValue, uint16_t wIndex, uint8_t *data, uint16_t length, uint32_t timeout) {
  std::lock_guard lk(usb_lock);

  int ret = LIBUSB_ERROR_NO_DEVICE;
  const uint8_t bmRequestType = dir | LIBUSB_REQUEST_TYPE_VENDOR | LIBUSB_RECIPIENT_DEVICE;
  while (connected) {
    ret = libusb_control_transfer(dev_handle, bmRequestType, bRequest, wValue, wIndex, data, length, timeout);
    if (ret >= 0) break;

    handle_usb_issue(ret, __func__);
  }
  return ret;
}

int USBDevice::bulk_read(uint8_t endpoint, uint8_t *data, int length, uint32_t timeout) {
  std::lock_guard lk(usb_lock);

  int transferred = 0;
  while (connected) {
    int err = libusb_bulk_transfer(dev_handle, endpoint, data, length, &transferred, timeout);
    if (err == 0) break;

    if (err == LIBUSB_ERROR_TIMEOUT) {
      break;  // timeout is okay to exit, recv still happened
    } else if (err == LIBUSB_ERROR_OVERFLOW) {
      comms_healthy = false;
      LOGE_100("overflow got 0x%x", transferred);
    } else if (err != 0) {
      handle_usb_issue(err, __func__);
    }
  }
  return transferred;
}

int USBDevice::bulk_write(uint8_t endpoint, uint8_t *data, int length, uint32_t timeout) {
  std::lock_guard lk(usb_lock);

  int transferred = 0;
  while (connected) {
    int err = libusb_bulk_transfer(dev_handle, endpoint, data, length, &transferred, timeout);
    if (err == 0 && transferred == length) break;

    if (err == LIBUSB_ERROR_TIMEOUT) {
      LOGW("Transmit buffer full");
      break;
    } else if (err != 0 || length != transferred) {
      handle_usb_issue(err, __func__);
    }
  }
  return transferred;
}

void USBDevice::handle_usb_issue(int err, const char func[]) {
  LOGE_100("usb error %d \"%s\" in %s", err, libusb_strerror((enum libusb_error)err), func);
  if (err == LIBUSB_ERROR_NO_DEVICE) {
    LOGE("lost connection");
    connected = false;
  }
  // TODO: check other errors, is simply retrying okay?
}
