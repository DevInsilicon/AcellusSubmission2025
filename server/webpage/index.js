const styles = `
  @keyframes pulsate {
    0% { opacity: 0.4; }
    50% { opacity: 1; }
    100% { opacity: 0.4; }
  }
  
  @keyframes trail {
    0% { transform: scale(1); opacity: 0.4; }
    100% { transform: scale(2); opacity: 0; }
  }
  
  .pulsating-dot {
    animation: pulsate 2s ease-in-out infinite;
  }

  .trail {
    animation: trail 2s ease-out infinite;
  }

  .trail-1 { animation-delay: 0s; }
  .trail-2 { animation-delay: 0.4s; }
  .trail-3 { animation-delay: 0.8s; }
`;

function App() {
    const deviceListRef = React.useRef(null);
    const [darkMode, setDarkMode] = React.useState(true);
    const [devices, setDevices] = React.useState([]);
    const [selectedDevice, setSelectedDevice] = React.useState(null);
    const [stats, setStats] = React.useState({
        totalDevices: 0,
        listeners: 0,
        suspicious: 0
    });

    const fetchData = async () => {
        try {
            const response = await fetch('/api/devices');
            const data = await response.json();
            const scrollPos = deviceListRef.current ? deviceListRef.current.scrollTop : 0;
            setDevices(data.devices);
            setStats(data.stats);
            requestAnimationFrame(() => {
                if (deviceListRef.current) {
                    deviceListRef.current.scrollTop = scrollPos;
                }
            });
            
            if (selectedDevice) {
                const updatedDevice = data.devices.find(d => d.mac === selectedDevice.mac);
                if (updatedDevice) setSelectedDevice(updatedDevice);
            }
        } catch (error) {
            console.error('Error fetching devices:', error);
        }
    };

    React.useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const updateDeviceStatus = async (deviceMac, newStatus) => {
        try {
            const response = await fetch(`/api/devices/${deviceMac}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });
            if (response.ok) {
                fetchData();
            }
        } catch (error) {
            console.error('Error updating device status:', error);
        }
    };

    const DeviceList = ({ deviceListRef }) => {
        const [editingDevice, setEditingDevice] = React.useState(null);
        const [newName, setNewName] = React.useState('');

        const handleRename = async (mac, newName) => {
            try {
                const response = await fetch(`/api/devices/${mac}/rename`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: newName })
                });
                if (response.ok) {
                    fetchData();
                    setEditingDevice(null);
                    setNewName('');
                }
            } catch (error) {
                console.error('Error renaming device:', error);
            }
        };

        const sortedDevices = [...devices].sort((a, b) => {
            const order = { suspicious: 0, unrecognised: 1, trusted: 2 };
            return order[a.status] - order[b.status];
        });

        return (
            <div ref={deviceListRef} className="flex flex-col gap-2 overflow-y-auto max-h-full">
                <div className="flex items-center bg-gray-900 p-3 rounded-lg sticky top-0">
                    <div className="w-3 h-3 mr-4"></div>
                    <div className="flex-1 grid grid-cols-5 gap-4 text-gray-400 text-sm font-semibold">
                        <span>Device Name</span>
                        <span>Category</span>
                        <span>Distance (m)</span>
                        <span>Signal (dBm)</span>
                        <span>Actions</span>
                    </div>
                </div>

                {sortedDevices.map(device => (
                    <div 
                        key={device.mac}
                        onClick={(e) => {
                            const scrollPos = deviceListRef.current ? deviceListRef.current.scrollTop : 0;
                            setSelectedDevice(device);
                            requestAnimationFrame(() => {
                                if (deviceListRef.current) {
                                    deviceListRef.current.scrollTop = scrollPos;
                                }
                            });
                        }}
                        className="flex items-center bg-gray-800 p-3 rounded-lg cursor-pointer hover:bg-gray-700"
                    >
                        <div className={`w-3 h-3 rounded-full mr-4 ${
                            device.status === 'trusted' ? 'bg-green-500' :
                            device.status === 'suspicious' ? 'bg-red-500' : 'bg-blue-500'
                        }`}></div>
                        <div className="flex-1 grid grid-cols-5 gap-4">
                            {editingDevice === device.mac ? (
                                <div className="flex items-center gap-2">
                                    <input
                                        type="text"
                                        value={newName}
                                        onChange={(e) => setNewName(e.target.value)}
                                        className="bg-gray-700 text-white px-2 py-1 rounded"
                                        placeholder={device.displayName}
                                    />
                                    <button
                                        onClick={() => handleRename(device.mac, newName)}
                                        className="bg-green-500 hover:bg-green-600 px-2 py-1 rounded"
                                    >
                                        Save
                                    </button>
                                    <button
                                        onClick={() => {
                                            setEditingDevice(null);
                                            setNewName('');
                                        }}
                                        className="bg-red-500 hover:bg-red-600 px-2 py-1 rounded"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            ) : (
                                <div className="flex items-center gap-2">
                                    <span>{device.displayName}</span>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setEditingDevice(device.mac);
                                            setNewName(device.displayName);
                                        }}
                                        className="text-gray-400 hover:text-white"
                                    >
                                        ✎
                                    </button>
                                </div>
                            )}
                            <span>{device.deviceType}</span>
                            <span>{device.distance}m</span>
                            <span>{device.signalStrength}dBm</span>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    updateDeviceStatus(device.mac, 
                                        device.status === 'trusted' ? 'unrecognised' : 'trusted'
                                    );
                                }}
                                className={`px-2 py-1 rounded ${
                                    device.status === 'trusted' 
                                    ? 'bg-red-500 hover:bg-red-600' 
                                    : 'bg-green-500 hover:bg-green-600'
                                }`}
                            >
                                {device.status === 'trusted' ? 'Untrust' : 'Trust'}
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        );
    };

    const DeviceDetails = () => (
        <div className="p-4">
            {selectedDevice ? (
                <div className="space-y-4">
                    <h2 className="text-xl font-bold">{selectedDevice.displayName}</h2>
                    <div className="grid grid-cols-2 gap-4">
                        <div>Status: <span className={
                            selectedDevice.status === 'trusted' ? 'text-green-500' :
                            selectedDevice.status === 'suspicious' ? 'text-red-500' : 'text-blue-500'
                        }>{selectedDevice.status}</span></div>
                        <div>Type: {selectedDevice.deviceType}</div>
                        <div>Distance: {selectedDevice.distance}m</div>
                        <div>Signal: {selectedDevice.signalStrength}dBm</div>
                        <div>First Seen: {new Date(parseInt(selectedDevice.firstSeen)).toLocaleString()}</div>
                        {Object.entries(selectedDevice.details).map(([key, value]) => (
                            <div key={key}>{key}: {value}</div>
                        ))}
                    </div>
                </div>
            ) : (
                <div className="text-gray-400 text-2xl">
                    Select a device to view details
                </div>
            )}
        </div>
    );

    React.useEffect(() => {
        if (darkMode) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
    }, [darkMode]);

    return (
        <div>
            <style>{styles}</style>
            <div className="bg-black min-h-screen flex">
                <div className="w-7/12 flex flex-col h-screen">
                    <div className="h-1/2 p-8">
                        <div className="bg-gray-700 p-6 rounded-lg h-full">
                            <DeviceDetails />
                        </div>
                    </div>
                    <div className="h-1/2 p-8">
                        <div className="bg-gray-700 p-6 rounded-lg h-full">
                            <DeviceList deviceListRef={deviceListRef} />
                        </div>
                    </div>
                </div>

                <div className="w-5/12 h-screen flex flex-col items-center p-[2vw]">
                    <div className="text-green-500 text-[3.5vw] font-bold mb-[4vh]">
                        AWAREID
                    </div>
                    
                    <div className="relative w-[20vw] h-[20vw] flex items-center justify-center mb-[4vh]">
                        <div className="absolute w-[10vw] h-[10vw] bg-green-500 rounded-full opacity-20 trail trail-1"></div>
                        <div className="absolute w-[10vw] h-[10vw] bg-green-500 rounded-full opacity-20 trail trail-2"></div>
                        <div className="absolute w-[10vw] h-[10vw] bg-green-500 rounded-full opacity-20 trail trail-3"></div>
                        <div className="relative w-[10vw] h-[10vw] bg-green-500 rounded-full pulsating-dot flex items-center justify-center">
                            <div className="text-white text-[1.5vw] font-bold">{stats.totalDevices}</div>
                        </div>
                    </div>

                    <div className="flex flex-col gap-[2vh] min-w-[20vw] items-center">
                        <div className="flex items-center w-full justify-center">
                            <div className="w-[0.8vw] h-[0.8vw] bg-green-500 rounded-full"></div>
                            <span className="text-green-500 text-[1.2vw] ml-[1vw]">{stats.listeners} Listeners Connected</span>
                        </div>
                        
                        <div className="flex items-center w-full justify-center translate-x-[2vw]">
                            <div className="w-[0.8vw] h-[0.8vw] bg-blue-500 rounded-full"></div>
                            <span className="text-blue-500 text-[1.2vw] ml-[1vw]">{stats.totalDevices} Devices Found</span>
                        </div>
                        
                        <div className="flex items-center w-full justify-center translate-x-[4vw]">
                            <div className="w-[0.8vw] h-[0.8vw] bg-red-500 rounded-full"></div>
                            <span className="text-red-500 text-[1.2vw] ml-[1vw]">{stats.suspicious} Suspicious</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

ReactDOM.render(<App />, document.getElementById('root'));
