# -*- coding: utf-8 -*-

from hashlib import md5
from shutil import copy2, rmtree
from subprocess import call
from tempfile import mkdtemp

from helpers import uncompressed_filename_and_compressor
from patch import Patch

import os
import portage

class DiffException(Exception):
    pass


class Diff:
    
    patch_format = 'switching'
    
    def __init__(self, src_distfile, src_ebuild, dest_distfile, dest_ebuild):
        self.src_distfile = src_distfile
        self.src_ebuild = src_ebuild
        self.dest_distfile = dest_distfile
        self.dest_ebuild = dest_ebuild
    
    def fetch_distfiles(self):
        self.src_ebuild.fetch(self.src_distfile)
        self.dest_ebuild.fetch(self.dest_distfile)
    
    def _copy_and_unpack(self, myfile, output_dir):
        distdir = portage.settings['DISTDIR']
        copy2(os.path.join(distdir, myfile), output_dir)
        tarball = os.path.join(output_dir, myfile)
        dest, program = uncompressed_filename_and_compressor(tarball)
        if program is not None and call([program, '-fd', tarball]) != os.EX_OK:
            raise DiffException('Failed to unpack file: %s' % tarball)
        return dest
    
    def generate(self, output_dir, clean_sources=True, compress=True):
        # running diffball from a git repository, while a version with xz support
        # isn't released :)
        diffball_bindir = os.environ.get('DIFFBALL_BINDIR', '/usr/bin')
        differ = os.path.join(diffball_bindir, 'differ')
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        src = self._copy_and_unpack(self.src_distfile, output_dir)
        dest = self._copy_and_unpack(self.dest_distfile, output_dir)
        self.diff_file = os.path.join(output_dir,
                                      '%s-%s.%s' % (self.src_distfile,
                                                    self.dest_distfile,
                                                    self.patch_format))
        
        cmd = [differ, src, dest, '--patch-format', self.patch_format,
               self.diff_file]
        
        if call(cmd) != os.EX_OK:
            raise DiffException('Failed to generate diff: %s' % self.diff_file)
        
        # validate
        patch = Patch(output_dir, self.src_distfile, self.dest_distfile, src)
        tmpdir = mkdtemp()
        patch.reconstruct(tmpdir)
        with open(dest, 'rb') as fp:
            cksm_dest = md5(fp.read()).hexdigest()
        with open(os.path.join(tmpdir, os.path.basename(dest)), 'rb') as fp:
            cksm_rec = md5(fp.read()).hexdigest()
        rmtree(tmpdir)
        if cksm_dest != cksm_rec:
            raise DiffException('Bad delta! :(')
        
        # remove sources
        if clean_sources:
            os.unlink(src)
            os.unlink(dest)
        
        # xz it
        if compress:
            if call(['xz', self.diff_file]) != os.EX_OK:
                raise DiffException('Failed to xz diff: %s' % self.diff_file)
            self.diff_file += '.xz'
    
    def __repr__(self):
        return '<%s %s -> %s>' % (self.__class__.__name__, self.src_distfile,
                                  self.dest_distfile)