/**
 * Phylogenetic tree layout utilities (rectangular, SVG-friendly).
 *
 * Key design properties (why this exists rather than reusing phylotree.js):
 *   - Layout produces leaf y-positions on a fixed `rowHeight` grid, so the
 *     heatmap on the right shares the SAME y-scale as the tree by
 *     construction (no asynchronous transform-readback).
 *   - Collapse is a pure data transformation on the d3.hierarchy: the Pinia
 *     store (`collapsedNodes`) is the single source of truth.
 *   - Node IDs are deterministic (the sorted set of descendant leaf names),
 *     so collapse persistence survives reloads and OG reselection.
 */

import * as d3 from 'd3';
import type { NewickNode } from './newick';

export interface PhyloDatum {
  name: string;
  branchLength: number;
  /** Stable, topology-derived identifier (sorted leaf-name set). */
  nodeId: string;
  /** All leaf names descending from this node (cached, sorted). */
  leafNames: string[];
  /** Lazy: present for internal nodes whose children have been hidden via collapse. */
  _collapsedChildren?: NewickNode[];
  /** Original children for re-expansion bookkeeping. */
  children?: PhyloDatum[];
}

/** Convert raw Newick AST into a d3.hierarchy with stable nodeIds attached. */
export function buildHierarchy(root: NewickNode): d3.HierarchyNode<PhyloDatum> {
  // First, decorate with leafNames + nodeId in a single post-order pass.
  function decorate(n: NewickNode): PhyloDatum {
    const decoratedChildren = n.children.map(decorate);
    let leafNames: string[];
    if (decoratedChildren.length === 0) {
      leafNames = [n.name];
    } else {
      const acc: string[] = [];
      for (const c of decoratedChildren) acc.push(...c.leafNames);
      acc.sort();
      leafNames = acc;
    }
    return {
      name: n.name,
      branchLength: n.branchLength,
      nodeId: leafNames.length === 1 ? `leaf:${leafNames[0]}` : `clade:${leafNames.join('|')}`,
      leafNames,
      children: decoratedChildren.length > 0 ? decoratedChildren : undefined,
    };
  }
  const decorated = decorate(root);
  return d3.hierarchy<PhyloDatum>(decorated, (d) => d.children);
}

export interface LayoutOptions {
  /** Pixel spacing between adjacent leaves. */
  rowHeight: number;
  /** Total horizontal pixels available for the tree (label area not included). */
  treeWidth: number;
  /** 'cladogram': all leaves at right edge. 'phylogram': x scaled by branch length. */
  mode: 'cladogram' | 'phylogram';
}

export interface LayoutNode {
  hnode: d3.HierarchyNode<PhyloDatum>;
  x: number;       // horizontal pixel (depth axis)
  y: number;       // vertical pixel (leaf-row axis)
  isLeaf: boolean;
  isCollapsed: boolean;
}

export interface LayoutResult {
  nodes: LayoutNode[];
  leaves: LayoutNode[];
  links: { source: LayoutNode; target: LayoutNode }[];
  totalHeight: number;
  totalWidth: number;
}

/**
 * Produce a clone of the hierarchy with `collapsedIds` nodes detached.
 * The collapsed nodes themselves are kept (as leaves of the visible tree)
 * so they can render as triangles; their original subtrees are preserved
 * on `_collapsedChildren` for tooltips / leaf counts.
 */
export function applyCollapse(
  root: d3.HierarchyNode<PhyloDatum>,
  collapsedIds: Set<string>,
): d3.HierarchyNode<PhyloDatum> {
  function rec(n: d3.HierarchyNode<PhyloDatum>): PhyloDatum {
    const d: PhyloDatum = {
      name: n.data.name,
      branchLength: n.data.branchLength,
      nodeId: n.data.nodeId,
      leafNames: n.data.leafNames,
    };
    if (collapsedIds.has(n.data.nodeId) && n.children && n.children.length > 0) {
      // Hide subtree; mark as collapsed via _collapsedChildren marker.
      d._collapsedChildren = [];
      return d;
    }
    if (n.children && n.children.length > 0) {
      d.children = n.children.map((c) => rec(c));
    }
    return d;
  }
  return d3.hierarchy<PhyloDatum>(rec(root), (d) => d.children);
}

/** Compute rectangular layout. y comes from leaf order; x from depth or branch length. */
export function layout(
  root: d3.HierarchyNode<PhyloDatum>,
  opts: LayoutOptions,
): LayoutResult {
  const leavesArr = root.leaves();
  const rowHeight = opts.rowHeight;

  // Assign y to leaves on a strict grid; internal-node y = mean(child y).
  const yOf = new Map<d3.HierarchyNode<PhyloDatum>, number>();
  leavesArr.forEach((leaf, i) => yOf.set(leaf, i * rowHeight + rowHeight / 2));

  function fillInternalY(n: d3.HierarchyNode<PhyloDatum>): number {
    if (!n.children || n.children.length === 0) return yOf.get(n)!;
    const childYs = n.children.map(fillInternalY);
    const y = (Math.min(...childYs) + Math.max(...childYs)) / 2;
    yOf.set(n, y);
    return y;
  }
  fillInternalY(root);

  // Compute x — depth (cladogram) or cumulative branch length (phylogram).
  const xOf = new Map<d3.HierarchyNode<PhyloDatum>, number>();
  if (opts.mode === 'cladogram') {
    const maxDepth = d3.max(root.descendants(), (d) => d.depth) || 1;
    const scale = opts.treeWidth / Math.max(1, maxDepth);
    root.each((n) => xOf.set(n, n.depth * scale));
  } else {
    // phylogram: cumulative branch length from root
    const cumul = new Map<d3.HierarchyNode<PhyloDatum>, number>();
    cumul.set(root, 0);
    root.each((n) => {
      if (n.parent) {
        const bl = Math.max(0, n.data.branchLength || 0);
        cumul.set(n, (cumul.get(n.parent) || 0) + bl);
      }
    });
    const maxC = Math.max(1e-9, ...Array.from(cumul.values()));
    const scale = opts.treeWidth / maxC;
    root.each((n) => xOf.set(n, (cumul.get(n) || 0) * scale));
  }

  const nodes: LayoutNode[] = root.descendants().map((h) => ({
    hnode: h,
    x: xOf.get(h)!,
    y: yOf.get(h)!,
    isLeaf: !h.children || h.children.length === 0,
    isCollapsed: !!h.data._collapsedChildren,
  }));

  const byH = new Map<d3.HierarchyNode<PhyloDatum>, LayoutNode>();
  for (const ln of nodes) byH.set(ln.hnode, ln);

  const links: { source: LayoutNode; target: LayoutNode }[] = [];
  for (const ln of nodes) {
    if (ln.hnode.parent) {
      links.push({ source: byH.get(ln.hnode.parent)!, target: ln });
    }
  }

  const leaves = nodes.filter((n) => n.isLeaf);
  return {
    nodes,
    leaves,
    links,
    totalHeight: leavesArr.length * rowHeight,
    totalWidth: opts.treeWidth,
  };
}

/**
 * Find the deepest internal nodes whose entire leaf set shares one species prefix.
 * Used by the "Collapse to species" quick action. Returns their nodeIds.
 *
 * `prefixFor` maps a leaf name to its species prefix (e.g. "AT" or "Arabidopsis_thaliana").
 */
export function collapseToSpeciesIds(
  root: d3.HierarchyNode<PhyloDatum>,
  prefixFor: (leafName: string) => string,
): string[] {
  const result: string[] = [];

  function rec(n: d3.HierarchyNode<PhyloDatum>): string | null {
    // Returns the single shared species prefix of all descendants, or null if mixed.
    if (!n.children || n.children.length === 0) {
      return prefixFor(n.data.name) || '';
    }
    const childPrefixes = n.children.map(rec);
    const first = childPrefixes[0];
    const allSame =
      first !== null && childPrefixes.every((p) => p === first);
    if (allSame) {
      return first;
    }
    // Mixed: collapse each monophyletic child that is itself uniform.
    n.children.forEach((c, i) => {
      const p = childPrefixes[i];
      if (p !== null && c.children && c.children.length > 0) {
        result.push(c.data.nodeId);
      }
    });
    return null;
  }
  rec(root);
  return result;
}
