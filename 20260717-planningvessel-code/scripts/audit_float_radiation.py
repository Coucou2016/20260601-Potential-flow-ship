from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planing_seakeeping.float_radiation_audit import run_audit

if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Strict radiation-only float diagnostic; not production")
    parser.add_argument("config")
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    raise SystemExit(run_audit(args.config,args.out))
