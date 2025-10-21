## PyPI

```commandline
cd eozilla
python -m build
twine upload dist/*
```

Do this for all subpackages too.

## Conda

After the PyPI packages have been deployed, we can create
a `conda-forge` staged-recipes PR.


If not already done, do

```commandline
git clone https://github.com/eo-tools/eozilla-recipes.git
```

```commandline
cd eozilla-recipes/recipes/eozilla
rattler-build generate-recipe pypi eozilla -w
```

Edit `./recipe.yaml`, merge the following

```yaml
about:
  home: "https://github.com/eo-tools/eozilla"

extra:
  recipe-maintainers:
    - forman
```
