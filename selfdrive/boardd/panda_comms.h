#pragma once

#include <mutex>
#include <atomic>
#include <cstdint>
#include <vector>

#include <linux/spi/spidev.h>

#include <libusb-1.0/libusb.h>


#define TIMEOUT 0
#define SPI_BUF_SIZE 1024

const bool PANDA_NO_RETRY = getenv("PANDA_NO_RETRY");


// comms base class
class PandaCommsHandle {
public:
  PandaCommsHandle(std::string serial) {};
  virtual ~PandaCommsHandle() {};
  virtual void cleanup() = 0;

  std::atomic<bool> connected = true;
  std::atomic<bool> comms_healthy = true;
  static std::vector<std::string> list();

  // HW communication
  virtual int control_write(uint8_t request, uint16_t param1, uint16_t param2, unsigned int timeout=TIMEOUT) = 0;
  virtual int control_read(uint8_t request, uint16_t param1, uint16_t param2, unsigned char *data, uint16_t length, unsigned int timeout=TIMEOUT) = 0;
  virtual int bulk_write(unsigned char endpoint, unsigned char* data, int length, unsigned int timeout=TIMEOUT) = 0;
  virtual int bulk_read(unsigned char endpoint, unsigned char* data, int length, unsigned int timeout=TIMEOUT) = 0;

protected:
  std::mutex hw_lock;
};

class PandaUsbHandle : public PandaCommsHandle {
public:
  PandaUsbHandle(std::string serial);
  ~PandaUsbHandle();
  int control_write(uint8_t request, uint16_t param1, uint16_t param2, unsigned int timeout=TIMEOUT);
  int control_read(uint8_t request, uint16_t param1, uint16_t param2, unsigned char *data, uint16_t length, unsigned int timeout=TIMEOUT);
  int bulk_write(unsigned char endpoint, unsigned char* data, int length, unsigned int timeout=TIMEOUT);
  int bulk_read(unsigned char endpoint, unsigned char* data, int length, unsigned int timeout=TIMEOUT);
  void cleanup();

  static std::vector<std::string> list();

private:
  libusb_context *ctx = NULL;
  libusb_device_handle *dev_handle = NULL;
  std::vector<uint8_t> recv_buf;
  void handle_usb_issue(int err, const char func[]);
};

class PandaSpiHandle : public PandaCommsHandle {
public:
  PandaSpiHandle(std::string serial);
  ~PandaSpiHandle();
  int control_write(uint8_t request, uint16_t param1, uint16_t param2, unsigned int timeout=TIMEOUT);
  int control_read(uint8_t request, uint16_t param1, uint16_t param2, unsigned char *data, uint16_t length, unsigned int timeout=TIMEOUT);
  int bulk_write(unsigned char endpoint, unsigned char* data, int length, unsigned int timeout=TIMEOUT);
  int bulk_read(unsigned char endpoint, unsigned char* data, int length, unsigned int timeout=TIMEOUT);
  void cleanup();

  static std::vector<std::string> list();

private:
  int spi_fd = -1;
  uint8_t tx_buf[SPI_BUF_SIZE];
  uint8_t rx_buf[SPI_BUF_SIZE];

  int wait_for_ack(spi_ioc_transfer &transfer, uint8_t ack);
  int spi_transfer(uint8_t endpoint, uint8_t *tx_data, uint16_t tx_len, uint8_t *rx_data, uint16_t max_rx_len);
  int spi_transfer_retry(uint8_t endpoint, uint8_t *tx_data, uint16_t tx_len, uint8_t *rx_data, uint16_t max_rx_len);
};
