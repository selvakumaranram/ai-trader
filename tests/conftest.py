import os
import sys

# Tests target the canonical, deployed code under vercel-demo/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vercel-demo")))
