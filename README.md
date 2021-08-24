# Jupyter examples to use OpenRouteService
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/GIScience/openrouteservice-examples/master?filepath=python)

(Mostly) real-world examples and inspirations to use the full breadth of ORS services and clients.

To get you kick started, [click here](https://mybinder.org/v2/gh/GIScience/openrouteservice-examples/master?filepath=python) to start a MyBinder interactive Jupyter server.

Or install locally with 

```bash
git clone https://github.com/GIScience/openrouteservice-examples.git

# Install the requirements in a virtual env
python -m venv .venv
source .venv/bin/activate

pip install -r requirements

# set up jupytext server extension
jupyter nbextension install --py jupytext --user
jupyter nbextension enable jupytext --user --py
jupyter serverextension enable jupytext

# Launch the Jupyter server on the python directory
jupyter notebook python/
```

Note, that every notebook is paired with a corresponding `.py`-file of the same name.
On changing either the notebook or the `.py`-file, the other one will be automatically updated.

When reviewing changes, only the `.py`-file needs to be looked at, the
`.ipynb`-file is only kept for use with jupyter in the browser and to render
maps and other information.
