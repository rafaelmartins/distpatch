# -*- coding: utf-8 -*-
"""
    distpatch.helpers
    ~~~~~~~~~~~~~~~~~

    Helper functions for distpatch.

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

import atexit
import os
import shutil
import tempfile

from subprocess import call


def tempdir(*args, **kwargs):
    def cleanup(directory):
        if os.path.isdir(directory):
            shutil.rmtree(directory)
    dirname = tempfile.mkdtemp(*args, **kwargs)
    atexit.register(cleanup, dirname)
    return dirname


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


def uncompress(fname, output_dir=None):
    # extract to a temporary directory and move back, to keep both files:
    # compressed and uncompressed.
    base_src = os.path.basename(fname)
    base_dest, compressor = uncompressed_filename_and_compressor(base_src)
    tmp_dir = tempdir()
    tmp_src = os.path.join(tmp_dir, base_src)
    tmp_dest = os.path.join(tmp_dir, base_dest)
    local_dir = os.path.dirname(os.path.abspath(fname))
    local_src = os.path.join(local_dir, base_src)
    if output_dir is None:
        local_dest = os.path.join(local_dir, base_dest)
    else:
        local_dest = os.path.join(output_dir, base_dest)
    shutil.copy2(local_src, tmp_src)
    if compressor is not None:
        rv = call([compressor, '-fd', tmp_src])
        if rv is not os.EX_OK:
            raise RuntimeError('Failed to decompress file: %d' % rv)
        if not os.path.exists(tmp_dest):
            raise RuntimeError('Decompressed file not found: %s' % tmp_dest)
    shutil.move(tmp_dest, local_dest)
    # we do automatic cleanup, but we should remove it here to save disk space
    shutil.rmtree(tmp_dir)
    return local_dest


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
