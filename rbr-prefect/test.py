from requirements_detector.detect import from_requirements_txt
from pathlib import Path


p = Path.cwd() / "rbr-prefect" / "requirements.txt"

r = from_requirements_txt(p)
