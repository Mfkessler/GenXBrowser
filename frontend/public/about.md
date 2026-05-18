# GenXBrowser

**Interactive browser for gene expression analysis.**

GenXBrowser visualizes gene expression data stored in AnnData (.h5ad) files. Select datasets from the catalog, apply filters based on gene metadata, and choose from multiple analysis types - including single-dataset analysis and cross-species comparisons.

## Analysis Types

- **Heatmap** - Interactive expression heatmaps with z-score normalization and hierarchical clustering
- **ORA** - Over-representation analysis with Fisher's exact test for GO term enrichment
- **Compare Expression** - Side-by-side expression comparison across species or datasets
- **Phylogenetic Tree** - Newick tree visualization for orthogroup gene families

## Key Features

- **Catalog & Selection** - Browse available datasets and select multiple species for analysis
- **Advanced Filtering** - Filter genes by GO terms, descriptions, EC numbers, and custom metadata columns
- **Gene Ontology** - Integrated GO term search with autocomplete and hierarchy navigation
- **Shareable States** - Export filtered data as TSV and share filter configurations via URL
- **Sample Metadata** - Filter and color by tissue types, conditions, and experimental metadata

## Technology

Built with Vue 3, Flask, and Plotly. Developed at Justus Liebig University Giessen as part of the ICIPS project.

Open source under MIT License · [GitHub](https://github.com/Mfkessler/GenXBrowser)

<p align="center">
  <img src="jlu-logo-200.png" alt="JLU Giessen" width="150" style="margin-top: 2rem;" />
</p>
