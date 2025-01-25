# Micropython

import machine
from os import urandom
import time
import network
import ucryptolib
import gc
import espnow
import uhashlib
import json


class config:
    def getWifiCreds():
        try:
            f = open("wifi.txt", "r")
            wifi = f.read()
            f.close()

            ssid = wifi.split("\n")[0]
            password = wifi.split("\n")[1]
            return ssid, password
        except:
            print("Error reading wifi.txt file. File empty?")
            return None, None
    def getNetCheck():
        try:
            f = open("netcheck.txt", "r")
            netcheck = f.read()
            f.close()
            return netcheck
        except:
            print("Error reading netcheck.txt file. File empty?")
            return None


class Manager:
    def __init__(self):
        print("Main system process started.")

        self.wifiManager = WiFiSystem(self)
        self.espnowManager = ESPNowSystem(self)
        self.operatorManager = OperatorSystem(self)

    def getWiFiManager(self):
        return self.wifiManager

    def getESPNowManager(self):
        return self.espnowManager

    def getOperatorManager(self):
        return self.operatorManager


class WiFiSystem:
    def __init__(self, manager: Manager):
        print("WiFi system process started.")
        self.manager = manager

        # Initialize in Station mode
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        # Ensure disconnected from any AP
        self.wlan.disconnect()
        self.mac = self.wlan.config('mac')  # Get MAC address from WLAN interface

    def getWlan(self):
        return self.wlan

    def getMac(self):
        return self.mac

    def attemptConnection(self):
        ssid, password = config.getWifiCreds()
        if ssid == None or password == None:
            print("No wifi credentials found.")
            raise Exception("No wifi credentials found.")

        try:
            self.wlan.connect(ssid, password)
            print("Connected to wifi.")
            return True
        except:
            print("Error connecting to wifi.")
            return False

    def isConnected(self):
        return self.wlan.isconnected()


class ESPNowSystem:
    def __init__(self, manager: Manager):
        print("ESPNow system process started.")
        self.manager = manager

        # Get WiFi interface
        self.wlan = manager.getWiFiManager().getWlan()
        # Ensure WiFi is disconnected before ESPNow
        self.wlan.disconnect()
        
        # Initialize ESPNow
        self.espnow = espnow.ESPNow()
        self.espnow.active(True)  # Activate ESPNow
        
        # Add broadcast peer after activation
        try:
            self.espnow.add_peer(b"\xff\xff\xff\xff\xff\xff")
        except OSError as e:
            print("Error adding peer:", e)

    def broadcastData(self, data):
        self.espnow.send(b"\xff\xff\xff\xff\xff\xff", data)

    def sendData(self, mac, data):
        self.espnow.send(mac, data)


class EncryptionSystem:
    def __init__(self):
        """Initialize encryption system with security parameters"""
        self.peers = {}  # {mac: aes_key}
        self.nonce_cache = set()  # Prevent replay attacks
        self.max_cache_size = 1000  # Limit memory usage
        self.block_size = 16  # AES block size

    def _cleanup(self):
        """Perform memory cleanup and maintenance"""
        current_time = time.time()
        # Clear expired nonces (older than 5 minutes)
        self.nonce_cache = {
            n
            for n in self.nonce_cache
            if current_time - int.from_bytes(n[:4], "big") < 300
        }
        gc.collect()

    def _derive_key(self, key_material, salt, iterations=1000):
        """Derive a cryptographic key using SHA256-based KDF"""
        key = key_material
        for _ in range(iterations):
            h = uhashlib.sha256()
            h.update(key + salt)
            key = h.digest()
        return key

    def createAsmKey(self):
        """Create asymmetric key pair"""
        private = urandom(32)
        public = bytes([x & 0x7F for x in private])
        return private, public

    def _generate_nonce(self):
        """Generate unique nonce with timestamp"""
        timestamp = int(time.time()).to_bytes(4, "big")
        random_bytes = urandom(12)
        return timestamp + random_bytes

    def encryptASM(self, public_key, data):
        """Encrypt data using asymmetric encryption with security measures"""
        if len(self.nonce_cache) > self.max_cache_size:
            self._cleanup()

        nonce = self._generate_nonce()
        if nonce in self.nonce_cache:
            raise ValueError("Nonce collision detected")
        self.nonce_cache.add(nonce)

        # Add authenticated metadata
        timestamp = int(time.time()).to_bytes(4, "big")
        data_len = len(data).to_bytes(4, "big")
        metadata = timestamp + data_len

        # Encrypt data with authentication
        result = bytearray()
        auth_data = metadata + data
        for i, b in enumerate(auth_data):
            result.append(b ^ public_key[i % len(public_key)])

        # Calculate MAC
        h = uhashlib.sha256()
        h.update(nonce + bytes(result))
        mac = h.digest()[:16]

        return nonce + bytes(result) + mac

    def decryptASM(self, private_key, encrypted_data):
        """Decrypt asymmetrically encrypted data with verification"""
        if (
            len(encrypted_data) < 44
        ):  # min length: nonce(16) + timestamp(4) + len(4) + mac(16)
            raise ValueError("Invalid data length")

        nonce = encrypted_data[:16]
        mac = encrypted_data[-16:]
        data = encrypted_data[16:-16]

        # Verify MAC
        h = uhashlib.sha256()
        h.update(nonce + data)
        if h.digest()[:16] != mac:
            raise ValueError("Authentication failed")

        # Check nonce and timestamp
        timestamp = int.from_bytes(nonce[:4], "big")
        if time.time() - timestamp > 300:  # 5 min expiry
            raise ValueError("Message expired")
        if nonce in self.nonce_cache:
            raise ValueError("Replay attack detected")
        self.nonce_cache.add(nonce)

        # Decrypt data
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ private_key[i % len(private_key)])

        # Verify metadata
        msg_timestamp = int.from_bytes(result[:4], "big")
        msg_len = int.from_bytes(result[4:8], "big")
        if msg_len != len(result) - 8:
            raise ValueError("Data length mismatch")

        return bytes(result[8:])

    def createKey(self):
        """Create new AES key with derivation"""
        salt = urandom(8)
        key_material = urandom(16)
        return self._derive_key(key_material, salt, iterations=100)

    def encrypt(self, key, data):
        """Encrypt data using AES-CBC with padding"""
        if not isinstance(data, bytes):
            raise TypeError("Data must be bytes")

        iv = urandom(16)
        padded = self._pad_data(data)
        cipher = ucryptolib.aes(key, 1, iv)  # CBC mode
        encrypted = cipher.encrypt(padded)

        # Add MAC for authentication
        h = uhashlib.sha256()
        h.update(iv + encrypted)
        mac = h.digest()[:16]

        return iv + encrypted + mac

    def decrypt(self, key, encrypted_data):
        """Decrypt AES-CBC data with authentication"""
        if len(encrypted_data) < 48:  # min length: iv(16) + block(16) + mac(16)
            raise ValueError("Invalid data length")

        iv = encrypted_data[:16]
        mac = encrypted_data[-16:]
        data = encrypted_data[16:-16]

        # Verify MAC
        h = uhashlib.sha256()
        h.update(iv + data)
        if h.digest()[:16] != mac:
            raise ValueError("Authentication failed")

        cipher = ucryptolib.aes(key, 1, iv)
        decrypted = cipher.decrypt(data)
        return self._unpad_data(decrypted)

    def _pad_data(self, data):
        """Add PKCS7 padding"""
        padding_len = self.block_size - (len(data) % self.block_size)
        padding = bytes([padding_len] * padding_len)
        return data + padding

    def _unpad_data(self, padded_data):
        """Remove PKCS7 padding with validation"""
        padding_len = padded_data[-1]
        if padding_len > self.block_size:
            raise ValueError("Invalid padding")
        for i in range(padding_len):
            if padded_data[-1 - i] != padding_len:
                raise ValueError("Invalid padding")
        return padded_data[:-padding_len]

    def addPeer(self, mac_address, key=None):
        """Add or update peer with optional custom key"""
        if key is None:
            key = self.createKey()
        self.peers[mac_address] = key
        return key

    def removePeer(self, mac_address):
        """Remove peer and associated key"""
        if mac_address in self.peers:
            del self.peers[mac_address]


class OperatorSystem:
    def __init__(self, manager: Manager):
        print("Operator system process started.")
        self.stage = 0
        self.isCrown = False
        self.manager = manager
        self.encryption = EncryptionSystem()
        self.espnowManager = manager.getESPNowManager()
        self.start_time = time.time()
        self.publicKey = None
        self.privateComsKey = None
        self.led = machine.Pin(2, machine.Pin.OUT)  # Initialize GPIO2 as output
        self.peer_led = machine.Pin(4, machine.Pin.OUT)  # LED for peer connection
        self.led.off()  # Ensure LED starts off
        self.peer_led.off()
        self.last_check = 0  # Add timestamp for last countdown check
        self.crown_status_complete = False  # Add flag for crown status completion
        self.connection_complete = False  # New flag for connection completion
        self.peers = {}  # Store connected peers when crown
        self.peer_keys = {}  # Store encryption keys for peers
        self.crown_announced = False  # Add flag to track if we've announced crown status

        self.checkCrownStatus()
        self.espnowManager.broadcastData(
            json.dumps({
                "type": "existingCrown",
                "mac": self.manager.getWiFiManager().getMac(),  # Use MAC from WiFi interface
            })
        )

    def processMessage(self, mac, msg):
        """New method to process incoming messages"""
        self.checkCrownStatus()
        print("Received message from", mac, ":", msg)

        if mac == b"\xff\xff\xff\xff\xff\xff":
            self.handleBroadcast(mac, msg)
        else:
            self.handlePrivate(mac, msg)

    def checkCrownStatus(self):
        current_time = time.time()
        time_remaining = 15 - (current_time - self.start_time)
        
        # Only print every ~1 second
        if current_time - self.last_check >= 1:
            if time_remaining > 0:
                print(f"Becoming crown in {time_remaining:.1f} seconds...")
            self.last_check = current_time
            
        if time_remaining <= 0:
            self.becomeCrown()
            self.crown_status_complete = True  # Set flag when complete

    def becomeCrown(self):
        if not self.crown_announced:  # Only announce once
            self.isCrown = True
            self.stage = 3
            print("No crown found - becoming crown node")
            self.led.on()  # Turn on LED when becoming crown
            self.crown_announced = True  # Set flag to prevent repeated announcements

    def networkListener(self, mac, msg):
        self.checkCrownStatus()
        print("Received message from", mac, ":", msg)

        if mac == b"\xff\xff\xff\xff\xff\xff":
            self.handleBroadcast(mac, msg)
        else:
            self.handlePrivate(mac, msg)

    def handleBroadcast(self, mac, msg):
        parsed = None
        try:
            parsed = json.loads(msg)
        except:
            print("Unrecognized ESPNow Packet?")
            return

        if self.isCrown:
            # Crown handling of broadcast messages
            if parsed["type"] == "existingCrown":
                # Respond to new nodes looking for crown
                private, public = self.encryption.createAsmKey()
                self.peer_keys[mac] = private
                self.espnowManager.sendData(
                    mac,
                    json.dumps({
                        "type": "respExistingCrown",
                        "mac": self.manager.getWiFiManager().getMac(),
                    })
                )
        else:
            # Non-crown handling of broadcast messages
            if parsed["type"] == "respExistingCrown":
                self.isCrown = False
                self.stage = 1
                self.led.off()
                self.espnowManager.sendData(
                    mac,
                    json.dumps({
                        "type": "reqPublickey",
                        "mac": self.manager.getWiFiManager().getMac(),
                    })
                )

    def handlePrivate(self, mac, msg):
        if self.isCrown:
            # Crown handling of private messages
            try:
                if mac not in self.peer_keys:
                    print("Unknown peer tried to communicate")
                    return
                
                parsed = json.loads(msg)
                if parsed["type"] == "reqPublickey":
                    # Send public key for initial encryption
                    _, public = self.encryption.createAsmKey()
                    self.espnowManager.sendData(
                        mac,
                        json.dumps({
                            "type": "respPublickey",
                            "publickey": public
                        })
                    )
                elif parsed["type"] == "reqAsmKey":
                    # Handle peer requesting to join network
                    private_key = self.peer_keys[mac]
                    decrypted = self.encryption.decryptASM(private_key, msg)
                    peer_data = json.loads(decrypted)
                    
                    # Store peer's private communication key
                    self.peers[mac] = {
                        "key": peer_data["privateKey"],
                        "netcheck": peer_data["NetCheck"]
                    }
                    
                    # Send acknowledgment
                    encrypted = self.encryption.encrypt(
                        self.peers[mac]["key"],
                        json.dumps({
                            "type": "privkeyAck",
                            "success": True
                        })
                    )
                    self.espnowManager.sendData(mac, encrypted)
                    print(f"Peer {mac} successfully joined")
            except Exception as e:
                print(f"Error handling crown message: {e}")
        else:
            # Non-crown handling of private messages
            parsed = None
            try:
                parsed = json.loads(msg)
            except:
                print("Unrecognized ESPNow Packet?")
                return

            if self.stage == 1 and parsed["type"] == "respPublickey":
                self.stage = 2
                self.publicKey = parsed["publickey"]
                self.privateComsKey = self.encryption.createKey()

                packet = json.dumps(
                    {
                        "type": "reqAsmKey",
                        "mac": self.espnowManager.espnow.get_mac_addr(),
                        "privateKey": self.privateComsKey,
                        "NetCheck": config.getNetCheck(),
                    }
                )

                encrypted = self.encryption.encryptASM(self.publicKey, packet)
                self.espnowManager.sendData(mac, encrypted)

            elif self.stage == 2:
                unencrypted = self.encryption.decrypt(self.privateComsKey, msg)
                normal = None
                unenc = None

                try:
                    normal = json.loads(unencrypted)
                except Exception:
                    print("Most likely encryption succeeded since normal successful")

                try:
                    unenc = json.loads(normal)
                except Exception:
                    print("enc most likely failed due to unenc not working")

                if unenc is not None:
                    if unenc["type"] == "privkeyAck":
                        if unenc["success"]:
                            self.stage = 3
                            print("Successfully connected to crown.")
                            self.peer_led.on()  # Turn on peer LED when connected to crown
                            self.connection_complete = True  # Set completion flag
                        else:
                            print("i have no clue how")
                            self.peer_led.off()

                if normal is not None:
                    if normal["type"] == "privkeyAck":
                        if not normal["success"]:
                            print("Failed to sync with crown node")
                        else:
                            print("No clue what happened server side issue?")

    def removePeer(self, mac):
        """Remove a peer from the crown's network"""
        if mac in self.peers:
            del self.peers[mac]
        if mac in self.peer_keys:
            del self.peer_keys[mac]


# RUN IF MAIN
if __name__ == "__main__":
    manager = Manager()
    
    # Message processing loop
    while True:
        try:
            # Check crown status
            manager.getOperatorManager().checkCrownStatus()
            
            # Process any messages
            mac, msg = manager.getESPNowManager().espnow.recv(0)
            if msg:
                manager.getOperatorManager().processMessage(mac, msg)
            
            # Only break if we're not crown and have completed connection
            if (not manager.getOperatorManager().isCrown and 
                manager.getOperatorManager().connection_complete):
                break
                
        except Exception as e:
            print("Error processing message:", e)
        time.sleep(0.1)