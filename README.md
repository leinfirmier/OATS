# OATS
OATS is Another Transcoding Script

OATS is a commandline tool that makes transcoding easy on Windows, Linux, or Mac.
The only prerequisites for OATS are FFmpeg and Python3. It can also make
torrents.

## A quick intro

OATS has one main script, called `oats`. Once installed you can make a quick
config file to get started:

  `oats mkconfig`

This will make a file in the current working directory named `oats.conf`. The
options accessible there are the same as in the interface, so you can configure
the defaults for your use. Any options specified at the command line take
priority over the config file. All options not supplied to the command line
will use their values set in the config file.

To see the options for `oats`, access the help:

  `oats -h`

Here's a sample command for transcoding two albums to MP3 at constant bitrate of 320
and MP3 of variable bitrate, quality 2, resulting files will be put into a directory
named `transcodes`:

  `oats --output-dir transcodes --formats "MP3 CBR 320,MP3 VBR 2" Album1 Album2`

## What formats can I use?

The best way to see what audio formats you can use is to enter

  `oats -F`

which will print a list of all available formats on your system. Formats may
allow parsed arguments which will be described per
`{name;units:restrictions}`. For instance "MP3 CBR {bitrate;kbps:8-320}"
indicates that MP3 constant bitrate accepts values in kbps between 8 and 320.

## Torrent creation options

The following options pertain to torrent creation: `--torrent=<bool>`,
`--announce-url=<url>`, `--torrent-dir=<dir>`, and `--source=<str>`. A full
example of these options is given here.

  `oats --torrent true --torrent-dir torrent_output --announce-url https://blah.com MyAlbum`

## Tool Extensibility in OATS

OATS is a frontend to a variety of audio codec tools. In its first iteration it
was just a frontend to FFmpeg, but now is able to modularly use different tools
and dynamically detect what is available. For instance, if you install LAME on
your system, and "lame" can be found on the path, OATS will attempt to
encode your MP3s with it instead of FFmpeg (currently, FFmpeg's Xing header is
considered deficient). Similarly, Opus Tools' `opusenc` and `opusdec`, and
Vorbis Tools' `oggenc` and `oggdec` will be employed over FFmpeg.

FFmpeg provides a good baseline of support for most formats, and you may never
need anything else. I hope to also add Sound eXchange (SoX) in the future as
a general tool.

## TODO - Things I want to do that are not yet done

 * ALAC support
 * AAC support
 * SoX Codecs
 * Channel Ops?
 * Possibly provide workaround for Windows Powershell tab-completion bug
 * magnet link support
