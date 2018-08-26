"""
Test application to dump the raw data received from the CCD line.
Parses it with Numpy and plots it with Matplotlib.
Needs 2 Uarts. One for the WishboneUart bridge for control and a
second one for the UartMemoryDumper.
"""
from litex.soc.tools.remote import RemoteClient
from time import sleep
from numpy import *
from matplotlib.pyplot import *
from matplotlib.animation import FuncAnimation
import threading
import argparse
from subprocess import Popen, call
from serial import Serial
import atexit


def main():
    global runThread, readData
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tty_ctrl", default="/dev/ttyUSB1", help="UartWishboneBridge for control")
    parser.add_argument("--tty_dump", default="/dev/ttyUSB2", help="UartMemoryDumper for data")
    parser.add_argument("--br_ctrl", default=115200, type=int, help="UartWishboneBridge baudrate")
    parser.add_argument("--br_dump", default=115200, type=int, help="UartMemoryDumper baudrate")
    args = parser.parse_args()
    print(args)

    #----------------------------------------------
    # Setup litex_server
    #----------------------------------------------
    call(["pkill", "litex_server*"])
    Popen(["litex_server", "uart", args.tty_ctrl, str(args.br_ctrl)])
    sleep(0.5)
    wishbone = RemoteClient(csr_csv="./build/csr.csv")
    atexit.register(wishbone.close)
    wishbone.open()
    fclk = wishbone.constants.system_clock_frequency

    #----------------------------------------------
    # Setup Matplotlib
    #----------------------------------------------
    def get_tau():
        intVal = wishbone.regs.ccd_i_tau.read()
        tau = intVal / fclk / 1e-3
        print("get_tau:", intVal, tau)
        return tau

    def set_tau(tau):
        intVal = int(tau * 1e-3 * fclk)
        wishbone.regs.ccd_i_tau.write(intVal)

    def update_plot(frame):
        print("u", end="", flush=True)
        l.set_ydata(readData)
        return l

    xdata = arange(128)
    ydata = zeros(128)
    ydata[1] = 4096
    fig, ax = subplots()
    l, = ax.plot(xdata, ydata, "-o")
    axfreq = axes([0.13, 0.9, 0.7, 0.05])
    sfreq = Slider(axfreq, 'Tau [ms]', 0.01, 100, valinit=get_tau())
    sfreq.on_changed(set_tau)

    #----------------------------------------------
    # Setup serial reader thread
    #----------------------------------------------
    wishbone.regs.mem_dump_tuneWord.write(
        int(args.br_dump / fclk * 2**32)
    )
    serial = Serial(args.tty_dump, args.br_dump)
    def read_from_port():
        while serial.isOpen():
            serial.read_until(b"\x42")
            buf = serial.read(256)
            readData = fromstring(buf, dtype=">u2")
            l.set_ydata(readData)
            fig.canvas.draw_idle()
            # print("*", end="", flush=True)

    atexit.register(serial.close)
    threading.Thread(target=read_from_port).start()
    show()

if __name__ == '__main__':
    main()