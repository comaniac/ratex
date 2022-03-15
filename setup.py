#!/usr/bin/env python
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Modifications Copyright (c) Facebook, Inc

# Environment variable you must set:
#
#   PYTORCH_SOURCE_PATH
#     the path to the PyTorch source
#
# Environment variables you are probably interested in:
#
#   DEBUG
#     build with -O0 and -g (debug symbols)
#
#   RAZOR_VERSION
#     specify the version, rather than the hard-coded version
#     in this file; used when we're building binaries for distribution
#
#   RELEASE_VERSION=0
#     create a release version (i.e., a version with no "+git" suffix)
#
#   COMPILE_PARALLEL=1
#     enable parallel compile
#
#   BUILD_CPP_TESTS=1
#     build the C++ tests
#

from __future__ import print_function
import glob2

from setuptools import setup, find_packages, distutils
from torch.utils.cpp_extension import BuildExtension, CppExtension
import distutils.ccompiler
import distutils.command.clean
import inspect
import multiprocessing
import multiprocessing.pool
import os
import platform
import re
import shutil
import subprocess
import sys
import site
import torch

import tvm
import raf

base_dir = os.path.dirname(os.path.abspath(__file__))
pytorch_source_dir = os.getenv("PYTORCH_SOURCE_PATH", None)
if pytorch_source_dir is None:
    raise RuntimeError("PYTORCH_SOURCE_PATH is unset")


def _get_build_mode():
    for i in range(1, len(sys.argv)):
        if not sys.argv[i].startswith("-"):
            return sys.argv[i]


def _check_env_flag(name, default=""):
    return os.getenv(name, default).upper() in ["ON", "1", "YES", "TRUE", "Y"]


def get_git_head_sha(base_dir):
    razor_git_sha = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=base_dir)
        .decode("ascii")
        .strip()
    )
    if os.path.isdir(os.path.join(pytorch_source_dir, ".git")):
        torch_git_sha = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=pytorch_source_dir)
            .decode("ascii")
            .strip()
        )
    else:
        torch_git_sha = ""
    return razor_git_sha, torch_git_sha


def get_build_version(razor_git_sha):
    version = os.getenv("RAZOR_VERSION", "0.1")
    if not _check_env_flag("RELEASE_VERSION", default="0"):
        version += "+git" + razor_git_sha
    return version


def create_version_files(base_dir, version, torch_git_sha):
    raf_version = raf.__version__
    torch_version = torch.__version__
    print("Building Razor version: {}".format(version))
    print("RAF version: {}".format(raf_version))
    print("PyTorch version: {}".format(torch_version))
    print("PyTorch commit ID: {}".format(torch_git_sha))
    py_version_path = os.path.join(base_dir, "razor", "version.py")
    with open(py_version_path, "w") as f:
        f.write('"""Autogenerated file, do not edit!"""\n')
        f.write("__version__ = '{}'\n".format(version))
        f.write("__raf_version__ = '{}'\n".format(raf_version))
        f.write("__torch_version__ = '{}'\n".format(torch_version))
        f.write("__torch_gitrev__ = '{}'\n".format(torch_git_sha))

    cpp_version_path = os.path.join(base_dir, "razor", "csrc", "version.cpp")
    with open(cpp_version_path, "w") as f:
        f.write("// Autogenerated file, do not edit!\n")
        f.write('#include "razor/csrc/version.h"\n\n')
        f.write("namespace razor {\n\n")
        f.write('const char RAF_VERSION[] = {{"{}"}};\n'.format(raf_version))
        f.write('const char TORCH_VERSION[] = {{"{}"}};\n'.format(torch_version))
        f.write('const char TORCH_GITREV[] = {{"{}"}};\n\n'.format(torch_git_sha))
        f.write("}  // namespace razor\n")


def generate_raf_aten_code(base_dir):
    generate_code_cmd = [os.path.join(base_dir, "scripts", "generate_code.sh")]
    if subprocess.call(generate_code_cmd, env=dict(os.environ, PTDIR=str(pytorch_source_dir))) != 0:
        print("Failed to generate ATEN bindings: {}".format(generate_code_cmd), file=sys.stderr)
        sys.exit(1)


def _compile_parallel(
    self,
    sources,
    output_dir=None,
    macros=None,
    include_dirs=None,
    debug=0,
    extra_preargs=None,
    extra_postargs=None,
    depends=None,
):
    # Those lines are copied from distutils.ccompiler.CCompiler directly.
    macros, objects, extra_postargs, pp_opts, build = self._setup_compile(
        output_dir, macros, include_dirs, sources, depends, extra_postargs
    )
    cc_args = self._get_cc_args(pp_opts, debug, extra_preargs)

    def compile_one(obj):
        try:
            src, ext = build[obj]
        except KeyError:
            return
        self._compile(obj, src, ext, cc_args, extra_postargs, pp_opts)

    list(multiprocessing.pool.ThreadPool(multiprocessing.cpu_count()).imap(compile_one, objects))
    return objects


# Plant the parallel compile function.
if _check_env_flag("COMPILE_PARALLEL", default="1"):
    try:
        if inspect.signature(distutils.ccompiler.CCompiler.compile) == inspect.signature(
            _compile_parallel
        ):
            distutils.ccompiler.CCompiler.compile = _compile_parallel
    except:
        pass


class Clean(distutils.command.clean.clean):
    def run(self):
        import glob
        import re

        with open(".gitignore", "r") as f:
            ignores = f.read()
            pat = re.compile(r"^#( BEGIN NOT-CLEAN-FILES )?")
            for wildcard in filter(None, ignores.split("\n")):
                match = pat.match(wildcard)
                if match:
                    if match.group(1):
                        # Marker is found and stop reading .gitignore.
                        break
                    # Ignore lines which begin with '#'.
                else:
                    for filename in glob.glob(wildcard):
                        try:
                            os.remove(filename)
                        except OSError:
                            shutil.rmtree(filename, ignore_errors=True)

        # It's an old-style class in Python 2.7...
        distutils.command.clean.clean.run(self)


class Build(BuildExtension):
    def run(self):
        # Run the original BuildExtension first. We need this before building
        # the tests.
        BuildExtension.run(self)
        if _check_env_flag("BUILD_CPP_TESTS", default="1"):
            # Build the C++ tests.
            cmd = [os.path.join(base_dir, "test/cpp/run_tests.sh"), "-B"]
            if subprocess.call(cmd) != 0:
                print("Failed to build tests: {}".format(cmd), file=sys.stderr)
                sys.exit(1)


razor_git_sha, torch_git_sha = get_git_head_sha(base_dir)
version = get_build_version(razor_git_sha)
build_mode = _get_build_mode()
if build_mode not in ["clean"]:
    # Generate version info
    create_version_files(base_dir, version, torch_git_sha)
    # Generate the code before globbing!
    generate_raf_aten_code(base_dir)

# Only include necessary abseil files.
source_files = list(
    set(glob2.glob("third_party/abseil-cpp/absl/**/*.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/*_test.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/*_testing.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/benchmarks.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/*_benchmark.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/*_benchmarks.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/spinlock_test_common.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/flags/**/*.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/mutex_nonprod.cc"))
    - set(glob2.glob("third_party/abseil-cpp/absl/**/gaussian_distribution_gentables.cc"))
)

# Add razor files.
source_files += (
    glob2.glob("razor/csrc/*.cpp")
    + glob2.glob("razor/csrc/ops/*.cpp")
    + glob2.glob("razor/csrc/compiler/*.cpp")
    + glob2.glob("razor/csrc/serialization/*.cpp")
    + glob2.glob("razor/csrc/value_ext/*.cpp")
    + glob2.glob("razor/csrc/pass_ext/*.cpp")
    + glob2.glob("razor/csrc/utils/*.cpp")
    + glob2.glob("third_party/client/*.cpp")
)

# Add lazy tensor core files.
source_files += (
    glob2.glob("razor/lazy_tensor_core/csrc/*.cpp")
    + glob2.glob("razor/lazy_tensor_core/csrc/compiler/*.cpp")
    + glob2.glob("razor/lazy_tensor_core/csrc/ops/*.cpp")
    + glob2.glob("razor/lazy_tensors/**/*.cc")
)

razor_path = os.path.join(base_dir, "razor")
third_party_path = os.path.join(base_dir, "third_party")

# Setup include directories folders.
include_dirs = [
    base_dir,
    razor_path,
    pytorch_source_dir,
    third_party_path,
    os.path.join(third_party_path, "abseil-cpp"),
    os.path.join(third_party_path, "raf/include"),
    os.path.join(third_party_path, "raf/3rdparty/tvm/include"),
    os.path.join(third_party_path, "raf/3rdparty/tvm/3rdparty/compiler-rt"),
    os.path.join(third_party_path, "raf/3rdparty/tvm/3rdparty/dmlc-core/include"),
    os.path.join(third_party_path, "raf/3rdparty/tvm/3rdparty/dlpack/include"),
]

tvm_library_dir = os.path.dirname(tvm._ffi.libinfo.find_lib_path()[0])
raf_library_dir = os.path.dirname(raf._lib.find_lib_path()[0])
library_dirs = [
    os.path.join(razor_path, "lib"),
    tvm_library_dir,
    raf_library_dir,
]

DEBUG = _check_env_flag("DEBUG")
IS_DARWIN = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def make_relative_rpath(path):
    if IS_DARWIN:
        return "-Wl,-rpath,@loader_path/" + path
    else:
        return "-Wl,-rpath,$ORIGIN/" + path


extra_compile_args = [
    "-std=c++14",
    "-Wno-sign-compare",
    "-Wno-unknown-pragmas",
    "-Wno-deprecated-declarations",
    "-Wno-return-type",
    "-Wunused-macros",
]

if re.match(r"clang", os.getenv("CC", "")):
    extra_compile_args += [
        "-Wno-macro-redefined",
        "-Wno-return-std-move",
    ]

if DEBUG:
    extra_compile_args += ["-O0", "-g"]
else:
    extra_compile_args += ["-DNDEBUG"]

PY_VERSION = "".join(sys.version[:3].split("."))
extra_link_args = [
    "-lraf",
    "-ltvm",
    make_relative_rpath(""),
    "-Wl,-rpath,{}".format(site.getsitepackages()[0]),
] + (["-O0", "-g"] if DEBUG else [])

setup(
    name="razor",
    version=version,
    # Exclude the build files.
    packages=find_packages(exclude=["build"]),
    ext_modules=[
        CppExtension(
            "_RAZORC",
            source_files,
            include_dirs=include_dirs,
            extra_compile_args=extra_compile_args,
            library_dirs=library_dirs,
            extra_link_args=extra_link_args,
        ),
    ],
    data_files=[],
    cmdclass={
        "build_ext": Build,
        "clean": Clean,
    },
    python_requires=">=3.7",
)
