import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// react-markdown hands every custom renderer a `node` (hast node) prop. Strip it
// so it doesn't land on the DOM element, which makes React warn about an unknown
// attribute. (`_node` is a variable, so eslint's varsIgnorePattern covers it.)
function rest(props) {
  const { node: _node, ...clean } = props;
  return clean;
}

// Maps a markdown element to a Tailwind-styled equivalent.
function tag(Element, className) {
  return function MdEl(props) {
    return <Element className={className} {...rest(props)} />;
  };
}

const components = {
  p: tag('p', 'my-2 first:mt-0 last:mb-0 leading-relaxed'),
  ul: tag('ul', 'my-2 ml-4 list-disc space-y-1 marker:text-slate-400'),
  ol: tag('ol', 'my-2 ml-4 list-decimal space-y-1 marker:text-slate-400'),
  li: tag('li', 'leading-relaxed'),
  strong: tag('strong', 'font-semibold text-slate-900 dark:text-white'),
  em: tag('em', 'italic'),
  h1: tag('h1', 'text-base font-bold mt-3 mb-1.5 first:mt-0'),
  h2: tag('h2', 'text-base font-bold mt-3 mb-1.5 first:mt-0'),
  h3: tag('h3', 'text-sm font-semibold mt-3 mb-1 first:mt-0'),
  blockquote: tag(
    'blockquote',
    'border-l-2 border-slate-300 dark:border-slate-600 pl-3 my-2 text-slate-600 dark:text-slate-400 italic',
  ),
  hr: tag('hr', 'my-3 border-slate-200 dark:border-slate-700'),
  pre: tag('pre', 'my-2 p-3 rounded-lg bg-slate-100 dark:bg-slate-800 overflow-x-auto text-[0.85em]'),
  th: tag('th', 'border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-3 py-1.5 text-left font-semibold text-slate-900 dark:text-white'),
  td: tag('td', 'border-b border-slate-100 dark:border-slate-800 px-3 py-1.5 align-top'),

  a: (props) => (
    <a
      className="text-primary underline underline-offset-2 hover:text-blue-600"
      target="_blank"
      rel="noreferrer"
      {...rest(props)}
    />
  ),
  // GFM tables can be wider than the bubble; wrap so they scroll instead of overflow.
  table: (props) => (
    <div className="my-2 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
      <table className="w-full border-collapse text-[0.92em]" {...rest(props)} />
    </div>
  ),
  // react-markdown v9 dropped the `inline` prop; block code is wrapped in <pre>
  // (and carries a language- class / newline), so detect it and let <pre> style it.
  code: (props) => {
    const { className, children, ...other } = rest(props);
    const isBlock = /language-/.test(className || '') || String(children).includes('\n');
    return isBlock ? (
      <code className="font-mono" {...other}>{children}</code>
    ) : (
      <code className="rounded bg-slate-100 dark:bg-slate-800 px-1 py-0.5 font-mono text-[0.85em]" {...other}>
        {children}
      </code>
    );
  },
};

// Renders assistant answers (which the LLM writes in Markdown - tables, lists,
// bold, etc.) as formatted output instead of raw text.
export default function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children || ''}
    </ReactMarkdown>
  );
}
