# Jupyter examples to use openrouteservice
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/GIScience/openrouteservice-examples/master?filepath=python)

(Mostly) real-world examples and inspirations to use the full range of ORS services and clients.

For an instant setup, you can use [MyBinder](https://mybinder.org/v2/gh/GIScience/openrouteservice-examples/master?filepath=python)
to start an interactive Jupyter server.

### Local installation

```bash
# clone the repo and enter folder
git clone https://github.com/GIScience/openrouteservice-examples.git
cd openrouteservice-examples

# Install the requirements in a virtual env and activate it
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

> Note: In case jupyter is already installed globally, and you want to use the local version, you can create a symlink to
> the local jupyter with:
>
>`ln -s .venv/bin/jupyter jupyter`
> 
> Then, run jupyter commands with `./jupyter` instead. 

### Launch the Jupyter server on the python directory
jupyter notebook python/

### Development
If you are not just using but editing or adding notebooks, you need to install the jupytext extension 

```bash
# set up jupytext server extension
jupyter nbextension install --py jupytext --user
jupyter nbextension enable jupytext --user --py
jupyter serverextension enable jupytext
```

Note, that every notebook is paired with a corresponding `.py`-file of the same name.
On changing either the notebook or the `.py`-file, the other one will be automatically updated.

When reviewing changes, only the `.py`-file needs to be looked at, the
`.ipynb`-file is only kept for use with jupyter in the browser and to render
maps and other information.

### Pairing new notebooks
New notebooks have to be paired by clicking `File > Jupytext > Pair notebook with light Script`
