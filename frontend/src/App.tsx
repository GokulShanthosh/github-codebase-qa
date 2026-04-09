import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Code2, ArrowLeft, Layers, GitBranch, Cpu } from "lucide-react";
import { HomePage } from "./components/HomePage";
import { CodeLensView } from "./components/CodeLensView";
import "./App.css";

type View = "home" | "codelens";

const VIEW_META: Record<string, { title: string; sub: string }> = {
  codelens: { title: "CodeLens", sub: "GitHub Codebase Q&A" },
};

export default function App() {
  const [view, setView] = useState<View>("home");

  const isHome = view === "home";
  const meta = VIEW_META[view];

  return (
    <div className="app-shell">
      <div className="bg-grid" />

      {/* Header */}
      <header className="app-header">
        <div className="header-brand">
          <AnimatePresence mode="wait">
            {!isHome && (
              <motion.button
                key="back"
                className="back-btn"
                onClick={() => setView("home")}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.15 }}
              >
                <ArrowLeft size={16} />
              </motion.button>
            )}
          </AnimatePresence>

          <div className="brand-icon">
            <Code2 size={20} className="text-violet-400" />
          </div>

          <AnimatePresence mode="wait">
            {isHome ? (
              <motion.div
                key="home-brand"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <h1 className="brand-title">AI Portfolio</h1>
                <p className="brand-sub">by Gokul</p>
              </motion.div>
            ) : (
              <motion.div
                key="tool-brand"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <h1 className="brand-title">{meta?.title}</h1>
                <p className="brand-sub">{meta?.sub}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {!isHome && (
          <motion.div
            className="header-chips"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="chip"><Layers size={12} /> AST Chunking</div>
            <div className="chip"><GitBranch size={12} /> Hybrid Retrieval</div>
            <div className="chip"><Cpu size={12} /> LangGraph</div>
          </motion.div>
        )}
      </header>

      {/* Page */}
      <AnimatePresence mode="wait">
        {isHome ? (
          <motion.main
            key="home"
            className="app-main app-main--home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <HomePage onLaunch={(tool) => setView(tool as View)} />
          </motion.main>
        ) : (
          <motion.main
            key={view}
            className="app-main app-main--tool"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <CodeLensView onBack={() => setView("home")} />
          </motion.main>
        )}
      </AnimatePresence>

      {isHome && (
        <footer className="app-footer">
          <span>tree-sitter · pgvector · BM25 · FlashRank · LangGraph · Gemini 2.5 Flash</span>
        </footer>
      )}
    </div>
  );
}
