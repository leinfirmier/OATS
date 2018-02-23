import mutagen
from mutagen.easyid3 import EasyID3
import sys

def main():
    src = mutagen.File(sys.argv[1], easy=True)
    dest = mutagen.File(sys.argv[2], easy=True)

    for tag in src:
        if tag in EasyID3.valid_keys.keys():
            dest[tag] = src[tag]

    #print(EasyID3.valid_keys.keys())
    dest.save()
    dest = mutagen.File(sys.argv[2])

    if len(src.pictures) > 0:
        apic = mutagen.id3.APIC(mime=src.pictures[0].mime, data=src.pictures[0].data)
        dest.tags.add(apic)

    dest.save()


