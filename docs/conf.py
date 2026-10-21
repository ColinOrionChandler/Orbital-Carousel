# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html


from importlib.metadata import version
from pathlib import Path

# Define path to the code to be documented **relative to where conf.py (this file) is kept**


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Orbital Carousel"
copyright = "2026, Colin Orion Chandler"
author = "Colin Orion Chandler"
release = version("orbital-carousel")
# for example take major/minor
version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["sphinx.ext.mathjax", "sphinx.ext.napoleon", "sphinx.ext.viewcode"]

extensions.append("autoapi.extension")

# -- sphinx-copybutton configuration ----------------------------------------
extensions.append("sphinx_copybutton")
## sets up the expected prompt text from console blocks, and excludes it from
## the text that goes into the clipboard.
copybutton_exclude = ".linenos, .gp"
copybutton_prompt_text = ">> "

## lets us suppress the copy button on select code blocks.
copybutton_selector = "div:not(.no-copybutton) > div.highlight > pre"

templates_path = []
exclude_patterns = ["_build", "**.ipynb_checkpoints"]

# This assumes that sphinx-build is called from the root directory
master_doc = "index"
# Remove 'view source code' from top of page (for html, not python)
html_show_sourcelink = False
# Remove namespaces from class/method signatures
add_module_names = False

autoapi_type = "python"
autoapi_dirs = [str(Path(__file__).resolve().parents[1] / "src")]
autoapi_ignore = ["*/__main__.py", "*/_version.py"]
autoapi_add_toctree_entry = True
autoapi_member_order = "bysource"

html_theme = "sphinx_rtd_theme"

html_context = {
    "display_github": True,
    "github_user": "ColinOrionChandler",
    "github_repo": "Orbital-Carousel",
    "github_version": "main",
    "conf_py_path": "/docs/",
}
