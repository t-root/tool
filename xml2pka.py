#!/usr/bin/env python3
"""
xml2pka.py - Chuyen doi qua lai giua XML va file Packet Tracer (.pka / .pkt)

Khong can cai them thu vien nao (Twofish + EAX viet bang Python thuan).

Cach dung:
    python xml2pka.py encode  input.xml  output.pka     # XML  -> PKA/PKT
    python xml2pka.py decode  input.pka  output.xml     # PKA/PKT -> XML
    python xml2pka.py selftest                          # tu kiem tra thuat toan
    python xml2pka.py input.xml                         # rut gon: tu doan chieu, tu dat ten

Thuat toan (theo pka2xml, dung cho Packet Tracer 7.x -> 9.x):
  ENCODE: XML -> nen zlib (4 byte do dai big-endian + zlib)
              -> XOR tung byte voi (len - i)
              -> Twofish-EAX (key = 16 byte 0x89, nonce = 16 byte 0x10, tag 16 byte o cuoi)
              -> dao nguoc va XOR voi (len - i*len)
  DECODE: lam nguoc lai.
Du lieu duoc xu ly o dang byte nen khong lam hong ky tu la trong XML.
"""
import os
import struct
import sys
import zlib

KEY = bytes([137] * 16)
NONCE = bytes([16] * 16)

# ----------------------------------------------------------------------------
# Twofish (khoa 128 bit) - Python thuan
# ----------------------------------------------------------------------------
_T = {
    0: ([0x8, 0x1, 0x7, 0xD, 0x6, 0xF, 0x3, 0x2, 0x0, 0xB, 0x5, 0x9, 0xE, 0xC, 0xA, 0x4],
        [0xE, 0xC, 0xB, 0x8, 0x1, 0x2, 0x3, 0x5, 0xF, 0x4, 0xA, 0x6, 0x7, 0x0, 0x9, 0xD],
        [0xB, 0xA, 0x5, 0xE, 0x6, 0xD, 0x9, 0x0, 0xC, 0x8, 0xF, 0x3, 0x2, 0x4, 0x7, 0x1],
        [0xD, 0x7, 0xF, 0x4, 0x1, 0x2, 0x6, 0xE, 0x9, 0xB, 0x3, 0x0, 0x8, 0x5, 0xC, 0xA]),
    1: ([0x2, 0x8, 0xB, 0xD, 0xF, 0x7, 0x6, 0xE, 0x3, 0x1, 0x9, 0x4, 0x0, 0xA, 0xC, 0x5],
        [0x1, 0xE, 0x2, 0xB, 0x4, 0xC, 0x3, 0x7, 0x6, 0xD, 0xA, 0x5, 0xF, 0x9, 0x0, 0x8],
        [0x4, 0xC, 0x7, 0x5, 0x1, 0x6, 0x9, 0xA, 0x0, 0xE, 0xD, 0x8, 0x2, 0xB, 0x3, 0xF],
        [0xB, 0x9, 0x5, 0x1, 0xC, 0x3, 0xD, 0xE, 0x6, 0x4, 0x7, 0xF, 0x2, 0x0, 0x8, 0xA]),
}


def _ror4(x, n):
    return ((x >> n) | (x << (4 - n))) & 0xF


def _make_q(which):
    t0, t1, t2, t3 = _T[which]
    q = []
    for x in range(256):
        a0, b0 = x >> 4, x & 15
        a1 = a0 ^ b0
        b1 = (a0 ^ _ror4(b0, 1) ^ ((8 * a0) & 15)) & 15
        a2, b2 = t0[a1], t1[b1]
        a3 = a2 ^ b2
        b3 = (a2 ^ _ror4(b2, 1) ^ ((8 * a2) & 15)) & 15
        a4, b4 = t2[a3], t3[b3]
        q.append((b4 << 4) | a4)
    return q


_Q0 = _make_q(0)
_Q1 = _make_q(1)


def _gf(a, b, poly):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a <<= 1
        if a & 0x100:
            a ^= poly
        b >>= 1
    return r


_MDS = [[0x01, 0xEF, 0x5B, 0x5B],
        [0x5B, 0xEF, 0xEF, 0x01],
        [0xEF, 0x5B, 0x01, 0xEF],
        [0xEF, 0x01, 0xEF, 0x5B]]
_RS = [[0x01, 0xA4, 0x55, 0x87, 0x5A, 0x58, 0xDB, 0x9E],
       [0xA4, 0x56, 0x82, 0xF3, 0x1E, 0xC6, 0x68, 0xE5],
       [0x02, 0xA1, 0xFC, 0xC1, 0x47, 0xAE, 0x3D, 0x19],
       [0xA4, 0x55, 0x87, 0x5A, 0x58, 0xDB, 0x9E, 0x03]]


def _rol(x, n):
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def _ror(x, n):
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


def _mds_word(y):
    z = 0
    for i in range(4):
        v = 0
        for j in range(4):
            v ^= _gf(_MDS[i][j], y[j], 0x169)
        z |= v << (8 * i)
    return z


def _h(x, l0, l1):
    y = [(x >> (8 * i)) & 0xFF for i in range(4)]
    y0 = _Q1[_Q0[_Q0[y[0]] ^ l1[0]] ^ l0[0]]
    y1 = _Q0[_Q0[_Q1[y[1]] ^ l1[1]] ^ l0[1]]
    y2 = _Q1[_Q1[_Q0[y[2]] ^ l1[2]] ^ l0[2]]
    y3 = _Q0[_Q1[_Q1[y[3]] ^ l1[3]] ^ l0[3]]
    return _mds_word([y0, y1, y2, y3])


class Twofish128:
    block_size = 16

    def __init__(self, key):
        if len(key) != 16:
            raise ValueError("chi ho tro khoa 128 bit")
        w = struct.unpack("<4I", key)
        me, mo = [w[0], w[2]], [w[1], w[3]]
        s = []
        for i in range(2):
            kb = key[8 * i:8 * i + 8]
            word = 0
            for r in range(4):
                v = 0
                for c in range(8):
                    v ^= _gf(_RS[r][c], kb[c], 0x14D)
                word |= v << (8 * r)
            s.append(word)
        s.reverse()  # S = [S1, S0]
        sb = [[(s[0] >> (8 * i)) & 0xFF for i in range(4)],
              [(s[1] >> (8 * i)) & 0xFF for i in range(4)]]
        # bang tra g(x) = h(x, S)
        self._g = [[0] * 256 for _ in range(4)]
        for x in range(256):
            y0 = _Q1[_Q0[_Q0[x] ^ sb[1][0]] ^ sb[0][0]]
            y1 = _Q0[_Q0[_Q1[x] ^ sb[1][1]] ^ sb[0][1]]
            y2 = _Q1[_Q1[_Q0[x] ^ sb[1][2]] ^ sb[0][2]]
            y3 = _Q0[_Q1[_Q1[x] ^ sb[1][3]] ^ sb[0][3]]
            for pos, yv in enumerate((y0, y1, y2, y3)):
                col = [0, 0, 0, 0]
                col[pos] = yv
                self._g[pos][x] = _mds_word(col)
        # subkeys
        me_b = [[(m >> (8 * i)) & 0xFF for i in range(4)] for m in me]
        mo_b = [[(m >> (8 * i)) & 0xFF for i in range(4)] for m in mo]
        k = []
        for i in range(20):
            a = _h((2 * i * 0x01010101) & 0xFFFFFFFF, me_b[0], me_b[1])
            b = _rol(_h(((2 * i + 1) * 0x01010101) & 0xFFFFFFFF, mo_b[0], mo_b[1]), 8)
            k.append((a + b) & 0xFFFFFFFF)
            k.append(_rol((a + 2 * b) & 0xFFFFFFFF, 9))
        self._k = k

    def _G(self, x):
        g = self._g
        return (g[0][x & 255] ^ g[1][(x >> 8) & 255] ^
                g[2][(x >> 16) & 255] ^ g[3][(x >> 24) & 255])

    def encrypt(self, block):
        k = self._k
        r0, r1, r2, r3 = struct.unpack("<4I", block)
        r0 ^= k[0]; r1 ^= k[1]; r2 ^= k[2]; r3 ^= k[3]
        for r in range(16):
            t0 = self._G(r0)
            t1 = self._G(_rol(r1, 8))
            f0 = (t0 + t1 + k[2 * r + 8]) & 0xFFFFFFFF
            f1 = (t0 + 2 * t1 + k[2 * r + 9]) & 0xFFFFFFFF
            r2 = _ror(r2 ^ f0, 1)
            r3 = _rol(r3, 1) ^ f1
            r0, r1, r2, r3 = r2, r3, r0, r1
        return struct.pack("<4I", r2 ^ k[4], r3 ^ k[5], r0 ^ k[6], r1 ^ k[7])


# ----------------------------------------------------------------------------
# EAX (nonce 16 byte, khong co header, tag 16 byte)
# ----------------------------------------------------------------------------
def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def _dbl(b):
    n = int.from_bytes(b, "big") << 1
    if n >> 128:
        n = (n & ((1 << 128) - 1)) ^ 0x87
    return n.to_bytes(16, "big")


def _cmac(enc, data):
    L = enc(bytes(16))
    k1 = _dbl(L)
    k2 = _dbl(k1)
    n = len(data)
    nblocks = max(1, (n + 15) // 16)
    complete = n > 0 and n % 16 == 0
    x = bytes(16)
    for i in range(nblocks - 1):
        x = enc(_xor(x, data[16 * i:16 * i + 16]))
    last = data[16 * (nblocks - 1):]
    if complete:
        last = _xor(last, k1)
    else:
        last = last + b"\x80" + bytes(15 - len(last))
        last = _xor(last, k2)
    return enc(_xor(x, last))


def _omac(enc, t, data):
    return _cmac(enc, bytes(15) + bytes([t]) + data)


def _ctr(enc, iv, data):
    out = bytearray(len(data))
    ctr = int.from_bytes(iv, "big")
    for i in range(0, len(data), 16):
        ks = enc(ctr.to_bytes(16, "big"))
        chunk = data[i:i + 16]
        out[i:i + len(chunk)] = _xor(chunk, ks)
        ctr = (ctr + 1) & ((1 << 128) - 1)
    return bytes(out)


def eax_encrypt(enc, nonce, plain, header=b""):
    n = _omac(enc, 0, nonce)
    h = _omac(enc, 1, header)
    c = _ctr(enc, n, plain)
    tag = _xor(_xor(n, h), _omac(enc, 2, c))
    return c + tag


def eax_decrypt(enc, nonce, data, header=b""):
    if len(data) < 16:
        raise ValueError("du lieu qua ngan")
    c, tag = data[:-16], data[-16:]
    n = _omac(enc, 0, nonce)
    h = _omac(enc, 1, header)
    expect = _xor(_xor(n, h), _omac(enc, 2, c))
    if expect != tag:
        raise ValueError("Sai tag EAX - file khong dung dinh dang hoac bi hong")
    return _ctr(enc, n, c)


# ----------------------------------------------------------------------------
# Dinh dang Packet Tracer
# ----------------------------------------------------------------------------
def xml_to_pka(xml_bytes):
    comp = struct.pack(">I", len(xml_bytes)) + zlib.compress(xml_bytes)
    n = len(comp)
    stage = bytes((comp[i] ^ ((n - i) & 0xFF)) for i in range(n))
    tf = Twofish128(KEY)
    enc = eax_encrypt(tf.encrypt, NONCE, stage)
    L = len(enc)
    out = bytearray(L)
    for i in range(L):
        out[L - 1 - i] = enc[i] ^ ((L - i * L) & 0xFF)
    return bytes(out)


def pka_to_xml(data):
    L = len(data)
    s1 = bytes((data[L - 1 - i] ^ ((L - i * L) & 0xFF)) for i in range(L))
    tf = Twofish128(KEY)
    dec = eax_decrypt(tf.encrypt, NONCE, s1)
    n = len(dec)
    comp = bytes((dec[i] ^ ((n - i) & 0xFF)) for i in range(n))
    size = struct.unpack(">I", comp[:4])[0]
    xml = zlib.decompress(comp[4:])
    if len(xml) != size:
        raise ValueError("Do dai sau giai nen khong khop")
    return xml


def selftest():
    # Vector chuan Twofish-128 (key = 0, plaintext = 0)
    tf = Twofish128(bytes(16))
    got = tf.encrypt(bytes(16)).hex().upper()
    want = "9F589F5CF6122C32B6BFEC2F2AE8C35A"
    print("Twofish vector :", "OK" if got == want else "SAI (%s)" % got)
    assert got == want
    sample = b"<?xml version='1.0'?><PACKETTRACER5_ACTIVITY>" + bytes(range(256)) * 50 + b"</PACKETTRACER5_ACTIVITY>"
    back = pka_to_xml(xml_to_pka(sample))
    print("Round trip     :", "OK" if back == sample else "SAI")
    assert back == sample


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        selftest()
        return 0
    if len(argv) == 2:  # tu doan chieu
        src = argv[1]
        low = src.lower()
        if low.endswith(".xml"):
            argv = [argv[0], "encode", src, os.path.splitext(src)[0] + ".pka"]
        else:
            argv = [argv[0], "decode", src, os.path.splitext(src)[0] + ".xml"]
    if len(argv) != 4 or argv[1] not in ("encode", "decode"):
        print(__doc__)
        return 1
    mode, src, dst = argv[1], argv[2], argv[3]
    with open(src, "rb") as f:
        data = f.read()
    out = xml_to_pka(data) if mode == "encode" else pka_to_xml(data)
    with open(dst, "wb") as f:
        f.write(out)
    print("%s: %s -> %s (%d -> %d byte)" % (mode, src, dst, len(data), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
