"""CLI for adding historical financial intelligence from an existing report.json."""
import argparse
import json
from pathlib import Path
from .historical_intelligence import analyze_history

def main():
    p = argparse.ArgumentParser(description='Generate historical intelligence from an existing report.json')
    p.add_argument('report', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--years', type=int, default=5)
    args = p.parse_args()
    result = analyze_history(json.loads(args.report.read_text()), years=args.years)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(args.output)

if __name__ == '__main__':
    main()
