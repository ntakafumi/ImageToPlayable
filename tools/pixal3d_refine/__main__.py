"""Command line entry point used by notebook 03."""
import argparse
import json

from . import repair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--views', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print('Aligning source and refining the texture; large GLBs may take several minutes.', flush=True)
    print(json.dumps(repair.run(args.model, args.views, args.output), indent=2), flush=True)


if __name__ == '__main__':
    main()
