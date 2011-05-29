#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distpatch.diff import DiffException
from distpatch.ebuild import EbuildException
from distpatch.package import Package, PackageException
from distpatch.patch import PatchException

import argparse
import os
import sys

parser = argparse.ArgumentParser(
    description='Creates binary deltas for distfiles of Gentoo Linux packages')

# positional arguments
parser.add_argument('packages', metavar='package-atom', nargs='*',
                    help='Package atoms')

# optional arguments
parser.add_argument('-o', '--output', dest='output_dir', metavar='DIR',
                    default=os.getcwd(), help='Output directory (default: ' \
                    'current directory)')
parser.add_argument('-f', '--file', dest='packages_file', metavar='FILE',
                    help='Read package atoms from a line-separated file. ' \
                    'This option will ignore `package-atom` arguments')
parser.add_argument('--stdin', dest='stdin', action='store_true', help='Read ' \
                    'line-separated package atoms from stdin. This option will ' \
                    'ignore `package-atom` arguments and `--file`')
parser.add_argument('-c', '--no-compress', dest='no_compress', action='store_true',
                    help='Disable the compression of generated deltas with xz(1)')
parser.add_argument('-p', '--preserve', dest='preserve', action='store_true',
                    help='Preserve the uncompressed sources in the output directory')

def main():
    args = parser.parse_args()

    # get the list of packages to be processed
    packages = args.packages[:]
    if args.stdin:
        packages = []
        for line in sys.stdin:
            packages.append(line.strip())
    elif args.packages_file is not None:
        if not os.path.isfile(args.packages_file):
            parser.error('invalid file: %s' % args.packages_file)
        packages = []
        with open(args.packages_file) as fp:
            for line in fp:
                packages.append(line.strip())
    
    if len(packages) == 0:
        parser.print_help()
    
    for package in packages:
        pkg = Package(package)
        for diff in pkg.diffs:
            diff.generate(args.output_dir, not args.preserve, not args.no_compress)

if __name__ == '__main__':
    main()