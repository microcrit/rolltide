import json
import os
import subprocess
import shutil


class CodeGeneratorPROS:
    def __init__(self):
        self.architecture = "PROS V5"
        self.version = "PROS V5 Project"

    def generate_code(self, ir, outdir='out'):
        os.makedirs(outdir, exist_ok=True)
        meta = {
            'arch': self.architecture,
            'version': self.version,
            'modules': ir.get('modules', []) if isinstance(ir, dict) else [],
        }
        out_file = os.path.join(outdir, 'pros_metadata.json')
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
        print(f"PROS metadata -> {out_file}")
        modules = meta.get('modules', [])
        _generate_common_build_files(modules, outdir=outdir, target='pros')
        _generate_pros_callbacks(modules, outdir=outdir)
        if shutil.which('prosv5'):
            print('PROS CLI detected: prosv5 is available on PATH')
        else:
            print('PROS CLI not detected.')


class CodeGeneratorIR:
    def __init__(self):
        self.architecture = "Generic IR"
        self.version = "1.0"

        self.backends = {
            'pe': CodeGeneratorCPPWindowsX86_64,
            'elf': CodeGeneratorCPPLinuxX86_64,
            'pros': CodeGeneratorPROS,
        }

    def generate_code(self, ir, outdir='out'):
        arch = getattr(self, 'architecture', 'pros')
        print(f"Generating code for target: {arch}")
        if arch in self.backends:
            generator_cls = self.backends[arch]
            gen = generator_cls()
            gen.generate_code(ir, outdir=outdir)
        else:
            print(f"Unknown backend: {arch}. Supported: {list(self.backends.keys())}")


class CodeGeneratorCPPWindowsX86_64:
    def __init__(self):
        self.architecture = "x86-64"
        self.version = "C++ Windows"

    def generate_code(self, ir, outdir='out'):
        os.makedirs(outdir, exist_ok=True)
        meta = {
            'arch': self.architecture,
            'version': self.version,
            'modules': ir.get('modules', []) if isinstance(ir, dict) else [],
        }
        out_file = os.path.join(outdir, 'cpp_windows_x86_64_metadata.json')
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
        print(f"C++ Windows x86-64 metadata -> {out_file}")
        modules = meta.get('modules', [])
        _generate_common_build_files(modules, outdir=outdir, target='windows')
        try:
            _compile_native_project(outdir, 'windows')
        except Exception as e:
            print(f"Native compilation failed: {e}")

class CodeGeneratorCPPLinuxX86_64:
    def __init__(self):
        self.architecture = "x86-64"
        self.version = "C++ Linux"

    def generate_code(self, ir, outdir='out'):
        os.makedirs(outdir, exist_ok=True)
        meta = {
            'arch': self.architecture,
            'version': self.version,
            'modules': ir.get('modules', []) if isinstance(ir, dict) else [],
        }
        out_file = os.path.join(outdir, 'cpp_linux_x86_64_metadata.json')
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
        print(f"C++ Linux x86-64 metadata -> {out_file}")
        modules = meta.get('modules', [])
        _generate_common_build_files(modules, outdir=outdir, target='linux')
        try:
            _compile_native_project(outdir, 'linux')
        except Exception as e:
            print(f"Native compilation failed: {e}")


def _generate_common_build_files(modules, outdir='out', target='linux'):
    os.makedirs(outdir, exist_ok=True)
    src_dir = os.path.join(outdir, 'src')
    inc_dir = os.path.join(outdir, 'include')
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(inc_dir, exist_ok=True)

    if target == 'pros':
        manifest = {
            "name": os.path.basename(os.path.abspath(outdir)),
            "version": "0.1.0",
            "prosversion": 5,
            "license": "MIT",
            "targets": ["v5"],
        }
        with open(os.path.join(outdir, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

    def map_type(t):
        if not t:
            return 'void'
        t = str(t)
        # handle mutable reference syntax from RollTide '&mut Type'
        if t.startswith('&mut '):
            base = t[len('&mut '):]
            # map to pointer type
            return map_type(base) + '*'
        if t.startswith('unsigned:'):
            base = t[len('unsigned:'):]
            if base == 'int':
                return 'unsigned int'
            return f'unsigned {base}'
        # Numeric aliases
        if t in ('int', 'i32'):
            return 'int32_t'
        if t in ('i16', 'i8'):
            return 'int'
        if t in ('long', 'i64'):
            return 'long'
        if t in ('u32', 'unsigned int'):
            return 'unsigned int'
        if t in ('u16', 'u8', 'byte'):
            return 'unsigned char'
        if t in ('f32', 'float'):
            return 'float'
        if t in ('f64', 'double'):
            return 'double'
        if t.lower() in ('string', 'str', 'string*'):
            return 'const char*'
        if t == 'pointer' or t == 'void*':
            return 'void*'
        if t.startswith('byte['):
            return 'uint8_t*'
        return t

    with open(os.path.join(inc_dir, 'main.h'), 'w', encoding='utf-8') as mh:
        mh.write('#pragma once\n')
        mh.write('#include <cstdint>\n')
        mh.write('#include <cstdio>\n')
        mh.write('\n// Forward declarations for common runtime/formatting types\n')
        mh.write('struct Formatter;\n')
        written_defs = set()
        for m in modules:
            for d in m.get('defs', []):
                if d.get('type') == 'struct':
                    if d.get('name') in written_defs:
                        continue
                    written_defs.add(d.get('name'))
                    mh.write(f'struct {d.get("name")} ' + '{\n')
                    for fld in d.get('fields', []):
                        fname = fld.get('name') or 'field'
                        ftype = None
                        if fld.get('type'):
                            if isinstance(fld.get('type'), dict):
                                base = fld.get('type').get('base')
                                if fld.get('type').get('array_length'):
                                    ftype = f'{map_type(base)}*'
                                else:
                                    ftype = map_type(base)
                            else:
                                ftype = map_type(fld.get('type'))
                        else:
                            ftype = 'int'
                        mh.write(f'  {ftype} {fname};\n')
                    mh.write('};\n\n')
                if d.get('type') == 'enum':
                    if d.get('name') in written_defs:
                        continue
                    written_defs.add(d.get('name'))
                    mh.write(f'enum class {d.get("name")} ' + '{\n')
                    for mem in d.get('members', []):
                        if isinstance(mem, dict):
                            if mem.get('value') is not None:
                                mh.write(f'  {mem.get("name")} = {mem.get("value")},\n')
                            else:
                                mh.write(f'  {mem.get("name")},\n')
                        elif isinstance(mem, str):
                            mh.write(f'  {mem},\n')
                    mh.write('};\n\n')
                if d.get('type') == 'val':
                    try:
                        value_expr = d.get('expr')
                        if isinstance(value_expr, list) and len(value_expr) == 1 and isinstance(value_expr[0], str):
                            mh.write(f'extern const auto {d.get("name")} = "{value_expr[0]}";\n')
                        else:
                            mh.write(f'extern const int {d.get("name")} = 0;\n')
                    except Exception:
                        mh.write(f'extern const int {d.get("name")} = 0;\n')

    with open(os.path.join(src_dir, 'main.cpp'), 'w', encoding='utf-8') as mc:
        mc.write('#include "main.h"\n')
        mc.write('#include <iostream>\n\n')
        mc.write('int main() {\n')
        mc.write('  std::cout << "Hello from generated project!" << std::endl;\n')
        mc.write('  return 0;\n')
        mc.write('}\n')

    for m in modules:
        mod_name = m.get('module', 'module')
        base = mod_name.replace('.', '_')
        header_name = f'{base}.h' if base != 'main' else 'module_main.h'
        header_path = os.path.join(inc_dir, header_name)
        cpp_path = os.path.join(src_dir, f'{base}.cpp')
        with open(header_path, 'w', encoding='utf-8') as hh:
            hh.write('#pragma once\n')
            hh.write('#include "main.h"\n')
            for d in m.get('defs', []):
                if d.get('type') == 'fn':
                    header_info = d.get('header') or {}
                    ret = map_type(header_info.get('ret')) if header_info.get('ret') else (map_type(d.get('ret_type')) if d.get('ret_type') else 'void')
                    args = []
                    for a in (d.get('args') or []):
                        if a.get('vararg'):
                            args.append('...')
                        else:
                            args.append(f"{map_type(a.get('type'))} {a.get('name') or 'arg'}")
                    fn_ident = header_info.get('ident') or d.get('name')
                    if not header_info.get('ident') and d.get('owner'):
                        fn_ident = f"{d.get('owner')}_{fn_ident}"
                    # if ident contains namespace qualifiers like pros::delay, emit wrapped namespace prototype
                    if '::' in fn_ident:
                        ns, ident_name = fn_ident.rsplit('::', 1)
                        hh.write(f'namespace {ns} {{ {ret} {ident_name}({", ".join(args)}); }}\n')
                    else:
                        hh.write(f'{ret} {fn_ident}({", ".join(args)});\n')
        with open(cpp_path, 'w', encoding='utf-8') as cc:
            cc.write('#include "main.h"\n')
            cc.write(f'#include "{base}.h"\n\n')
            for d in m.get('defs', []):
                if d.get('type') == 'fn':
                    header_info = d.get('header') or {}
                    ret = map_type(header_info.get('ret')) if header_info.get('ret') else (map_type(d.get('ret_type')) if d.get('ret_type') else 'void')
                    args = []
                    for a in (d.get('args') or []):
                        if a.get('vararg'):
                            args.append('...')
                        else:
                            args.append(f"{map_type(a.get('type'))} {a.get('name') or 'arg'}")
                    fn_ident = header_info.get('ident') or d.get('name')
                    if not header_info.get('ident') and d.get('owner'):
                        fn_ident = f"{d.get('owner')}_{fn_ident}"
                    cc.write(f'{ret} {fn_ident}({", ".join(args)})' + ' {\n')
                    cc.write('  // TODO: fill in generated function\n')
                    if ret != 'void':
                        if ret in ('int', 'long', 'unsigned int'):
                            cc.write('  return 0;\n')
                        else:
                            cc.write('  return ({})0;\n'.format(ret))
                    cc.write('}\n\n')
                if d.get('type') == 'defc':
                    for mbr in d.get('members', []):
                        if mbr.get('type') == 'struct':
                            hh.write(f'struct {mbr.get("name")} ' + '{\n')
                            for fld in mbr.get('fields', []):
                                fname = fld.get('name') or 'field'
                                ftype = 'int'
                                if fld.get('type'):
                                    if isinstance(fld.get('type'), dict):
                                        base = fld.get('type').get('base')
                                        if fld.get('type').get('array_length'):
                                            ftype = f'{map_type(base)}*'
                                        else:
                                            ftype = map_type(base)
                                    else:
                                        ftype = map_type(fld.get('type'))
                                hh.write(f'  {ftype} {fname};\n')
                            hh.write('};\n\n')
                        if mbr.get('type') == 'fn':
                            header_info = mbr.get('header') or {}
                            ret = map_type(header_info.get('ret')) if header_info.get('ret') else (map_type(mbr.get('ret_type')) if mbr.get('ret_type') else 'void')
                            args = []
                            for a in (mbr.get('args') or []):
                                if a.get('vararg'):
                                    args.append('...')
                                else:
                                    args.append(f"{map_type(a.get('type'))} {a.get('name') or 'arg'}")
                            fn_ident = header_info.get('ident') or mbr.get('name')
                            if not header_info.get('ident') and d.get('name'):
                                fn_ident = f"{d.get('name')}_{fn_ident}"
                            hh.write(f'{ret} {fn_ident}({", ".join(args)});\n')
                            fn_ident = header_info.get('ident') or mbr.get('name')
                            cc.write(f'{ret} {fn_ident}({", ".join(args)})' + ' {\n')
                            cc.write('  // TODO: fill in generated defc member function\n')
                            if ret != 'void':
                                if ret in ('int', 'long', 'unsigned int'):
                                    cc.write('  return 0;\n')
                                else:
                                    cc.write('  return ({})0;\n'.format(ret))
                            cc.write('}\n\n')
                if d.get('type') == 'val':
                    if isinstance(d.get('expr'), list) and len(d.get('expr')) == 1 and isinstance(d.get('expr')[0], str):
                        cc.write(f'const auto {d.get("name")} = std::string("{d.get("expr")[0]}");\n')
                    else:
                        cc.write(f'const int {d.get("name")} = 0;\n')

    with open(os.path.join(outdir, 'Makefile'), 'w', encoding='utf-8') as mk:
        mk.write('# Auto-generated Makefile\n')
        mk.write('CXX ?= g++\n')
        mk.write('CXXFLAGS ?= -std=c++17 -O2 -Iinclude\n')
        mk.write('SRCS := $(wildcard src/*.cpp)\n')
        mk.write('OBJS := $(SRCS:.cpp=.o)\n')
        mk.write('TARGET := bin/project\n\n')
        mk.write('all: $(TARGET)\n\n')
        mk.write('$(TARGET): $(OBJS)\n')
        mk.write('\t$(CXX) $(CXXFLAGS) -o $@ $^\n\n')
        mk.write('clean:\n')
        if os.name == 'nt':
            mk.write('\tif exist $(OBJS) del /Q $(OBJS)\n')
            mk.write('\tif exist $(TARGET) del /Q $(TARGET)\n')
        else:
            mk.write('\trm -rf $(OBJS) $(TARGET)\n')
        if target == 'pros':
            mk.write('\n# PROS targets\n')
            mk.write('prosv5 := $(shell command -v prosv5 2>/dev/null || true)\n')
            mk.write('prosv5-compile:\n')
            mk.write('\t@if [ -n "$(prosv5)" ]; then prosv5 c compile; else echo "prosv5 CLI not found"; fi\n')
            mk.write('prosv5-upload:\n')
            mk.write('\t@if [ -n "$(prosv5)" ]; then prosv5 c upload project; else echo "prosv5 CLI not found"; fi\n')

    with open(os.path.join(outdir, 'CMakeLists.txt'), 'w', encoding='utf-8') as cm:
        cm.write('cmake_minimum_required(VERSION 3.5)\n')
        cm.write(f'project({os.path.basename(os.path.abspath(outdir))})\n')
        cm.write('add_executable(project src/main.cpp')
        for f in os.listdir(src_dir):
            if f.endswith('.cpp') and f != 'main.cpp':
                cm.write(' src/' + f)
        cm.write(')\n')
        cm.write('target_include_directories(project PRIVATE include)\n')

    with open(os.path.join(outdir, 'Justfile'), 'w', encoding='utf-8') as jf:
        jf.write('set shell := ["bash", "-cu"]\n\n')
        jf.write('build:\n')
        jf.write('\t@echo Building...\n')
        jf.write('\t@make\n\n')
        jf.write('clean:\n')
        jf.write('\t@make clean\n\n')
        jf.write('flash:\n')
        jf.write('\t@echo Flashing via PROS CLI (if available)\n')
        jf.write('\t@if command -v prosv5 >/dev/null 2>&1; then prosv5 c compile && prosv5 c upload project; else echo "prosv5 not found"; fi\n')

    build_sh = os.path.join(outdir, 'build.sh')
    with open(build_sh, 'w', encoding='utf-8') as bs:
        bs.write('#!/usr/bin/env bash\nset -e\nmake\n')
    try:
        os.chmod(build_sh, 0o755)
    except Exception:
        pass

    build_bat = os.path.join(outdir, 'build.bat')
    with open(build_bat, 'w', encoding='utf-8') as bb:
        bb.write('@echo off\n')
        bb.write('if not exist bin mkdir bin\n')
        if target == 'pros':
            bb.write('prosv5 c compile\n')
            bb.write('if %errorlevel% neq 0 (\n')
            bb.write('  echo PROS build failed.\n')
            bb.write('  exit /b %errorlevel%\n')
            bb.write(') else (\n')
            bb.write('  prosv5 c upload project\n')
            bb.write(')\n')
        else:
            bb.write('make\n')
            bb.write('if %errorlevel% neq 0 (\n')
            bb.write('  echo Build failed.\n')
            bb.write('  exit /b %errorlevel%\n')
            bb.write(')\n')

    print(f'Common build files written to {outdir}')


def _generate_pros_callbacks(modules, outdir):
    src_dir = os.path.join(outdir, 'src')
    inc_dir = os.path.join(outdir, 'include')
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(inc_dir, exist_ok=True)

    main_cpp = os.path.join(src_dir, 'main.cpp')
    with open(main_cpp, 'w', encoding='utf-8') as mc:
        mc.write('#include "main.h"\n')
        mc.write('#include <pros/apix.h>\n')
        mc.write('#include <iostream>\n\n')
        mc.write('void initialize() {\n')
        mc.write('  // called when the robot is powered on or the program is started\n')
        mc.write('  std::cout << "Robot initializing" << std::endl;\n')
        mc.write('}\n\n')
        mc.write('void disabled() {\n')
        mc.write('  // disabled callback\n')
        mc.write('}\n\n')
        mc.write('void competition_initialize() {\n')
        mc.write('  // called once when starting in competition mode\n')
        mc.write('}\n\n')
        mc.write('void autonomous() {\n')
        mc.write('  // autonomous code here\n')
        mc.write('}\n\n')
        mc.write('void opcontrol() {\n')
        mc.write('  // operator control (driver control) loop here\n')
        mc.write('  while (true) {\n')
        mc.write('    pros::delay(10);\n')
        mc.write('  }\n')
        mc.write('}\n')


def _compile_native_project(outdir, target_os: str):
    """Attempt to compile the generated native project on the current host.
    Uses g++ for Linux/macOS and g++/cl for Windows if available. Returns the path to the binary if successful.
    """
    src_dir = os.path.join(outdir, 'src')
    bin_dir = os.path.join(outdir, 'bin')
    os.makedirs(bin_dir, exist_ok=True)
    cxx = shutil.which('g++') or shutil.which('clang++')
    if not cxx and os.name == 'nt':
        cxx = shutil.which('cl')
    if not cxx:
        raise RuntimeError('No supported C++ compiler found (g++, clang++, or cl).')

    srcs = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith('.cpp')]
    if not srcs:
        raise RuntimeError('No .cpp source files to compile')

    outbin = os.path.join(bin_dir, 'project.exe' if os.name == 'nt' else 'project')
    if 'cl' in os.path.basename(cxx):
        cmd = [cxx, '/EHsc', '/std:c++17'] + srcs + ['/Fe' + outbin]
    else:
        cmd = [cxx, '-std=c++17', '-O2', '-I' + os.path.join(outdir, 'include'), '-o', outbin] + srcs

    print(f'Native project: {cmd}')
    subprocess.run(cmd, check=True)
    print(f'Compiled binary -> {outbin}')
    return outbin