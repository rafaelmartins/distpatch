# -*- coding: utf-8 -*-

import os
import portage

from collections import OrderedDict

from distpatch.diff import Diff
from distpatch.ebuild import Ebuild
from distpatch.patch import Patch

dbapi = portage.db[portage.settings['ROOT']]['porttree'].dbapi


class PackageException(Exception):
    pass


class Package:

    def __init__(self, deltadb):
        self.deltadb = deltadb

    def _lineage_identification(self):
        self.diffs = []
        diffs = []
        taken = {}
        for ebuild_id in range(len(self.ebuilds) - 1):
            cpvs = self.ebuilds.keys()
            src_cpv = cpvs[ebuild_id]
            dest_cpv = cpvs[ebuild_id + 1]
            src_ebuild = self.ebuilds[src_cpv]
            dest_ebuild = self.ebuilds[dest_cpv]
            for src_distfile in src_ebuild.src_uri_map.keys():
                avg_distfile = None
                avg_ebuild = None
                max_avg = 0.0
                avgs = {}
                for dest_distfile in dest_ebuild.src_uri_map.keys():
                    prefix = ''
                    suffix = ''
                    for i in range(min(len(src_distfile), len(dest_distfile))):
                        if src_distfile[i] == dest_distfile[i]:
                            prefix += src_distfile[i]
                        else:
                            break
                    for i in range(min(len(src_distfile), len(dest_distfile))):
                        if src_distfile[-i - 1] == dest_distfile[-i - 1]:
                            suffix = src_distfile[-i - 1] + suffix
                        else:
                            break
                    avg = float(len(prefix) + len(suffix)) / 2
                    if avg in avgs:
                        if avg_distfile == avgs[avg]:
                            avg_distfile = None
                            avg_ebuild = None
                        continue
                    avgs[avg] = dest_distfile
                    if avg > max_avg:
                        avg_distfile = dest_distfile
                        avg_ebuild = dest_ebuild
                        max_avg = avg
                if avg_distfile is not None and src_distfile != avg_distfile:
                    diffs.append((max_avg, Diff(src_distfile, src_ebuild,
                                                avg_distfile, avg_ebuild)))
        for avg, diff in diffs:
            if diff.dest_distfile in taken:
                if taken[diff.dest_distfile][0] > avg:
                    continue
                else:
                    tmp_diffs = []
                    for tmp_diff in self.diffs:
                        if tmp_diff.dest_distfile != diff.dest_distfile:
                            tmp_diffs.append(tmp_diff)
                    self.diffs = tmp_diffs
            self.diffs.append(diff)
            taken[diff.dest_distfile] = (avg, diff)

    def _resolve_distfiles(self):
        self.patches = []
        patches_list = []
        for distfile in self.ebuild.src_uri_map:
            tmp = []
            line = self.deltadb.get_by_dest(distfile)
            while len(line) > 0:
                if line[0].dest.fname in self._distfiles_list:
                    break
                tmp.append(line[0])
                line = self.deltadb.get_by_dest(line[0].src.fname)
            patches_list.append(tmp)
        for records in patches_list:
            if len(records) == 0:
                continue
            records = list(reversed(records))
            self.patches.append(Patch(*records))

    def diff(self, atom):
        self.ebuilds = OrderedDict()
        for cpv in dbapi.match(atom):
            self.ebuilds[cpv] = Ebuild(cpv)
        self._lineage_identification()

    def patch(self, cpv, output_dir=None):
        if output_dir is None:
            output_dir = portage.settings['DISTDIR']
        self.ebuild = Ebuild(cpv)
        self._distfiles_list = []
        if os.path.isdir(output_dir):
            self._distfiles_list += os.listdir(output_dir)
        delta_dir = os.path.join(output_dir, 'delta-reconstructed')
        if os.path.isdir(delta_dir):
            self._distfiles_list += os.listdir(delta_dir)
        self._resolve_distfiles()

    def fetch_distfiles(self):
        for diff in self.diffs:
            diff.fetch_distfiles()
