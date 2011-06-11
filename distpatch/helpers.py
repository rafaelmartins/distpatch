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
