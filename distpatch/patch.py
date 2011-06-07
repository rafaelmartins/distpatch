# -*- coding: utf-8 -*-

from subprocess import call
from helpers import uncompressed_filename_and_compressor

import glob
import os
import portage
import re

re_diff_filename = re.compile(r'(?P<dest>.+)\.(?P<format>[^(\.xz)]+)(\.xz)?$')

class PatchException(Exception):
    pass


class Patch:
    
    def __init__(self, *dbrecords):
        self.dbrecords = dbrecords
        self.src_distfile = os.path.basename(dbrecords[0].src.fname)
        self.dest_distfile = os.path.basename(dbrecords[-1].dest.fname)
        if not self._verify_deltas():
            raise PatchException('Invalid delta sequence: %s' % self.dbrecords)
    
    def _verify_deltas(self):
        self.patch_format = None
        for record in self.dbrecords:
            rv = re_diff_filename.match(record.delta.fname)
            if rv is None:
                return False
            patch_format = rv.groupdict()['format']
            if self.patch_format is None:
                self.patch_format = patch_format
                continue
            if self.patch_format != patch_format:
                return False
        return True

    def reconstruct(self, input_dir=None, output_dir=None, compress=True):
        diffball_bindir = os.environ.get('DIFFBALL_BINDIR', '/usr/bin')
        patcher = os.path.join(diffball_bindir, 'patcher')

        distdir = portage.settings['DISTDIR']
        if input_dir is None:
            input_dir = os.path.join(distdir, 'patches')
        if output_dir is None:
            output_dir = distdir
        src = os.path.join(distdir, self.src_distfile)
        dest, compressor = uncompressed_filename_and_compressor(self.dest_distfile)
        dest = os.path.join(output_dir, dest)
        
        cmd = [patcher, src, '--patch-format', self.patch_format]
        cmd += [os.path.join(input_dir, i.delta.fname) for i in self.dbrecords]
        cmd.append(dest)

        if call(cmd) != os.EX_OK:
            raise PatchException('Failed to reconstruct file: %s' % dest)

        if compress and compressor is not None and call([compressor, dest]) != os.EX_OK:
            raise PatchException('Failed to compress reconstructed file: %s' % dest)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__,
                            ' -> '.join([i.delta.fname for i in self.dbrecords]))
