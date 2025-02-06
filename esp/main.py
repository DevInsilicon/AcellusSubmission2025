import network
import ubluetooth
import ujson
import urequests
from machine import Timer
import time
from config import config

# Hardcoded settings
SERVER_IP = "192.168.1.238"
WIFI_SSID = "NonweuStudios-GAMING"
WIFI_PASS = "barreljudge765"

# Manufacturer IDs
APPLE_COMPANY_ID = 0x004C
MICROSOFT_COMPANY_ID = 0x0006
GOOGLE_COMPANY_ID = 0x00E0
SAMSUNG_COMPANY_ID = 0x0075

# Device type identification constants
DEVICE_TYPES = {
    # Apple devices
    "iPhone": ["iPhone", "i386", "x86_64"],
    "iPad": ["iPad"],
    "MacBook": ["MacBook", "Macmini", "iMac", "MacPro"],
    "AirPods": ["AirPods", "Beat"],
    "AppleWatch": ["Watch"],
    # Windows/Microsoft devices
    "Surface": ["Surface"],
    "Windows": ["DESKTOP-", "LAPTOP-", "PC-"],
    # Android devices
    "Android": [
        "SM-",
        "Pixel",
        "OnePlus",
        "HUAWEI",
        "Xiaomi",
        "OPPO",
        "vivo",
        "Galaxy",
    ],
    # Other devices
    "Smart Home": ["Echo", "Alexa", "Google Home", "Nest", "Hue"],
    "Gaming": ["Xbox", "PlayStation", "Nintendo", "PS5", "PS4"],
}


class BLEScanner:
    def __init__(self):
        self.ble = ubluetooth.BLE()
        self.ble.active(True)
        self.devices = {}
        self.scanning = False
        self.mac_address = ":".join(["%02X" % i for i in self.ble.config("mac")[1]])

    def parse_manufacturer_data(self, mfg_data):
        """Parse manufacturer specific data to identify device type and details."""
        if len(mfg_data) < 2:
            return None

        company_id = (mfg_data[1] << 8) | mfg_data[0]
        data = mfg_data[2:]

        if company_id == APPLE_COMPANY_ID:
            return self.parse_apple_data(data)
        elif company_id == MICROSOFT_COMPANY_ID:
            return self.parse_microsoft_data(data)
        elif company_id == GOOGLE_COMPANY_ID:
            return self.parse_google_data(data)
        elif company_id == SAMSUNG_COMPANY_ID:
            return self.parse_samsung_data(data)
        return None

    def parse_apple_data(self, data):
        """Parse Apple-specific manufacturer data."""
        device_info = {"manufacturer": "Apple"}

        if len(data) > 2:
            type_code = data[2]
            # Apple device type codes
            device_types = {
                0x02: "iPhone",
                0x04: "iPad",
                0x07: "MacBook",
                0x0A: "AirPods",
                0x0B: "Apple Watch",
                0x0C: "HomePod",
                0x0D: "Apple TV",
            }
            device_info["type"] = device_types.get(type_code, "Apple Device")

            # Try to extract model information
            if len(data) > 4:
                model_code = data[3]
                device_info["model"] = f"{device_info['type']} {model_code}"

        return device_info

    def parse_microsoft_data(self, data):
        """Parse Microsoft-specific manufacturer data."""
        device_info = {"manufacturer": "Microsoft"}

        if len(data) > 1:
            if data[0] == 0x01:
                device_info["type"] = "Surface"
            elif data[0] == 0x02:
                device_info["type"] = "Xbox"
            else:
                device_info["type"] = "Windows Device"

        return device_info

    def parse_google_data(self, data):
        """Parse Google-specific manufacturer data."""
        device_info = {"manufacturer": "Google"}

        if len(data) > 1:
            device_types = {
                0x01: "Pixel",
                0x02: "Nest",
                0x03: "Chromecast",
                0x04: "Google Home",
            }
            device_info["type"] = device_types.get(data[0], "Android Device")

        return device_info

    def parse_samsung_data(self, data):
        """Parse Samsung-specific manufacturer data."""
        device_info = {"manufacturer": "Samsung"}

        if len(data) > 1:
            if data[0] == 0x01:
                device_info["type"] = "Galaxy Phone"
            elif data[0] == 0x02:
                device_info["type"] = "Galaxy Tablet"
            elif data[0] == 0x03:
                device_info["type"] = "Galaxy Watch"
            elif data[0] == 0x04:
                device_info["type"] = "Galaxy Buds"
            else:
                device_info["type"] = "Samsung Device"

        return device_info

    def extract_device_name(self, name):
        """Extract owner name and device type from advertised name."""
        if not name:
            return None, None

        # Common patterns for device names
        owner = None
        device_type = None

        # Check for possessive names (e.g., "Jack's iPhone")
        if "'" in name or "'s" in name:
            parts = name.replace("'s", "'").split("'")
            if len(parts) >= 2:
                owner = parts[0].strip()
                device_type = parts[1].strip()
        else:
            # Try to identify if it's a specific device type
            for known_type, patterns in DEVICE_TYPES.items():
                if any(pattern.lower() in name.lower() for pattern in patterns):
                    device_type = known_type
                    break

        return owner, device_type

    def identify_device_type(self, name, mfg_info=None):
        """Identify device type from name and manufacturer info."""
        if mfg_info and "type" in mfg_info:
            return mfg_info["type"]

        owner, device_type = self.extract_device_name(name)
        if device_type:
            return device_type

        # Check for common name patterns
        name_lower = name.lower() if name else ""
        if name_lower:
            if "iphone" in name_lower:
                return "iPhone"
            elif "ipad" in name_lower:
                return "iPad"
            elif "macbook" in name_lower:
                return "MacBook"
            elif "pixel" in name_lower:
                return "Android (Pixel)"
            elif "galaxy" in name_lower:
                return "Android (Samsung)"
            elif any(brand.lower() in name_lower for brand in DEVICE_TYPES["Android"]):
                return "Android Device"

        return "Unknown"

    def scan_callback(self, event, data):
        if event == 5:  # _IRQ_SCAN_RESULT
            addr_type, addr, adv_type, rssi, adv_data = data
            addr = ":".join(["%02X" % i for i in addr])

            # Initialize device info
            device_info = {
                "mac": addr,
                "name": "Unknown Device",
                "type": "Unknown",
                "signal": rssi,
                "manufacturer": "Unknown",
                "model": "Unknown",
                "owner": None,
            }

            # Parse advertisement data
            i = 0
            try:
                while i < len(adv_data):
                    length = adv_data[i]
                    if length == 0:
                        break

                    type_id = adv_data[i + 1]
                    data_slice = adv_data[i + 2 : i + length + 1]

                    if type_id == 0x09:  # Complete Local Name
                        try:
                            name = bytes(data_slice).decode()
                            device_info["name"] = name
                            owner, _ = self.extract_device_name(name)
                            if owner:
                                device_info["owner"] = owner
                        except:
                            pass

                    elif type_id == 0xFF:  # Manufacturer Specific Data
                        mfg_info = self.parse_manufacturer_data(data_slice)
                        if mfg_info:
                            device_info.update(mfg_info)

                    elif type_id == 0x0A:  # Tx Power Level
                        try:
                            # MicroPython compatible way to convert bytes to signed int
                            value = int.from_bytes(bytes(data_slice), 'big')
                            # Convert to signed if necessary
                            if value > 127:
                                value -= 256
                            device_info["tx_power"] = value
                        except:
                            pass

                    i += length + 1

            except Exception as e:
                print(f"Error parsing advertisement data: {str(e)}")

            # Set final device type based on all collected information
            device_info["type"] = self.identify_device_type(
                device_info["name"],
                device_info if device_info["manufacturer"] != "Unknown" else None
            )

            # Update device info in devices dictionary
            self.devices[addr] = device_info

    def start_scan(self):
        if not self.scanning:
            self.devices.clear()
            self.ble.irq(self.scan_callback)
            # Scan for longer (5 seconds) to catch more advertisement packets
            self.ble.gap_scan(5000, 30000, 30000)
            self.scanning = True

    def is_scanning(self):
        return self.scanning

    def get_devices(self):
        return list(self.devices.values())

    def gatherDeviceDetails(self):
        """
        Attempt to connect to each device and gather additional information.
        Logs connection attempts and merges info with the existing device dictionary.
        """
        for mac, dev in self.devices.items():
            if not dev.get("detailedInfoObtained"):
                print(f"Attempting connection to {mac}...")
                try:
                    # NOTE: The actual connection method depends on MicroPython / hardware.
                    # For many boards, ble.gap_connect(address_type, address) is not supported.
                    # Pseudocode for demonstration:
                    # self.ble.gap_connect(0, self._mac_string_to_bytes(mac))
                    # Wait or handle connection in callback, then gather info:
                    extra_info = {"battery": "Unknown", "alias": dev["name"]}  # Example
                    dev.update(extra_info)
                    dev["detailedInfoObtained"] = True
                    print(f"Connected to {mac}, retrieved info: {extra_info}")
                    # self.ble.gap_disconnect(self._mac_string_to_bytes(mac))
                except Exception as e:
                    print(f"Error connecting to {mac}: {e}")

    # Optional helper if micropython supports gap_connect addresses in bytes
    def _mac_string_to_bytes(self, mac_str):
        return bytes(int(b, 16) for b in mac_str.split(":"))


def connect_wifi():
    # Try hardcoded credentials first
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        try:
            wlan.connect(WIFI_SSID, WIFI_PASS)
            for _ in range(10):
                if wlan.isconnected():
                    print("Connected to hardcoded network")
                    return True
                time.sleep(1)
        except:
            print("Failed to connect with hardcoded credentials")

        # Fallback to wifi.txt
        ssid, password = config.getWifiCreds()
        if ssid and password:
            try:
                wlan.connect(ssid, password)
                for _ in range(10):
                    if wlan.isconnected():
                        print("Connected using wifi.txt")
                        return True
                    time.sleep(1)
            except:
                print("Failed to connect with wifi.txt")
    return wlan.isconnected()


def report_to_server(scanner):
    if not scanner.is_scanning():
        scanner.start_scan()
        time.sleep(5.1)  # Wait for enhanced scan to complete

        devices = scanner.get_devices()
        if devices:
            try:
                response = urequests.post(
                    f"http://{SERVER_IP}:3000/api/devices",
                    headers={"Content-Type": "application/json"},
                    data=ujson.dumps(
                        {"listenerMac": scanner.mac_address, "devices": devices}
                    ),
                )
                print(
                    f"Reported {len(devices)} devices. Status: {response.status_code}"
                )
                response.close()
            except Exception as e:
                print("Error reporting to server:", e)


def report_single_device(scanner, device_mac):
    """Report or update a single device's information."""
    if not scanner.is_scanning():
        scanner.start_scan()
        time.sleep(2.1)  # Shorter scan time for single device
        
        devices = scanner.get_devices()
        device = next((d for d in devices if d['mac'] == device_mac), None)
        
        if device:
            try:
                response = urequests.post(
                    f"http://{SERVER_IP}:3000/api/device",
                    headers={"Content-Type": "application/json"},
                    data=ujson.dumps({
                        "listenerMac": scanner.mac_address,
                        "device": device
                    })
                )
                print(f"Updated device {device_mac}. Status: {response.status_code}")
                response.close()
                return True
            except Exception as e:
                print("Error reporting single device:", e)
                return False
    return False


def main():
    if not connect_wifi():
        print("Failed to connect to WiFi")
        return

    scanner = BLEScanner()
    print(f"Scanner MAC: {scanner.mac_address}")

    while True:
        report_to_server(scanner)
        # Gather extra details after scanning
        scanner.gatherDeviceDetails()
        time.sleep(1.5)  # Wait before next scan


if __name__ == "__main__":
    main()
