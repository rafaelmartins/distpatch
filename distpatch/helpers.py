# -*- coding: utf-8 -*-

import os


def uncompressed_filename_and_compressor(tarball):
    '''returns the filename of the given tarball uncompressed and the compressor.
    '''

    compressors = {
        '.gz': ('gzip', ''),
        '.bz2': ('bzip2', ''),
        '.xz': ('xz', ''),
        '.lzma': ('lzma', ''),
        '.tgz': ('gzip', '.tar'),
        '.tbz2': ('bzip2', '.tar'),
    }

    dest, ext = os.path.splitext(tarball)
    compressor = compressors.get(ext.lower(), None)
    if compressor is None:
        return tarball, None
    return dest + compressor[1], compressor[0]


def format_size(size):

    KB = 1024
    MB = KB * 1024
    GB = MB * 1024
    TB = GB * 1024

    size = float(size)

    if size > TB:
        return '%.3f TB' % (size / TB)
    elif size > GB:
        return '%.3f GB' % (size / GB)
    elif size > MB:
        return '%.3f MB' % (size / MB)
    elif size > KB:
        return '%.3f KB' % (size / KB)
    else:
        return '%.0f B' % size
