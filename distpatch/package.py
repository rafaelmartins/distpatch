# -*- coding: utf-8 -*-

from collections import OrderedDict
from diff import Diff
from ebuild import Ebuild
from patch import Patch

import os
import portage

dbapi = portage.db[portage.settings['ROOT']]['porttree'].dbapi

class PackageException(Exception):
    pass


class Package:
    
    def __init__(self, atom, deltadb):
        self.atom = atom
        self.deltadb = deltadb
        self.ebuilds = OrderedDict()
        for cpv in dbapi.match(atom):
            self.ebuilds[cpv] = Ebuild(cpv)

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
                        if src_distfile[-i-1] == dest_distfile[-i-1]:
                            suffix = src_distfile[-i-1] + suffix
                        else:
                            break
                    avg = float(len(prefix) + len(suffix))/2
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
        patches_dict = OrderedDict()
        for cpv, ebuild in self.ebuilds.iteritems():
            patches_dict[cpv] = []
            for distfile in ebuild.src_uri_map:
                tmp = []
                line = self.deltadb.get_by_dest(distfile)
                while len(line) > 0:
                    if line[0].dest.fname in self._distfiles_list:
                        break
                    tmp.append(line[0])
                    line = self.deltadb.get_by_dest(line[0].src.fname)
                patches_dict[cpv].append(tmp)
        self.patches = []
        for cpv, records_list in patches_dict.iteritems():
            for records in records_list:
                if len(records) == 0:
                    continue
                records = list(reversed(records))
                self.patches.append(Patch(*records))

    def diff(self):
        self._lineage_identification()

    def patch(self):
        self._distfiles_list = os.listdir(portage.settings['DISTDIR'])
        self._resolve_distfiles()

    def fetch_distfiles(self):
        for diff in self.diffs:
            diff.fetch_distfiles()
