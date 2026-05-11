/**
 * Minimal Newick tree parser.
 *
 * Returns a plain JSON tree compatible with d3.hierarchy().
 *
 * Supported syntax (a deliberately small subset, sufficient for our trees):
 *   - parentheses for nesting
 *   - commas to separate siblings
 *   - optional node name (may be quoted with single quotes)
 *   - optional :branch_length after the name
 *   - trailing ';'
 *   - whitespace anywhere outside quoted names
 *
 * Not (yet) supported: NHX extensions, square-bracket comments, double-quoted names.
 */

export interface NewickNode {
  name: string;
  branchLength: number;       // 0 when missing
  children: NewickNode[];
}

export function parseNewick(input: string): NewickNode {
  let i = 0;
  const src = input;

  function skipWs(): void {
    while (i < src.length && /\s/.test(src[i])) i++;
  }

  function readName(): string {
    skipWs();
    if (src[i] === "'") {
      // single-quoted name; doubled '' becomes literal '
      i++;
      let out = '';
      while (i < src.length) {
        if (src[i] === "'") {
          if (src[i + 1] === "'") { out += "'"; i += 2; continue; }
          i++;
          return out;
        }
        out += src[i++];
      }
      return out;
    }
    let out = '';
    while (i < src.length && !/[,():;\s]/.test(src[i])) out += src[i++];
    return out;
  }

  function readNumber(): number {
    skipWs();
    let s = '';
    while (i < src.length && /[0-9eE+\-.]/.test(src[i])) s += src[i++];
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : 0;
  }

  function readNode(): NewickNode {
    skipWs();
    const node: NewickNode = { name: '', branchLength: 0, children: [] };
    if (src[i] === '(') {
      i++;
      node.children.push(readNode());
      skipWs();
      while (src[i] === ',') {
        i++;
        node.children.push(readNode());
        skipWs();
      }
      if (src[i] !== ')') {
        throw new Error(`Newick parse error: expected ')' at pos ${i}`);
      }
      i++;
    }
    node.name = readName();
    skipWs();
    if (src[i] === ':') {
      i++;
      node.branchLength = readNumber();
    }
    return node;
  }

  const root = readNode();
  skipWs();
  if (src[i] === ';') i++;
  return root;
}
