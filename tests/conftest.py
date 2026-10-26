import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PYATNITSA_HOME"] = tempfile.mkdtemp(prefix="pyat-test-")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
