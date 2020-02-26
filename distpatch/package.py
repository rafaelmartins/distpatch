# -*- coding: utf-8 -*-
"""
    distpatch.package
    ~~~~~~~~~~~~~~~~~

    High-level interface for delta generation and distfile reconstruction.

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

import os
import portage

from collections import OrderedDict

from distpatch.diff import Diff, DiffUnsupported
from distpatch.ebuild import Distfile, Ebuild
from distpatch.patch import Patch

dbapi = portage.create_trees()[portage.settings['ROOT']]['porttree'].dbapi


class PackageException(Exception):
    pass


class Package(object):

    def __init__(self, deltadb):
        self.deltadb = deltadb

    def _lineage_identification(self):
        self.diffs = []
        diffs = []
        taken = {}
        for ebuild_id in range(len(self.ebuilds) - 1):
            cpvs = list(self.ebuilds.keys())
            src_cpv = cpvs[ebuild_id]
            dest_cpv = cpvs[ebuild_id + 1]
            src_ebuild = self.ebuilds[src_cpv]
            dest_ebuild = self.ebuilds[dest_cpv]
            for src_distfile in list(src_ebuild.src_uri_map.keys()):
                avg_distfile = None
                avg_ebuild = None
                max_avg = 0.0
                avgs = {}
                for dest_distfile in list(dest_ebuild.src_uri_map.keys()):
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
                    diffs.append((max_avg, Diff(Distfile(src_distfile,
                                                         src_ebuild),
                                                Distfile(avg_distfile,
                                                         avg_ebuild))))
        for avg, diff in diffs:
            if diff.dest.fname in taken:
                if taken[diff.dest.fname][0] > avg:
                    continue
                else:
                    tmp_diffs = []
                    for tmp_diff in self.diffs:
                        if tmp_diff.dest.fname != diff.dest.fname:
                            tmp_diffs.append(tmp_diff)
                    self.diffs = tmp_diffs
            self.diffs.append(diff)
            taken[diff.dest.fname] = (avg, diff)

    def _distfiles_list(self, output_dir):
        if output_dir is None:
            output_dir = portage.settings['DISTDIR']
        distfiles_list = []
        if os.path.isdir(output_dir):
            distfiles_list += os.listdir(output_dir)
        delta_dir = os.path.join(output_dir, 'delta-reconstructed')
        if os.path.isdir(delta_dir):
            distfiles_list += os.listdir(delta_dir)
        return distfiles_list

    def diff(self, atom):
        self.ebuilds = OrderedDict()
        for cpv in dbapi.match(atom):
            self.ebuilds[cpv] = Ebuild(cpv)
        self._lineage_identification()
        _diffs = self.diffs[:]
        self.diffs = []
        for diff in _diffs:
            try:
                diff.validate_distfiles()
            except DiffUnsupported:
                pass
            else:
                self.diffs.append(diff)

    def patch(self, cpv, output_dir=None):
        self.patches = []
        ebuild = Ebuild(cpv)
        distfiles = self._distfiles_list(output_dir)
        hops_list = []
        for distfile in ebuild.src_uri_map:
            hops = []
            dbline = self.deltadb.get_by_dest(distfile)
            while len(dbline) > 0:
                if dbline[0].dest.fname in distfiles:
                    break
                hops.append(dbline[0])
                dbline = self.deltadb.get_by_dest(dbline[0].src.fname)
            hops.reverse()
            if len(hops) > 0 and hops[0].src.fname in distfiles:
                hops_list.append(hops)
        for hops in hops_list:
            if len(hops) > 0:
                self.patches.append(Patch(*hops))
        return self.patches

    def patch_distfile(self, distfile, output_dir=None):
        self.patches = []
        distfiles = self._distfiles_list(output_dir)
        hops = []
        dbline = self.deltadb.get_by_dest(distfile)
        while len(dbline) > 0:
            if dbline[0].dest.fname in distfiles:
                break
            hops.append(dbline[0])
            dbline = self.deltadb.get_by_dest(dbline[0].src.fname)
        hops.reverse()
        if len(hops) == 0 or hops[0].src.fname not in distfiles:
            return
        self.patches.append(Patch(*hops))

    def fetch_distfiles(self):
        fetched = []
        for diff in self.diffs:
            if diff.src.fname not in fetched:
                diff.src.fetch()
                fetched.append(diff.src.fname)
            if diff.dest.fname not in fetched:
                diff.dest.fetch()
                fetched.append(diff.dest.fname)


# used by distdiffer --all
cp_all = dbapi.cp_all
