import xib2code
import argparse
import os.path
import glob

arg_parser = argparse.ArgumentParser(description='Convert XIB files into code')
arg_parser.add_argument('-i', '--input', metavar='SRC', required=True,
                        help='Input file or folder')
arg_parser.add_argument('-r', '--recursive', action='store_true',
                        help='Scan input folder recursively. Ignored if source is a single file')
arg_parser.add_argument('-o', '--output', metavar='OUT', required=True,
                        help='Output file or folder')
arg_parser.add_argument('-t', '--keep-tree', action='store_true',
                        help='If input and output are folders, then reflect structure of input subfolders in the output')
arg_parser.add_argument('-x', '--suffix', metavar='EXT', default='.inl',
                        help='Suffix for generated files')


def iterate_files(args):
    if os.path.isdir(args.input):
        if args.recursive:
            glob_path = args.input + '/**/*.xib'
        else:
            glob_path = args.input + '/*.xib'
        for input_path in glob.iglob(glob_path, recursive=args.recursive):

            if args.keep_tree:
                output_path = os.path.relpath(input_path, args.input)
            else:
                output_path = os.path.basename(input_path)
            (output_path, _) = os.path.splitext(output_path)
            output_path = output_path + args.suffix
            output_path = os.path.join(args.output, output_path)
            yield input_path, output_path
    else:
        if os.path.isdir(args.output):
            output_path = os.path.join(args.output, os.path.basename(args.input) + args.suffix)
        else:
            output_path = args.output
        yield args.input, output_path


def run_tool():
    args = arg_parser.parse_args()
    for (input_path, output_path) in iterate_files(args):
        print((input_path, output_path))

if __name__ == '__main__':
    run_tool()