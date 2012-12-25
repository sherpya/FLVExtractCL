
def GetMask(size):
    return (1 << size) - 1

def BitGet(x, length, size=64):
    r = x >> (size - length)
    x = (x << length) & GetMask(size)
    return (x, r)

def BitSet(x, length, value, size=64):
    mask = GetMask(size) >> (size - length)
    return (x << length) | (value & mask)
