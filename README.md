# Unity Bundle Extractor

A simple Python tool for extracting Unity AssetBundle `.bundle` files using UnityPy.

Install dependencies:

```powershell
python -m pip install UnityPy texture2ddecoder
```

Extract one bundle:

```powershell
python bundle_extractor.py "path/to/file.bundle" -o "path/to/output"
```

Extract all bundles in a folder:

```powershell
python bundle_extractor.py "path/to/bundles" -o "path/to/output" -r
```

