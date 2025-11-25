import argparse
import os
import json
from typing import Any, List, Dict

import subprocess
import shutil
from backend import CodeGeneratorIR, _compile_native_project
from compiler import build_ir_from_files

def build_command(args):
	files = args.files
	outdir = args.outdir or 'out'
	target = args.target or 'pros'
	os.makedirs(outdir, exist_ok=True)
	print(f"Building files: {files} => target {target} -> {outdir}")
	ir = build_ir_from_files(files, lib_dirs=['lib'])
	with open(os.path.join(outdir, 'ir.json'), 'w', encoding='utf-8') as f:
		json.dump(ir, f, indent=2)
	gen = CodeGeneratorIR()
	gen.architecture = target
	gen.generate_code(ir, outdir=outdir)
	if args.compile:
		if target in ('elf', 'pe'):
			try:
				_compile_native_project(outdir, 'linux' if target == 'elf' else 'windows')
			except Exception as e:
				print(f"Compilation failed: {e}")
		elif target == 'pros':
			import shutil
			if shutil.which('prosv5'):
				try:
					print('Running prosv5 c compile...')
					subprocess.run(['prosv5', 'c', 'compile'], cwd=outdir, check=True)
				except Exception as e:
					print(f'PROS compile failed: {e}')
			else:
				print('PROS CLI not found; skipping compilation for target pros.')


def main():
	parser = argparse.ArgumentParser(prog='rolltide')
	sub = parser.add_subparsers(dest='command')
	buildp = sub.add_parser('build', help='Build RollTide sources')
	buildp.add_argument('files', nargs='+', help='RollTide source files to compile')
	buildp.add_argument('-t', '--target', choices=['pe', 'elf', 'pros'], default='pros')
	buildp.add_argument('-o', '--outdir', help='Output directory', default='out')
	buildp.add_argument('--compile', action='store_true', help='Attempt to compile native binaries after generating code')
	args = parser.parse_args()
	if args.command == 'build':
		build_command(args)
	else:
		parser.print_help()


if __name__ == '__main__':
	main()
