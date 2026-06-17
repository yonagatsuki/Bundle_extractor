# Unity Bundle Extractor

A simple Python tool for extracting Unity AssetBundle `.bundle` files using UnityPy.

Install dependencies:

```powershell
python -m pip install UnityPy texture2ddecoder
```

Extract one bundle:

```powershell
python bundle_extractor.py "F:\path\file.bundle" -o "F:\path\output"
```

Extract all bundles in a folder:

```powershell
python bundle_extractor.py "F:\path\bundles" -o "F:\path\output" -r
```
