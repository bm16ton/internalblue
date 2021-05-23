#!/usr/bin/python2

# Jiska Classen, Secure Mobile Networking Lab

import sys
from argparse import Namespace
from datetime import datetime

import numpy as np
from pwnlib.asm import asm

import internalblue.hci as hci
from internalblue.cli import InternalBlueCLI
from internalblue.ioscore import iOSCore

"""
Measure the RNG of the iPhone 7.
Similar to matedealer's thesis, p. 51.

Changes:

* Every 5th byte is now 0x42 to ensure that no other process wrote
  into this memory region in the meantime. Does it job and cheaper
  than checksums.

* When we are done, we send an HCI event containing 'RAND'. We catch
  this with a callback. Way more efficient than polling.

* We overwrite the original `rbg_rand` function with `bx lr` to
  ensure we're the only ones accessing the RNG.
  
* !!! Wi-Fi must be disabled by hand.

"""

# hd --len 0x1100 0x20f200
# hd --len 0x1000 0x222000
# hd --len 0x3000 0x229000
ASM_LOCATION_RNG = 0x229000  # load our snippet here
MEM_RNG = ASM_LOCATION_RNG + 0xf0  # store results here
MEM_ROUNDS = 0x900  # run this often (x5 bytes)
FUN_RNG = 0x6CE22  # original RNG function that we overwrite with bx lr

ASM_SNIPPET_RNG = """

    pop {r4-r8, lr} // fix the launch ram 4 byte thingie 
    
    // use r0-r7 locally
    push {r0-r7, lr}
    
    // send a command complete event as we overwrote the launch_RAM handler to prevent HCI timeout event wait
    mov  r0, #0xFC4E // launch RAM command
    mov  r1, 0       // event success
    bl   0x2BCA      // bthci_event_SendCommandCompleteEventWithStatus
    
    // enter RNG dumping mode
    ldr  r0, =0x%x      // run this many rounds
    ldr  r1, =0x%x      // dst: store RNG data here
    bl   dump_rng
    
    // done, let's notify
    bl   notify_hci  // doesn't work on iPhone 7 !!!
    
    // back to lr
    pop  {r0-r7, pc}
    
    
    //// the main RNG dumping routine
    dump_rng:
    
    // wait until RNG is ready, which is indicated by status 0x200fffff
    wait_ready:
        ldr  r2,=0x352604
        ldr  r2, [r2]
        ldr  r3, =0x200fffff
        cmp  r2, r3
        bne  wait_ready  
    
    // request new entropy: rbg_control_adr=1
    mov  r3, 1
    ldr  r2, =0x352600
    str  r3, [r2]
    
    // dst is in r1, dump RNG value here
    ldr  r2, =0x352608
    ldr  r3, [r2]
    str  r3, [r1]
    add  r1, 4 
    
    // add a test byte to ensure that no other process wrote here
    mov  r3, 0x42
    str  r3, [r1]
    add  r1, 1
    
    // loop for rounds in r0
    subs r0, 1
    bne  dump_rng
    bx   lr
    
    
    
    //// issue an HCI event once we're done
    notify_hci:
        
    push  {r0-r4, lr}

    // allocate vendor specific hci event
    mov  r2, 6
    mov  r1, 0xff
    mov  r0, 8
    bl   0x2BF2    // bthci_event_AllocateEventAndFillHeader
    mov  r4, r0    // save pointer to the buffer in r4

    // append buffer with "RAND"
    add  r0, 10
    ldr  r1, =0x444e4152 // RAND
    str  r1, [r0]
    
    // send hci event
    mov  r0, r4  // back to buffer at offset 0
    bl   0x29E0  // bthci_event_AttemptToEnqueueEventToTransport

    pop   {r0-r4, pc}
    
    
""" % (MEM_ROUNDS, MEM_RNG)

internalblue = iOSCore(log_level='info')
internalblue.interface = internalblue.device_list()[0][1]  # just use the first device

# setup sockets
if not internalblue.connect():
    internalblue.logger.critical("No connection to target device.")
    exit(-1)

internalblue.logger.info("installing assembly patches...")

"""

# Disable original RNG
patch = asm("bx lr; bx lr", vma=FUN_RNG)  # 2 times bx lr is 4 bytes and we can only patch 4 bytes
if not internalblue.patchRom(FUN_RNG, patch):
    internalblue.logger.critical("Could not disable original RNG!")
    exit(-1)
"""

# Install the RNG code in RAM (2nd step on iPhone to not disturb the readMemAligned snippet)
code = asm(ASM_SNIPPET_RNG, vma=ASM_LOCATION_RNG)
if not internalblue.writeMem(address=ASM_LOCATION_RNG, data=code, progress_log=None):
    internalblue.logger.critical("error!")
    exit(-1)

# iPhone 7 Launch_RAM fix: overwrite an unused HCI handler
# Here it is not called within the handler table but within another function.
patch = asm("b 0x%x" % ASM_LOCATION_RNG, vma=0x607AC)
if not internalblue.patchRom(0x607AC, patch, 0):  # use slot 0 and only slot 0
    internalblue.logger.critical("Could not implement our launch RAM fix!")
    exit(-1)

internalblue.logger.info("Installed all RNG hooks.")

"""
We cannot call HCI Read_RAM from this callback as it requires another callback (something goes wrong here),
so we cannot solve this recursively but need some global status variable. Still, polling this is way faster
than polling a status register in the Bluetooth firmware itself.
"""
# global status
internalblue.rnd_done = False


def rngStatusCallback(record):
    hcipkt = record[0]  # get HCI Event packet

    if not issubclass(hcipkt.__class__, hci.HCI_Event):
        return

    if hcipkt.data[0:4] == bytes("RAND", "utf-8"):
        internalblue.logger.debug("Random data done!")
        internalblue.rnd_done = True


# add RNG callback
internalblue.registerHciCallback(rngStatusCallback)

# cli.commandLoop(internalblue)


# read for multiple rounds to get more experiment data
rounds = 1000
i = 0
data = bytearray()
while rounds > i:
    internalblue.logger.info("RNG round %i..." % i)

    # launch assembly snippet
    internalblue.launchRam(ASM_LOCATION_RNG)

    # wait until we set the global variable that everything is done
    while not internalblue.rnd_done:
        continue
    internalblue.rnd_done = False

    # and now read and save the random
    random = internalblue.readMem(MEM_RNG, MEM_ROUNDS * 5)

    # do an immediate check to tell where the corruption happened
    check = random[4::5]
    pos = 0
    failed = False
    for c in check:
        pos = pos + 1
        if c != 0x42:
            internalblue.logger.warning("    Data was corrupted at 0x%x, repeating round." % (MEM_RNG + (pos * 5)))
            failed = True
            break

    if failed:
        continue

    # no errors, save data
    data.extend(random)
    i = i + 1

internalblue.logger.info("Finished acquiring random data!")

# uhm and for deleting every 5th let's take numpy (oh why??)
data = np.delete(data, np.arange(4, data.__len__(), 5))

f = open("i7_randomdata-%irounds-%s.bin" % (rounds, datetime.now()), "wb")
f.write(data)
f.close()

internalblue.logger.info("--------------------")
internalblue.logger.info("Entering InternalBlue CLI to interpret RNG.")

# enter CLI
cli = InternalBlueCLI(Namespace(data_directory=None, verbose=False, trace=None, save=None), internalblue)
sys.exit(cli.cmdloop())
