"""
Code Chunker — AST-based code splitting using tree-sitter.

WHY THIS EXISTS:
Normal text splitters split by character count. Code has meaning at the
function/class level. We use tree-sitter to parse each file into an AST
and extract functions and classes as individual chunks with rich metadata.
"""
from dataclasses import dataclass, field
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_java as tsjava


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CodeChunk:
    """One semantic unit of code (a function or class) ready to be embedded."""
    content: str              # raw source code of this chunk
    metadata: dict = field(default_factory=dict)
    # metadata keys:
    #   file_path, language, node_type, name, class_name, start_line, end_line


# ---------------------------------------------------------------------------
# Language registry
# ---------------------------------------------------------------------------
# WHY: tree-sitter needs a compiled grammar per language.
# We load each grammar once at module import time (not per file) for performance.

_LANGUAGES = {
    "python":     Language(tspython.language(), "python"),
    "javascript": Language(tsjavascript.language(), "javascript"),
    "java":       Language(tsjava.language(), "java"),
}

# WHY: Different languages name their AST nodes differently.
# Python uses "function_definition", Java uses "method_declaration".
# We map each language to the node types we want to extract as chunks.
_CHUNK_NODE_TYPES = {
    "python":     {"function_definition", "class_definition"},
    "javascript": {"function_declaration", "method_definition", "class_declaration"},
    "java":       {"method_declaration", "class_declaration"},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_file(content: str, language: str, file_path: str) -> list[CodeChunk]:
    """
    Parse a source file and return a list of CodeChunks.
    Each chunk is one function or class with metadata attached.

    Returns empty list if the language is unsupported or file fails to parse.
    """
    language_obj = _LANGUAGES.get(language)
    if not language_obj:
        return []

    # WHY bytes: tree-sitter works on raw bytes, not Python strings.
    # UTF-8 encoding handles all unicode in source files correctly.
    parser = Parser()
    parser.set_language(language_obj)
    tree = parser.parse(bytes(content, "utf-8"))

    chunks: list[CodeChunk] = []

    # Start recursive traversal from the root node.
    # parent_class=None because top-level nodes have no parent class yet.
    _walk(tree.root_node, content, language, file_path, chunks, parent_class=None)

    return chunks


# ---------------------------------------------------------------------------
# Private — AST traversal
# ---------------------------------------------------------------------------

def _walk(
    node: Node,
    content: str,
    language: str,
    file_path: str,
    chunks: list[CodeChunk],
    parent_class: str | None,
) -> None:
    """
    Recursively walk the AST tree.
    When we find a function or class node, extract it as a chunk.
    Then keep walking its children to catch nested functions/methods.
    """
    target_types = _CHUNK_NODE_TYPES.get(language, set())

    if node.type in target_types:
        # Extract the raw source text for this node using byte offsets.
        # WHY byte offsets: node.start_byte/end_byte are always accurate
        # regardless of multi-byte unicode characters in the file.
        chunk_content = content[node.start_byte:node.end_byte]
        name = _get_name(node)

        chunks.append(CodeChunk(
            content=chunk_content,
            metadata={
                "file_path":  file_path,
                "language":   language,
                "node_type":  node.type,
                "name":       name,
                # If this node is a method inside a class, record the class name.
                # If this node IS a class, class_name is None (it's the parent).
                "class_name": parent_class if "class" not in node.type else None,
                # +1 because tree-sitter uses 0-indexed lines, humans use 1-indexed.
                "start_line": node.start_point[0] + 1,
                "end_line":   node.end_point[0] + 1,
            }
        ))

        # WHY recurse with name as parent_class:
        # If this node is a class, its children (methods) need to know
        # which class they belong to. We pass the class name down.
        next_parent = name if "class" in node.type else parent_class
        for child in node.children:
            _walk(child, content, language, file_path, chunks, parent_class=next_parent)

    else:
        # Not a target node — keep walking children looking for target nodes.
        for child in node.children:
            _walk(child, content, language, file_path, chunks, parent_class=parent_class)


def _get_name(node: Node) -> str | None:
    """
    Extract the name of a function or class node.
    tree-sitter exposes named fields on nodes — 'name' is the identifier field.
    e.g. for `def calculate_tax(...)`, the name field gives us 'calculate_tax'.
    """
    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode("utf-8")
    return None
