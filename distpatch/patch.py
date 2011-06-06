# -*- coding: utf-8 -*-

from subprocess import call
from helpers import uncompressed_filename_and_compressor

import glob
import os
import re

re_diff_filename = re.compile(r'(?P<dest>.+)\.(?P<format>[^(\.xz)]+)(\.xz)?$')

class PatchException(Exception):
    pass


class Patch:
    
    def __init__(self, src_dir, src_distfile, dest_distfile):
        self.src_dir = src_dir
        self.src_distfile = src_distfile
        self.dest_distfile = dest_distfile
        self._generate_delta_sequence()
    
    def _get_diff(self, src_distfile):
        diffs = glob.glob(os.path.join(self.src_dir, src_distfile + '-*'))
        diffs = [os.path.basename(i) for i in diffs]
        if len(diffs) == 0:
            raise PatchException('No diff available for: %s' % src_distfile)
        if len(diffs) > 1:
            raise PatchException('More than 1 diff with %s as source.' % src_distfile)
        return diffs[0]
    
    def _generate_delta_sequence(self):
        current_format = None
        current_src = self.src_distfile[:]
        self._diffs = []
        while current_src != self.dest_distfile:
            current_diff = self._get_diff(current_src)
            if not current_diff.startswith(current_src):
                raise PatchException('Invalid diff: %s' % current_diff)
            rv = re_diff_filename.match(current_diff[len(current_src)+1:])
            if rv is None:
                raise PatchException('Invalid diff naming scheme: %s' % \
                                     current_diff)
            rd = rv.groupdict()
            if current_format is not None:
                if rd['format'] != current_format:
                    raise PatchException(
                        'All the patches should have the same format: %s != %s' % \
                        (rd['format'], current_format))
            self._diffs.append(current_diff)
            current_format = rd['format']
            current_src = rd['dest']
        self.patch_format = current_format

    def reconstruct(self, output_dir, compress=True):
        diffball_bindir = os.environ.get('DIFFBALL_BINDIR', '/usr/bin')
        patcher = os.path.join(diffball_bindir, 'patcher')
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        src = uncompressed_filename_and_compressor(self.src_distfile)[0]
        src = os.path.join(self.src_dir, src)
        dest, compressor = uncompressed_filename_and_compressor(self.dest_distfile)
        dest = os.path.join(output_dir, dest)
        
        cmd = [patcher, src, '--patch-format', self.patch_format]
        cmd += [os.path.join(self.src_dir, i) for i in self._diffs]
        cmd.append(dest)
        
        if call(cmd) != os.EX_OK:
            raise PatchException('Failed to reconstruct file: %s' % dest)

        if compress and compressor is not None and call([compressor, dest]) != os.EX_OK:
            raise PatchException('Failed to compress reconstructed file: %s' % dest)
