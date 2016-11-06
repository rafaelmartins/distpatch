# -*- coding: utf-8 -*-
"""
    distpatch.ebuild
    ~~~~~~~~~~~~~~~~

    Module to abstract ebuild/distfile interfaces.

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

import os
import portage

from collections import OrderedDict

from portage.dbapi.porttree import _parse_uri_map
from portage.package.ebuild.fetch import fetch

dbapi = portage.create_trees()[portage.settings['ROOT']]['porttree'].dbapi


class EbuildException(Exception):
    pass


class DistfileException(Exception):
    pass


class Ebuild(object):

    def __init__(self, cpv):
        if not dbapi.cpv_exists(cpv):
            raise EbuildException('Invalid CPV: %s' % cpv)
        self.cpv = cpv

    @property
    def eapi(self):
        try:
            return int(dbapi.aux_get(self.cpv, ['EAPI'])[0])
        except:
            return 0

    @property
    def src_uri(self):
        return ' '.join(dbapi.aux_get(self.cpv, ['SRC_URI']))

    @property
    def src_uri_map(self):
        return _parse_uri_map(self.cpv, {
            'EAPI': self.eapi,
            'SRC_URI': self.src_uri,
        })

    def fetch(self, myfile=None):
        mysettings = portage.config(clone=portage.settings)
        mysettings['O'] = os.path.dirname(dbapi.findname(self.cpv))
        available_files = self.src_uri_map
        if myfile is None:
            files = available_files
        else:
            if myfile not in available_files:
                raise EbuildException('Invalid distfile: %s' % myfile)
            files = OrderedDict()
            files[myfile] = available_files[myfile]
        if 'distpatch' in mysettings.features:
            mysettings.features.remove('distpatch')
        if not fetch(files, mysettings, allow_missing_digests=False):
            raise EbuildException('Failed to fetch distfiles for %s' % self.cpv)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.cpv)


class Distfile(object):

    def __init__(self, fname, ebuild):
        self.fname = os.path.basename(fname)
        if not isinstance(ebuild, Ebuild):
            raise DistfileException('Invalid %s object: %r' % \
                                    (Ebuild.__name__, ebuild))
        self.ebuild = ebuild

    def fetch(self):
        self.ebuild.fetch(self.fname)

    def __repr__(self):
        return '<%s %s from %s>' % (self.__class__.__name__, self.fname,
                                    self.ebuild)
