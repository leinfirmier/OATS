"""
Bencoding for OATS
"""

def bencode_bytes(var):
    return str(len(var)).encode() + b':' + var


def bencode_string(var):
    return bencode_bytes(var.encode())


def bencode_integer(var):
    return b'i' + str(var).encode() + b'e'


def bencode_boolean(var):
    return b'i1e' if var else b'i0e'


def bencode_list(var):
    ret = b'l'

    for item in var:
        ret += Bencode(item)

    return ret + b'e'


def bencode_dict(var):
    ret = b'd'

    for key, value in sorted(var.items(), key=lambda x: x[0]):
        ret += Bencode(key) + Bencode(value)

    return ret + b'e'


def Bencode(var):
    vartype = type(var)
    varfunc = {int: bencode_integer,
               bool: bencode_boolean,
               str: bencode_string,
               bytes: bencode_bytes,
               list: bencode_list,
               tuple: bencode_list,
               dict: bencode_dict}

    return varfunc[vartype](var)

