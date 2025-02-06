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
