const express = require("express");
const path = require("path");
const fs = require('fs');
const app = express();
app.use(express.json());

const STORAGE_FILE = path.join(__dirname, 'deviceHistory.json');
const deviceHistory = {
    firstSeen: new Map(),
    customNames: new Map()
};

try {
    if (fs.existsSync(STORAGE_FILE)) {
        const data = JSON.parse(fs.readFileSync(STORAGE_FILE, 'utf8'));
        deviceHistory.firstSeen = new Map(Object.entries(data.firstSeen || {}));
        deviceHistory.customNames = new Map(Object.entries(data.customNames || {}));
    }
} catch (error) {
    console.error('Error loading device history:', error);
}

const saveDeviceHistory = () => {
    try {
        const data = {
            firstSeen: Object.fromEntries(deviceHistory.firstSeen),
            customNames: Object.fromEntries(deviceHistory.customNames)
        };
        fs.writeFileSync(STORAGE_FILE, JSON.stringify(data, null, 2));
    } catch (error) {
        console.error('Error saving device history:', error);
    }
};

const cleanupDeviceHistory = () => {
    const OLD_DEVICE_THRESHOLD = 30 * 24 * 60 * 60 * 1000;
    const now = Date.now();
    
    for (const [mac, firstSeen] of deviceHistory.firstSeen) {
        if (now - parseInt(firstSeen) > OLD_DEVICE_THRESHOLD && !deviceHistory.customNames.has(mac)) {
            deviceHistory.firstSeen.delete(mac);
        }
    }
    saveDeviceHistory();
};

setInterval(cleanupDeviceHistory, 24 * 60 * 60 * 1000);

const devices = new Map();
const listeners = new Set();
let sessionStartTime = Date.now();

const VENDOR_MAPPINGS = {
    '00:03:93': 'Apple',
    '00:05:02': 'Apple',
    '00:0A:27': 'Apple',
    '00:0A:95': 'Apple',
    '00:1E:52': 'Apple',
    '00:22:41': 'Apple',
    '00:23:32': 'Apple',
    '00:25:00': 'Apple',
    '00:26:BB': 'Apple',
    '00:30:65': 'Apple',
    '00:50:E4': 'Apple',
    '00:56:CD': 'Apple',
    '00:61:71': 'Apple',
    '00:C6:10': 'Apple',
    '04:15:52': 'Apple',
    '04:26:65': 'Apple',
    '04:48:9A': 'Apple',
    '04:4B:ED': 'Apple',
    '04:52:F3': 'Apple',
    '04:54:53': 'Apple',
    '14:10:9F': 'Apple',
    '24:A0:74': 'Apple',
    '28:6A:BA': 'Apple',
    '34:C0:59': 'Apple',
    '38:F9:D3': 'Apple',
    '3C:07:54': 'Apple',
    '3C:E1:A1': 'Apple',
    '40:30:04': 'Apple',
    '40:B3:95': 'Apple',
    '44:00:10': 'Apple',
    '58:B0:35': 'Apple',
    '60:C5:47': 'Apple',
    '64:B0:A6': 'Apple',
    '70:3E:AC': 'Apple',
    '78:CA:39': 'Apple',
    '88:63:DF': 'Apple',
    '88:66:A5': 'Apple',
    '00:03:FF': 'Microsoft',
    '00:12:5A': 'Microsoft',
    '00:15:5D': 'Microsoft',
    '00:17:FA': 'Microsoft',
    '00:1D:D8': 'Microsoft',
    '00:22:48': 'Microsoft',
    '00:25:AE': 'Microsoft',
    '00:50:F2': 'Microsoft',
    '28:18:78': 'Microsoft',
    '3C:83:75': 'Microsoft',
    '48:86:E8': 'Microsoft',
    '50:1A:C5': 'Microsoft',
    '58:82:A8': 'Microsoft',
    '60:45:BD': 'Microsoft',
    '00:07:AB': 'Samsung',
    '00:12:47': 'Samsung',
    '00:15:99': 'Samsung',
    '00:17:C9': 'Samsung',
    '00:1C:43': 'Samsung',
    '00:1A:11': 'Google',
    '08:9E:08': 'Google',
    'A4:77:33': 'Google',
    'AC:C1:EE': 'OnePlus',
    '94:65:2D': 'OnePlus',
    '00:EC:0A': 'Xiaomi',
    '04:CF:8C': 'Xiaomi',
    '00:37:6D': 'Huawei',
    '00:E0:FC': 'Huawei',
    '04:BD:70': 'Huawei',
    '00:E0:4C': 'Realme',
    '48:EE:0C': 'Oppo',
    '4C:B1:6C': 'Oppo',
    '94:87:E0': 'Xiaomi',
};

const identifyVendor = (mac, deviceType = '') => {
    if (!mac) return 'Unknown';
    
    const prefix = mac.substring(0, 8).toUpperCase();
    const shortPrefix = mac.substring(0, 5).toUpperCase();
    
    const macVendor = VENDOR_MAPPINGS[prefix] || 
                     Object.entries(VENDOR_MAPPINGS).find(([key, _]) => key.startsWith(shortPrefix))?.[1];
    
    if (macVendor) return macVendor;

    const type = deviceType.toLowerCase();
    if (type.includes('iphone') || type.includes('ipad') || type.includes('macbook') || 
        type.includes('airpods') || type.includes('apple') || type.includes('imac')) {
        return 'Apple';
    }
    if (type.includes('windows') || type.includes('surface') || type.includes('xbox')) {
        return 'Microsoft';
    }
    if (type.includes('galaxy') || type.includes('samsung')) {
        return 'Samsung';
    }
    if (type.includes('pixel') || type.includes('google')) {
        return 'Google';
    }
    if (type.includes('oneplus')) {
        return 'OnePlus';
    }
    if (type.includes('xiaomi')) {
        return 'Xiaomi';
    }
    if (type.includes('huawei')) {
        return 'Huawei';
    }
    if (type.includes('oppo')) {
        return 'Oppo';
    }

    return 'Unknown';
};

const identifyDeviceType = (device) => {
    const vendor = identifyVendor(device.mac);
    const name = (device.displayName || '').toLowerCase();
    const services = device.details?.services || [];

    const getDefaultName = (type, model = '') => {
        return device.displayName || `${type}${model ? ' ' + model : ''}`;
    };

    if (vendor === 'Apple') {
        const model = name.match(/\b(iphone|ipad|macbook|airpods|watch|imac|mac mini|mac pro)\b/i)?.[1];
        if (model) {
            const modelInfo = name.match(/\b(1[1-4]|X|XS|XR|SE|pro|air|max)\b/i)?.[1] || '';
            switch(model.toLowerCase()) {
                case 'iphone': return getDefaultName('iPhone', modelInfo.toUpperCase());
                case 'ipad': return getDefaultName('iPad', modelInfo.toUpperCase());
                case 'macbook': return getDefaultName('MacBook', modelInfo);
                case 'airpods': return getDefaultName('AirPods', modelInfo);
                case 'watch': return getDefaultName('Apple Watch');
                case 'imac': return getDefaultName('iMac');
                case 'mac mini': return getDefaultName('Mac Mini');
                case 'mac pro': return getDefaultName('Mac Pro');
            }
        }

        if (services.includes('0x2A00')) return getDefaultName('AirPods');
        if (services.includes('0x180A')) return getDefaultName('Apple Watch');
        return getDefaultName('Apple Device');
    }

    if (vendor === 'Microsoft') {
        if (name.includes('surface')) return getDefaultName('Surface');
        if (name.includes('xbox')) return getDefaultName('Xbox');
        return getDefaultName('Windows Device');
    }

    if (vendor === 'Samsung') {
        if (name.includes('galaxy')) {
            const model = name.match(/\b(s[0-9]+|note|fold|flip|tab|ultra|plus)\b/i)?.[0];
            return getDefaultName('Samsung Galaxy', model ? model.toUpperCase() : '');
        }
        return getDefaultName('Samsung Device');
    }

    if (['Google', 'OnePlus', 'Xiaomi', 'Huawei', 'Realme', 'Oppo'].includes(vendor)) {
        return getDefaultName(`${vendor} Device`);
    }

    return 'Unknown Device';
};

const getAppleDeviceName = async (mac) => {
    try {
        const peripheral = await noble.connect(mac);
        const deviceName = await peripheral.readHandle(0x0003);
        await peripheral.disconnect();
        return deviceName.toString();
    } catch (error) {
        console.log(`Failed to get Apple device name: ${error.message}`);
        return null;
    }
};

const isSuspicious = (device) => {
    const suspiciousFactors = [
        device.previousMacs && device.previousMacs.length > 3,
        device.signalStrength > -30,
        device.displayName.toLowerCase().includes('hidden') || 
        device.displayName.toLowerCase().includes('unknown'),
        device.appearances > 10 && (Date.now() - device.firstSeen) < 300000,
        device.deviceType.toLowerCase().includes('restricted') ||
        device.deviceType.toLowerCase().includes('spoofed')
    ];

    return suspiciousFactors.filter(Boolean).length >= 2;
};

const customNames = new Map();

const processDevice = async (deviceData, listenerMac) => {
    const existingDevice = devices.get(deviceData.mac);
    const now = Date.now();
    
    const firstSeenDate = parseInt(deviceHistory.firstSeen.get(deviceData.mac)) || now;
    const storedCustomName = customNames.get(deviceData.mac) || deviceHistory.customNames.get(deviceData.mac);
    
    const initialVendor = identifyVendor(deviceData.mac);
    const deviceType = deviceData.type === 'Unknown' ? 
        identifyDeviceType({ 
            mac: deviceData.mac, 
            displayName: storedCustomName || deviceData.name,
            details: { ...deviceData, vendor: initialVendor }
        }) : 
        deviceData.type;
    
    const vendor = identifyVendor(deviceData.mac, deviceType);

    if (!deviceHistory.firstSeen.has(deviceData.mac)) {
        deviceHistory.firstSeen.set(deviceData.mac, now.toString());
        saveDeviceHistory();
    }

    if (vendor === 'Apple' && !deviceData.name) {
        const appleName = await getAppleDeviceName(deviceData.mac);
        if (appleName) {
            deviceData.name = appleName;
        }
    }

    if (existingDevice) {
        if (Math.abs(deviceData.signal) < Math.abs(existingDevice.signalStrength)) {
            existingDevice.signalStrength = deviceData.signal;
            existingDevice.nearestListener = listenerMac;
        }
        
        existingDevice.appearances++;
        existingDevice.lastSeen = now;
        
        if (deviceData.previousMac && !existingDevice.previousMacs.includes(deviceData.previousMac)) {
            existingDevice.previousMacs.push(deviceData.previousMac);
        }

        existingDevice.status = isSuspicious(existingDevice) ? 'suspicious' : 
                               existingDevice.status === 'trusted' ? 'trusted' : 'unrecognised';

        existingDevice.deviceType = deviceType;
        existingDevice.details.vendor = vendor;
        existingDevice.vendor = vendor;
        
        if (storedCustomName) {
            existingDevice.displayName = storedCustomName;
        }
        
        existingDevice.firstSeen = firstSeenDate;
        return existingDevice;
    }

    const newDevice = {
        id: Date.now(),
        mac: deviceData.mac,
        vendor: vendor,
        displayName: storedCustomName || deviceData.name || identifyDeviceType({ 
            mac: deviceData.mac, 
            displayName: deviceData.name,
            details: { ...deviceData, vendor }
        }),
        deviceType: deviceType,
        signalStrength: deviceData.signal,
        distance: Math.round(Math.pow(10, (-69 - deviceData.signal) / (10 * 2)) * 10) / 10,
        status: 'unrecognised',
        nearestListener: listenerMac,
        firstSeen: firstSeenDate,
        lastSeen: now,
        appearances: 1,
        previousMacs: deviceData.previousMac ? [deviceData.previousMac] : [],
        details: {
            vendor: vendor,
            mac: deviceData.mac,
            services: deviceData.services || []
        }
    };

    devices.set(deviceData.mac, newDevice);
    return newDevice;
};

app.post('/api/devices', express.json(), async (req, res) => {
    const { devices: reportedDevices, listenerMac } = req.body;

    if (!listenerMac || !Array.isArray(reportedDevices)) {
        return res.status(400).json({ error: 'Invalid request format' });
    }

    listeners.add(listenerMac);

    const processedDevices = await Promise.all(reportedDevices.map(device => 
        processDevice(device, listenerMac)
    ));

    const OLD_THRESHOLD = 300000;
    for (const [mac, device] of devices) {
        if (Date.now() - device.lastSeen > OLD_THRESHOLD) {
            devices.delete(mac);
        }
    }

    res.json({
        success: true,
        stats: {
            totalDevices: devices.size,
            listeners: listeners.size,
            suspicious: Array.from(devices.values()).filter(d => d.status === 'suspicious').length
        }
    });
});

app.post('/api/device', express.json(), async (req, res) => {
    const { device, listenerMac } = req.body;

    if (!listenerMac || !device || !device.mac) {
        return res.status(400).json({ error: 'Invalid device update format' });
    }

    listeners.add(listenerMac);

    const processedDevice = await processDevice(device, listenerMac);

    res.json({
        success: true,
        device: processedDevice,
        stats: {
            totalDevices: devices.size,
            listeners: listeners.size,
            suspicious: Array.from(devices.values()).filter(d => d.status === 'suspicious').length
        }
    });
});

app.post('/api/devices/:mac/status', express.json(), (req, res) => {
    const { mac } = req.params;
    const { status } = req.body;
    
    if (!devices.has(mac)) {
        return res.status(404).json({ error: 'Device not found' });
    }

    const device = devices.get(mac);
    device.status = status;
    
    res.json({ success: true, device });
});

app.post('/api/devices/:mac/rename', express.json(), (req, res) => {
    const { mac } = req.params;
    const { name } = req.body;
    
    if (!devices.has(mac)) {
        return res.status(404).json({ error: 'Device not found' });
    }

    if (!name || typeof name !== 'string') {
        return res.status(400).json({ error: 'Invalid name provided' });
    }

    deviceHistory.customNames.set(mac, name);
    saveDeviceHistory();
    
    const device = devices.get(mac);
    device.displayName = name;
    
    res.json({ success: true, device });
});

app.get('/api/devices', (req, res) => {
    const sortedDevices = Array.from(devices.values()).sort((a, b) => {
        const aHasName = a.displayName && a.displayName !== 'Unknown Device';
        const bHasName = b.displayName && b.displayName !== 'Unknown Device';
        
        if (aHasName && !bHasName) return -1;
        if (!aHasName && bHasName) return 1;

        if (a.deviceType === 'Unknown Device' && b.deviceType !== 'Unknown Device') return 1;
        if (a.deviceType !== 'Unknown Device' && b.deviceType === 'Unknown Device') return -1;
        
        const statusOrder = { suspicious: 0, unrecognised: 1, trusted: 2 };
        return statusOrder[a.status] - statusOrder[b.status];
    });

    res.json({
        devices: sortedDevices,
        stats: {
            totalDevices: devices.size,
            listeners: listeners.size,
            suspicious: sortedDevices.filter(d => d.status === 'suspicious').length
        }
    });
});

app.use('/webpage', express.static(path.join(__dirname, 'webpage')));

app.get('/', (req, res) => {
    res.redirect('/webpage/');
});

app.use((req, res, next) => {
    if (req.url === '/webpage/index.html') {
        return res.redirect('/webpage/');
    }
    next();
});

app.use((req, res, next) => {
    if (req.url.startsWith('/asset/')) {
        return res.redirect(req.url.replace('/asset/', '/webpage/'));
    }
    next();
});

app.listen(3000, () => console.log("Server listening on port 3000"));
