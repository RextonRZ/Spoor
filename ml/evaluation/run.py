"""Entry point: run from backend/ so the spoor package and its environment are available.

    cd backend && uv run python ../ml/evaluation/run.py --dataset ../ml/evaluation/datasets/<name>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spoor_eval.run import main

if __name__ == "__main__":
    main()
