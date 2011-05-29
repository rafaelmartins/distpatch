# -*- coding: utf-8 -*-

import os

def uncompressed_filename_and_compressor(tarball):
    '''returns the filename of the given tarball uncompressed and the compressor.
    '''
    dest, ext = os.path.splitext(tarball)
    compressor = None
    if ext in ('.gz', '.tgz'):
        compressor = 'gzip'
    elif ext in ('.bz2', '.tbz2'):
        compressor = 'bzip2'
    elif ext == '.xz':
        compressor = 'xz'
    elif ext == '.lzma':
        compressor = 'lzma'
    if ext in ('.tgz', '.tbz2'):
        return dest + '.tar', compressor
    return dest, compressor
