

Linux Setup
-----------
The following steps are required to use the CYW20735B1 evaluation kit as normal HCI device on Linux with BlueZ.
 

**1. Setup as HCI device**

You need to set the baud rate to 3 Mbit/s. Replace `/dev/ttyUSB0` with your device.

    btattach -B /dev/ttyUSB0 -S 3000000
    
If this does not work directly, use:

    stty -F /dev/ttyUSB0 3000000
    btattach -B /dev/ttyUSB0
    
Sometimes, you need to plug/unplug the evaluation board multiple times and run a combination of the commands above.
If setup was successful can be checked with `hciconfig`. A MAC address with all zeros indicates that the baud rate
was not set correctly and you need to try again.

**2. Use with BlueZ**

Assuming that you already have a regular Bluetooth device, you new device is `hci1`.

    hciconfig hci1 up

You can list your HCI devices:

    hcitool dev

**3. Command line tools for connections**

Scanning for devices:

    hcitool scan
    hcitool lescan

Connections and pairing:

    bluetoothctl

Enter into `bluetoothctl` command prompt:

    power on
    agent on
    default-agent
    scan on

Optional - accept connections:

    advertise on
    pairable on
    discoverable on

Do a pairing and then connect:

    pair aa:bb:cc:dd:ee:ff
    connect aa:bb:cc:dd:ee:ff



Diagnostics
-----------

On some devices, diagnostic logging for LMP and LCP already works out of the box.
Note that diagnostics can do more, but the additional features are currently not
integrated into *BlueZ* or the Linux kernel.

To enable diagnostics, execute:

    echo 1 > /sys/kernel/debug/bluetooth/hci0/vendor_diag
    
By default, this entry is only created for Intel and Broadcom chips.
The evaluation board claims to be Cypress, a different vendor ID, thus
the vendor diagnostics are missing.
*BlueZ* already comes with a monitor that decodes some parts of the diagnostic
traffic, simply run:

    btmon