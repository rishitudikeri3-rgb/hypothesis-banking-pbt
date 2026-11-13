"""
conftest.py - Shared pytest/Hypothesis setup, loaded automatically by pytest.
"""

from hypothesis import settings

# One Hypothesis profile for the whole project:
#  - deadline=None : don't fail a test just because one example ran slowly
#                    (timing on a laptop is noisy and is not what we test).
#  - database=None : don't replay failures saved from earlier runs, so every
#                    run depends only on --hypothesis-seed and is reproducible.
settings.register_profile("project", deadline=None, database=None)
settings.load_profile("project")
