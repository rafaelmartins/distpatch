# -*- coding: utf-8 -*-

from collections import OrderedDict
from portage.dbapi.porttree import _parse_uri_map
from portage.package.ebuild.fetch import fetch

import os
import portage

dbapi = portage.db[portage.settings['ROOT']]['porttree'].dbapi

class EbuildException(Exception):
    pass


class Ebuild:
    
    def __init__(self, cpv):
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
        if not fetch(files, mysettings, allow_missing_digests=False):
            raise EbuildException('Failed to fetch distfiles for %s' % self.cpv)
    
    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.cpv)


if __name__ == '__main__':
    a = Ebuild('sci-electronics/kicad-20090320.1666-r2')
    a.fetch()
