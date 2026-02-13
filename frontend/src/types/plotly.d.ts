// Type declarations for plotly.js-dist-min
declare module 'plotly.js-dist-min' {
  export interface Data {
    x?: (string | number | Date)[];
    y?: (number | null)[];
    z?: number[][];
    type?: 'scatter' | 'bar' | 'heatmap' | 'pie' | 'box' | 'histogram' | 'scatter3d';
    mode?: 'lines' | 'markers' | 'lines+markers' | 'text' | 'none';
    name?: string;
    text?: string | string[];
    hovertext?: string | string[];
    hoverinfo?: 'x' | 'y' | 'z' | 'text' | 'name' | 'all' | 'none' | 'skip' | string;
    hovertemplate?: string | string[];
    line?: {
      color?: string;
      width?: number;
      dash?: 'solid' | 'dot' | 'dash' | 'longdash' | 'dashdot' | 'longdashdot';
      shape?: 'linear' | 'spline' | 'hv' | 'vh' | 'hvh' | 'vhv';
    };
    marker?: {
      color?: string | string[] | number[];
      size?: number | number[];
      symbol?: string;
      opacity?: number;
      line?: {
        color?: string;
        width?: number;
      };
    };
    fill?: 'none' | 'tozeroy' | 'tozerox' | 'tonexty' | 'tonextx' | 'toself' | 'tonext';
    fillcolor?: string;
    opacity?: number;
    legendgroup?: string;
    showlegend?: boolean;
    visible?: boolean | 'legendonly';
    connectgaps?: boolean;
  }

  export interface Layout {
    title?: string | { text: string; font?: Font };
    autosize?: boolean;
    width?: number;
    height?: number;
    margin?: { l?: number; r?: number; t?: number; b?: number; pad?: number };
    paper_bgcolor?: string;
    plot_bgcolor?: string;
    font?: Font;
    xaxis?: Axis;
    yaxis?: Axis;
    legend?: {
      x?: number;
      y?: number;
      xanchor?: 'auto' | 'left' | 'center' | 'right';
      yanchor?: 'auto' | 'top' | 'middle' | 'bottom';
      bgcolor?: string;
      bordercolor?: string;
      borderwidth?: number;
      font?: Font;
      orientation?: 'v' | 'h';
      traceorder?: 'normal' | 'reversed' | 'grouped' | 'reversed+grouped';
      tracegroupgap?: number;
    };
    hovermode?: 'x' | 'y' | 'closest' | false | 'x unified' | 'y unified';
    hoverlabel?: {
      bgcolor?: string;
      bordercolor?: string;
      font?: Font;
    };
    showlegend?: boolean;
    shapes?: Shape[];
    annotations?: Annotation[];
  }

  export interface Font {
    family?: string;
    size?: number;
    color?: string;
  }

  export interface Axis {
    title?: string | { text: string; font?: Font; standoff?: number };
    type?: 'linear' | 'log' | 'date' | 'category' | 'multicategory';
    autorange?: boolean | 'reversed';
    range?: [number | string, number | string];
    tickmode?: 'auto' | 'linear' | 'array';
    tickvals?: (number | string)[];
    ticktext?: string[];
    tickangle?: number;
    tickfont?: Font;
    showgrid?: boolean;
    gridcolor?: string;
    gridwidth?: number;
    zeroline?: boolean;
    zerolinecolor?: string;
    zerolinewidth?: number;
    showline?: boolean;
    linecolor?: string;
    linewidth?: number;
    showticklabels?: boolean;
    fixedrange?: boolean;
    categoryorder?: 'trace' | 'category ascending' | 'category descending' | 'array' | 'total ascending' | 'total descending';
    categoryarray?: string[];
  }

  export interface Shape {
    type?: 'circle' | 'rect' | 'path' | 'line';
    x0?: number | string;
    y0?: number | string;
    x1?: number | string;
    y1?: number | string;
    path?: string;
    line?: { color?: string; width?: number; dash?: string };
    fillcolor?: string;
    opacity?: number;
    layer?: 'below' | 'above';
    xref?: 'x' | 'paper';
    yref?: 'y' | 'paper';
  }

  export interface Annotation {
    x?: number | string;
    y?: number | string;
    xref?: 'x' | 'paper';
    yref?: 'y' | 'paper';
    text?: string;
    showarrow?: boolean;
    arrowhead?: number;
    ax?: number;
    ay?: number;
    font?: Font;
    align?: 'left' | 'center' | 'right';
    bgcolor?: string;
    bordercolor?: string;
    borderwidth?: number;
    borderpad?: number;
    opacity?: number;
  }

  export interface Config {
    responsive?: boolean;
    displayModeBar?: boolean | 'hover';
    displaylogo?: boolean;
    modeBarButtonsToRemove?: string[];
    modeBarButtonsToAdd?: string[];
    toImageButtonOptions?: {
      format?: 'svg' | 'png' | 'jpeg' | 'webp';
      filename?: string;
      height?: number;
      width?: number;
      scale?: number;
    };
    scrollZoom?: boolean;
    editable?: boolean;
    staticPlot?: boolean;
  }

  export function newPlot(
    graphDiv: HTMLElement | string,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<HTMLElement>;

  export function react(
    graphDiv: HTMLElement | string,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<HTMLElement>;

  export function purge(graphDiv: HTMLElement | string): void;

  export function relayout(
    graphDiv: HTMLElement | string,
    update: Partial<Layout>
  ): Promise<HTMLElement>;

  export function restyle(
    graphDiv: HTMLElement | string,
    update: Partial<Data>,
    indices?: number | number[]
  ): Promise<HTMLElement>;

  export namespace Plots {
    function resize(graphDiv: HTMLElement | string): void;
  }

  export function toImage(
    graphDiv: HTMLElement | string,
    opts?: {
      format?: 'svg' | 'png' | 'jpeg' | 'webp';
      width?: number;
      height?: number;
      scale?: number;
    }
  ): Promise<string>;

  export function downloadImage(
    graphDiv: HTMLElement | string,
    opts?: {
      format?: 'svg' | 'png' | 'jpeg' | 'webp';
      width?: number;
      height?: number;
      scale?: number;
      filename?: string;
    }
  ): Promise<string>;
}
