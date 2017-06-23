from setuptools import setup, find_packages
from distutils.extension import Extension
from Cython.Build import cythonize
import os

import numpy

moscalibdir = os.path.join("mosca", "lib")

corelib_c       = os.path.join(moscalibdir, "_corelib.c")
corelib_pyx     = os.path.join(moscalibdir, "corelib.pyx")
corelib_link    = []
if os.name == "posix":
    corelib_link += ['pthread']

corelib = Extension('mosca.lib.corelib',
                        sources      = [corelib_c, corelib_pyx],
                        include_dirs = [".", moscalibdir],
                        libraries    = corelib_link )


ni_dir = os.path.join("C:","\Program Files (x86)",
                        "National Instruments",
                        "Shared",
                        "ExternalCompilerSupport",
                        "C")
ni_lib = "NIDAQmx"
ni_libdir = os.path.join(ni_dir,
                        "lib64",
                        "msvc")
ni_include = os.path.join(ni_dir,
                            "include")
ni_pyx = os.path.join(moscalibdir, "NI.pyx")

nidriver = Extension("mosca.lib.NI",
                    sources     =[corelib_c, ni_pyx],
                    include_dirs=[
                        numpy.get_include(),
                        ni_include
                    ],
                    library_dirs = [
                        ni_libdir
                    ],
                    libraries   =[
                        ni_lib
                    ])

extensions = [ corelib, nidriver ]

setup(
    packages    = find_packages(),
    ext_modules = cythonize(extensions)
)
