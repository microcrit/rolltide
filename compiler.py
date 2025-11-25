import os
import re
from typing import Dict, List, Any, Optional


class Macro:
    def __init__(self, name: str):
        self.name = name
        self.header = {}


class RTModuleParser:
    def __init__(self, lib_dirs: Optional[List[str]] = None):
        self.lib_dirs = lib_dirs or ['lib']
        self.macros = {}

    def find_file(self, include_name: str) -> Optional[str]:
        include_name = include_name.strip()
        if include_name.startswith('<') and include_name.endswith('>'):
            include_name = include_name[1:-1]
        if include_name.startswith('rt/'):
            include_name = include_name[len('rt/'):]
        for lib in self.lib_dirs:
            path = os.path.join(lib, include_name + '.rt')
            if os.path.exists(path):
                return path
        for lib in self.lib_dirs:
            path = os.path.join(lib, include_name)
            if os.path.exists(path):
                return path
        return None

    def parse(self, files: List[str]) -> Dict[str, Any]:
        modules = []
        visited = set()
        def visit(fpath: str):
            if fpath in visited:
                return
            visited.add(fpath)
            module = {'module': os.path.splitext(os.path.basename(fpath))[0], 'defs': []}
            lines = open(fpath, encoding='utf-8').read().splitlines()
            i = 0
            pending_annotations = []
            pending_header = {}
            while i < len(lines):
                line = lines[i].strip()
                if not line or line.startswith('#'):
                    i += 1
                    continue
                if line.startswith('include '):
                    inc = line.split(' ', 1)[1].strip()
                    if inc.startswith('<') and inc.endswith('>'):
                        inc = inc[1:-1]
                    path = self.find_file(inc)
                    if path:
                        visit(path)
                    i += 1
                    continue
                if line.startswith('macro '):
                    match = re.match(r'macro\s+(@[\w\.]+)', line)
                    name = match.group(1) if match else None
                    macro = Macro(name if name else 'anon')
                    i += 1
                    while i < len(lines) and lines[i].strip().startswith('@'):
                        l = lines[i].strip()
                        m = re.match(r'@header\.(\w+)\s+"([^"]+)"', l)
                        if m:
                            macro.header[m.group(1)] = m.group(2)
                        i += 1
                    self.macros[macro.name] = macro
                    continue
                if line.startswith('@'):
                    if line.startswith('@header.'):
                        m = re.match(r'@header\.(\w+)\s+"([^"]*)"', line)
                        if m:
                            pending_header[m.group(1)] = m.group(2)
                        else:
                            pending_annotations.append(line)
                    else:
                        pending_annotations.append(line)
                    i += 1
                    continue
                if line.startswith('struct '):
                    match = re.match(r'struct\s+(\w+)', line)
                    name = match.group(1) if match else 'Struct'
                    struct = {'type': 'struct', 'name': name, 'fields': []}
                    i += 1
                    while i < len(lines) and lines[i].startswith('  '):
                        fld = lines[i].strip()
                        if not fld:
                            i += 1
                            continue
                        if fld.startswith('@'):
                            i += 1
                            continue
                        m = re.match(r'(\w+)\s*:\s*(.+)', fld)
                        if m:
                            fname, ftype = m.group(1), m.group(2)
                            struct['fields'].append({'name': fname, 'type': ftype})
                        i += 1
                    module['defs'].append(struct)
                    continue
                if line.startswith('into '):
                    match = re.match(r'into\s+(\w+).*', line)
                    target = match.group(1) if match else None
                    i += 1
                    while i < len(lines) and lines[i].startswith('  '):
                        l = lines[i].strip()
                        if l.startswith('def '):
                            fn = self._parse_def(lines, i)
                            i += fn['lines_consumed']
                            fn['type'] = 'fn'
                            fn['owner'] = target
                            if pending_annotations:
                                fn['annotations'] = pending_annotations.copy()
                                pending_annotations.clear()
                            if pending_header:
                                fn['header'] = pending_header.copy()
                                pending_header.clear()
                            module['defs'].append(fn)
                            continue
                        i += 1
                    continue
                if line.startswith('def '):
                    fn = self._parse_def(lines, i)
                    i += fn['lines_consumed']
                    fn['type'] = 'fn'
                    if pending_annotations:
                        fn['annotations'] = pending_annotations.copy()
                        pending_annotations.clear()
                    if pending_header:
                        fn['header'] = pending_header.copy()
                        pending_header.clear()
                    module['defs'].append(fn)
                    continue
                i += 1
            modules.append(module)
        for f in files:
            if not os.path.exists(f):
                raise FileNotFoundError(f)
            visit(os.path.abspath(f))
        return {'modules': modules}

    def _parse_def(self, lines: List[str], start: int) -> Dict[str, Any]:
        header = lines[start].strip()
        m = re.match(r'def\s+(\w+)\s*\[(.*)\]', header)
        name = m.group(1) if m else 'fn'
        args_str = m.group(2) if m else ''
        args = []
        if args_str.strip():
            for a in args_str.split(','):
                a = a.strip()
                if not a:
                    continue
                am = re.match(r'(\w+)\s*:\s*(.+)', a)
                if am:
                    args.append({'name': am.group(1), 'type': am.group(2)})
                else:
                    args.append({'name': 'arg', 'type': a})
        ret = None
        arrow = re.search(r'->\s*(\w+)', header)
        if arrow:
            ret = arrow.group(1)

        i = start + 1
        while i < len(lines) and (lines[i].startswith('  ') or not lines[i].strip()):
            i += 1
        return {'name': name, 'args': args, 'ret_type': ret, 'lines_consumed': i - start}


def build_ir_from_files(files: List[str], lib_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
    parser = RTModuleParser(lib_dirs=lib_dirs)
    ir = parser.parse(files)
    for module in ir['modules']:
        for d in module['defs']:
            if d.get('annotations'):
                for ann in d['annotations']:
                    if ann in parser.macros:
                        d.setdefault('header', {}).update(parser.macros[ann].header)
    return ir


if __name__ == '__main__':
    import sys
    print(build_ir_from_files(sys.argv[1:]))
