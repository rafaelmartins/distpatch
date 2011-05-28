# -*- coding: utf-8 -*-

from collections import OrderedDict
from diff import Diff
from ebuild import Ebuild

import portage

dbapi = portage.db[portage.settings['ROOT']]['porttree'].dbapi

class PackageException(Exception):
    pass


class Package:
    
    def __init__(self, atom):
        self.atom = atom
        self.ebuilds = OrderedDict()
        for cpv in dbapi.match(atom):
            self.ebuilds[cpv] = Ebuild(cpv)
        self._lineage_identification()

    def _lineage_identification_forward(self):
        self.diffs = []
        for ebuild_id in range(len(self.ebuilds) - 1):
            cpvs = self.ebuilds.keys()
            src_cpv = cpvs[ebuild_id]
            dest_cpv = cpvs[ebuild_id + 1]
            src_ebuild = self.ebuilds[src_cpv]
            dest_ebuild = self.ebuilds[dest_cpv]
            for src_distfile in src_ebuild.src_uri_map.keys():
                prefix_max = None
                prefix_maxlen = 0
                for dest_distfile in dest_ebuild.src_uri_map.keys():
                    prefix = ''
                    for i in range(min(len(src_distfile), len(dest_distfile))):
                        if src_distfile[i] == dest_distfile[i]:
                            prefix += src_distfile[i]
                        else:
                            break
                    if len(prefix) > prefix_maxlen:
                        prefix_max = dest_distfile
                        prefix_maxlen = len(prefix)
                if prefix_max is not None and src_distfile != prefix_max:
                    self.diffs.append(Diff(src_distfile, src_ebuild, dest_distfile, dest_ebuild))
    
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
                    diffs.append((max_avg, Diff(src_distfile, src_ebuild, avg_distfile, dest_ebuild)))
        for avg, diff in diffs:
            if diff.dest_distfile in taken:
                if taken[diff.dest_distfile][0] > avg:
                    continue
            self.diffs.append(diff)
            taken[diff.dest_distfile] = (avg, diff)
    
    def fetch_distfiles(self):
        for diff in self.diffs:
            diff.fetch_distfiles()

if __name__ == '__main__':
    a = Package('gentoo-sources')
    #a.fetch_distfiles()
    for diff in a.diffs:
        print diff
        #diff.generate('nginx')
    