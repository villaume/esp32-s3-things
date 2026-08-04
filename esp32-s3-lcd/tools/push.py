# /// script
# dependencies = ["pyserial"]
# ///
"""Copy a file to the board over the plain raw REPL, verified by SHA-256.

`mpremote fs cp` is not reliable against this board's firmware (MicroPython
1.22.0-preview, 2023-12-02): it has silently truncated an 11 KB file to 4352
bytes and, on other runs, reported success while writing nothing at all. Its
raw-paste flow control does not agree with this build. This script uses the
plain raw REPL in small chunks and refuses to claim success unless the file on
the device hashes to the same value as the local one.

    uv run tools/push.py main.py
    MPY_PORT=/dev/cu.usbmodemXXXX uv run tools/push.py main.py [remote_name]
"""
import base64
import glob
import hashlib
import os
import sys
import time

import serial

CHUNK = 192


def find_port():
    port = os.environ.get("MPY_PORT")
    if port:
        return port
    # Deliberately not mpremote's "connect auto", which happily picks
    # /dev/cu.Bluetooth-Incoming-Port and floods 0xff.
    candidates = sorted(glob.glob("/dev/cu.usbmodem*") +
                        glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    if not candidates:
        sys.exit("no board found; set MPY_PORT=/dev/cu.usbmodemXXXX")
    if len(candidates) > 1:
        sys.exit("multiple ports found, set MPY_PORT to one of: " +
                 ", ".join(candidates))
    return candidates[0]


def raw_cmd(ser, cmd, timeout=10):
    """Run one statement in the raw REPL and return its stdout."""
    ser.write(cmd.encode() + b"\x04")
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        buf += ser.read(256)
        if buf.count(b"\x04") >= 2 and buf.rstrip().endswith(b">"):
            break
    if not buf.startswith(b"OK"):
        raise RuntimeError("no OK from board: %r" % buf[:120])
    out, _, rest = buf[2:].partition(b"\x04")
    err, _, _ = rest.partition(b"\x04")
    if err.strip():
        raise RuntimeError(err.decode("utf8", "replace").strip())
    return out.decode("utf8", "replace")


def enter_raw_repl(ser):
    """Reset, then interrupt during boot.py's sleep before main.py can run.

    Without the reset this cannot get in while main.py is crash-looping.
    """
    ser.dtr = False
    ser.rts = True
    time.sleep(0.15)
    ser.rts = False
    deadline = time.time() + 8
    while time.time() < deadline:
        ser.write(b"\r\x03\x03")
        time.sleep(0.1)
        ser.reset_input_buffer()
        ser.write(b"\r\x01")
        time.sleep(0.25)
        if b"raw REPL" in ser.read(300):
            return True
    return False


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    local = sys.argv[1]
    remote = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(local)

    with open(local, "rb") as fh:
        data = fh.read()
    want = hashlib.sha256(data).hexdigest()

    port = find_port()
    ser = serial.Serial(port, 115200, timeout=1)
    if not enter_raw_repl(ser):
        sys.exit("could not enter raw REPL on %s" % port)

    raw_cmd(ser, "import binascii\nf=open(%r,'wb')" % remote)
    for i in range(0, len(data), CHUNK):
        payload = base64.b64encode(data[i:i + CHUNK]).decode()
        raw_cmd(ser, "f.write(binascii.a2b_base64('%s'))" % payload)
        print("\r  %s: %d/%d bytes" % (remote, min(i + CHUNK, len(data)),
                                       len(data)), end="", flush=True)
    raw_cmd(ser, "f.close()")
    print()

    got = raw_cmd(ser, """
try:
    import hashlib
except ImportError:
    import uhashlib as hashlib
import binascii
d=open(%r,'rb').read()
print(len(d), binascii.hexlify(hashlib.sha256(d).digest()).decode())
""" % remote).strip()
    ser.write(b"\r\x02")
    ser.close()

    gotsize, gothash = got.split()
    if gothash == want and int(gotsize) == len(data):
        print("OK   %s verified: %s bytes, sha256 %s" %
              (remote, gotsize, gothash[:16]))
    else:
        sys.exit("FAIL %s: device has %s bytes / %s, want %d / %s" %
                 (remote, gotsize, gothash[:16], len(data), want[:16]))


if __name__ == "__main__":
    main()
