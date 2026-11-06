"""CLI for opt-in comparison of locally supplied raw and parsed SEC filings."""
import argparse
import json
from pathlib import Path
from .phase17_validation import audit_local_raw_html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-html', required=True)
    parser.add_argument('--parsed-json', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = audit_local_raw_html(args.raw_html, args.parsed_json)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(output)

if __name__ == '__main__':
    main()
