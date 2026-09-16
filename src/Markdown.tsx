import { useEffect, useRef, useState } from 'react';
import type { ComponentPropsWithoutRef } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Root } from 'mdast';
import './markdown.css';

// Keep explicit Markdown alignment; align purely numeric columns when it is omitted.
function numericColumns() {
  type Node = { type: string; value?: string; children?: Node[]; align?: ('left' | 'right' | 'center' | null)[] | null };
  const text = (node: Node): string => node.value ?? node.children?.map(text).join('') ?? '';
  const numeric = (value: string) => /^(?:[—–-]|\(?[+−~-]?\s*[$€£₹]?\s*[+−-]?\d[\d,]*(?:\.\d+)?\s*(?:%|x|R)?\)?)$/i.test(value.trim());
  function visit(node: Node) {
    if (node.type === 'table' && node.children && node.align) {
      const rows = node.children.slice(1);
      node.align = node.align.map((alignment, index) => alignment || (
        rows.length && rows.every(row => row.children?.[index] && numeric(text(row.children[index]))) ? 'right' : null
      ));
    }
    node.children?.forEach(visit);
  }
  return (tree: Root) => visit(tree);
}

function MarkdownTable({ children, ...props }: ComponentPropsWithoutRef<'table'>) {
  const scroll = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  useEffect(() => {
    const element = scroll.current;
    if (!element) return;
    const measure = () => setOverflow(element.scrollWidth > element.clientWidth + 1);
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    measure();
    return () => observer.disconnect();
  }, [children]);
  return <div className={`markdown-table${overflow ? ' is-overflowing' : ''}`}>
    <div ref={scroll} className="markdown-table-scroll" role="region" aria-label="Analysis table" tabIndex={overflow ? 0 : undefined}>
      <table {...props}>{children}</table>
    </div>
    {overflow && <div className="markdown-table-hint">Scroll sideways to see all columns <span aria-hidden="true">↔</span></div>}
  </div>;
}

const components: Components = {
  table: ({ node, ...props }) => <MarkdownTable {...props} />,
  th: ({ node, ...props }) => <th scope="col" {...props} />,
};

/** The same safe renderer for streamed replies, saved conversations and notebook entries. */
export function Markdown({ children, className = '' }: { children: string; className?: string }) {
  return <div className={`markdown rendered-markdown ${className}`}>
    <ReactMarkdown remarkPlugins={[remarkGfm, numericColumns]} components={components}>{children}</ReactMarkdown>
  </div>;
}
