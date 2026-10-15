"""Rebuild a report without running a model. Existing review.csv entries are preserved."""
import argparse
from filename_bench.report import build_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--dataset-root", required=True)
    args = parser.parse_args()
    print(build_report(args.run_dir, args.dataset_root))
