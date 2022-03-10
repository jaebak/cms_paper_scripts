# Install instructions
```
cd paper or an folder
git submodule update --init --remote --recursive
git clone git@github.com:jaebak/cms_paper_scripts.git
```

# Run examples
```
python3 cms_paper_scripts/tdrDiff.py SUS-20-004 -p papers --revBase HEAD --revDiff HEAD~1
```
```
python3 cms_paper_scripts/tdrDiff.py AN-19-112 -p notes --revBase HEAD --revDiff HEAD~1
```

# About latexdiff
Got recent version of latexdiff for bug fixes from : https://github.com/ftilmann/latexdiff
