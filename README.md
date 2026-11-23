# GenXBrowser

<img src="./frontend/public/GenX_Logo.png" alt="GenXBrowser logo" width="112">

Explore and compare gene expression across datasets in your browser.

## Use GenXBrowser

**[Open the public instance](https://genxbrowser.computational.bio/public/genxbrowser/catalog)** — no account needed.

1. Select one or more datasets in the catalog.
2. Use the sidebar to filter genes/transcripts or samples. If a view is disabled, check its tooltip and narrow your selection.
3. Open **Heatmap** for expression patterns, **ORA** for GO enrichment, **Compare Expression** for orthogroups across species, or **Phylogenetic Tree** for gene trees where available.
4. Export results or copy a share link. Anyone with the link can open the saved view; don't include confidential values.

## Run your own instance

Install Conda (e.g. Miniforge) and have a TSV count matrix ready: IDs in the first column, samples in the remaining columns.

```bash
git clone https://github.com/Mfkessler/GenXBrowser.git
cd GenXBrowser/prepare
conda env create -f environment.yml
conda activate genxprep
genxprep init
# Edit config.yml to point to your matrix and any optional metadata.
genxprep build config.yml
genxprep app config.yml
```

Open [localhost:5173](http://localhost:5173). Press `Ctrl+C` to stop. After setup, add `--skip-setup` for faster restarts.

The launcher binds to loopback with debug off. Set `ADMIN_TOKEN` before starting to enable `/admin`; browsing works without it. For network deployments, use production servers and HTTPS, and don't expose the backend port directly. See [input formats](prepare/README.md#-input-data), [backend deployment](backend/README.md#production) and [frontend deployment](frontend/README.md#deployment).

[MIT license](LICENSE) (software).
