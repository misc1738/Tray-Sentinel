"""
Runner script for scenarios
Usage:
  python run_scenario.py --scenario ../scenarios/medium_risk_voltage_fluctuation.json --dry-run
"""
from tools.simulator.simulator import SimpleSimulator
from pathlib import Path
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--api", required=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        print("Scenario file not found:", scenario_path)
        return

    sim = SimpleSimulator(scenario=__import__('json').load(open(scenario_path)), api_endpoint=args.api, dry_run=args.dry_run, seed=args.seed)
    sim.run()


if __name__ == '__main__':
    main()
