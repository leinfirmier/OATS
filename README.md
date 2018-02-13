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
priority over the config file.

To see the options for `oats`, do the following:

  `oats -h`

Here's a sample command for transcoding two albums to MP3 320 and MP3 V2, the
resulting files will be put into a directory named `transcodes`:

  `oats --output-dir transcodes --formats 320,V2 Album1 Album2`

If you want to enable torrent creation, you can set the following options:

  `oats --torrent true --torrent-dir torrents --announce-url https://blah.com MyAlbum`

All options not supplied to the command line will use their values set in the
config file.

## TODO - Things I want to do that are not yet done

 * Refine ALAC support
 * Provide Vorbis support
 * Provide Opus support
 * Maybe provide options for channel operations, stereo -> mono is popular bitate
   conservation method for audiobooks
 * Possibly provide workaround for Windows Powershell tab-completion bug
 * Support magnet links
