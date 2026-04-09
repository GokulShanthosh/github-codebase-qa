import { lazy, Suspense } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion } from "framer-motion";

// Lazy-load the heavy syntax highlighter so it splits into its own chunk
const SyntaxHighlighter = lazy(() =>
  import("react-syntax-highlighter").then((m) => ({ default: m.Prism }))
);
// vscDarkPlus is just a JSON object — fine to import eagerly
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Props {
  content: string;
  streaming?: boolean;
}

// Distinguish block code (has language class OR is multiline) from inline code
function CodeBlock({ className, children, ...props }: React.HTMLAttributes<HTMLElement>) {
  const match = /language-(\w+)/.exec(className || "");
  const code = String(children).replace(/\n$/, "");
  const isBlock = !!match || code.includes("\n");

  if (isBlock) {
    return (
      <Suspense fallback={<pre className="md-code-fallback">{code}</pre>}>
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={match?.[1] ?? "text"}
          PreTag="div"
          customStyle={{
            margin: "10px 0",
            borderRadius: "10px",
            fontSize: "13px",
            lineHeight: "1.6",
            border: "1px solid rgba(255,255,255,0.07)",
            background: "#1e1e2e",
          }}
          codeTagProps={{ style: { fontFamily: "var(--mono)" } }}
        >
          {code}
        </SyntaxHighlighter>
      </Suspense>
    );
  }

  return (
    <code className="md-inline-code" {...props}>
      {children}
    </code>
  );
}

export function MarkdownContent({ content, streaming }: Props) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Unwrap <pre> so SyntaxHighlighter controls its own wrapper
          pre: ({ children }) => <>{children}</>,
          code: CodeBlock as React.ComponentType<React.HTMLAttributes<HTMLElement>>,
          // Style tables
          table: ({ children }) => (
            <div className="md-table-wrap">
              <table className="md-table">{children}</table>
            </div>
          ),
          // Style blockquotes
          blockquote: ({ children }) => (
            <blockquote className="md-blockquote">{children}</blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>

      {streaming && (
        <motion.span
          className="md-cursor"
          animate={{ opacity: [1, 0] }}
          transition={{ duration: 0.55, repeat: Infinity }}
        />
      )}
    </div>
  );
}
