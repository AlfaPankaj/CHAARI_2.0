# CHAARI 2.0 – config/rag.py — Agentic RAG + RAPTOR Configuration
# All constants for the hierarchical retrieval-augmented generation pipeline.

import os


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(_BASE_DIR, "data", "knowledge")
VECTORDB_DIR = os.path.join(_BASE_DIR, "data", "vectordb")


EMBEDDING_MODEL = "all-MiniLM-L6-v2"       
EMBEDDING_DIMENSION = 384


CHUNK_SIZE = 512            
CHUNK_OVERLAP = 50          
CODE_CHUNK_BY_FUNCTION = True  

SUPPORTED_EXTENSIONS = {".py", ".txt", ".md", ".pdf", ".json", ".csv", ".docx", ".xlsx"}



TREE_DEPTH = 4              

GMM_MAX_CLUSTERS = 50       
GMM_COVARIANCE_TYPE = "full"
GMM_RANDOM_STATE = 42
GMM_THRESHOLD = 0.1         

SUMMARY_MAX_TOKENS = 200    
SUMMARY_TEMPERATURE = 0.3   
SUMMARY_PROMPT = (
    "You are a technical documentation summarizer. "
    "Summarize the following related text chunks into a single concise paragraph. "
    "Preserve ALL technical details: function names, config values, port numbers, "
    "file paths, class names, and architecture patterns. "
    "Do NOT add opinions or filler words. Be precise and factual.\n\n"
    "CHUNKS:\n{chunks}\n\n"
    "SUMMARY:"
)



COLLECTION_CHAARI_DOCS = "chaari_docs"       
COLLECTION_USER_DOCS = "user_docs"           
COLLECTION_CONVERSATIONS = "conversations"   

META_LEVEL = "tree_level"       
META_PARENT_ID = "parent_id"    
META_SOURCE = "source"          
META_CHUNK_ID = "chunk_id"      



MAX_RAG_ITERATIONS = 3      
TOP_K_PER_LEVEL = 5         
RELEVANCE_THRESHOLD = 0.35  

OLLAMA_BASE_URL = "http://localhost:11434"
ROUTER_MODEL = "llama3.2:3b"            
LEVEL_SELECTOR_MODEL = "llama3.2:3b"    
EVALUATOR_MODEL = "llama3.2:3b"         

RAG_TRIGGER_KEYWORDS = [
    r"(?i)\b(find\s+(?:all\s+)?info|summarize|summarise|summary\s+of)\b",
    r"(?i)\b(main\s+theme|compare|comparison|contrast)\b",
    r"(?i)\b(search\s+through|search\s+(?:my\s+)?documents?|look\s+up\s+in)\b",
    r"(?i)\b(analyze|analyse)\s+(?:the\s+)?(?:marks|data|content|text|info)\b",
    r"(?i)\b(what\s+is\s+(?:the\s+)?(?:main|key|central)\s+(?:theme|topic|idea|point))\b",
    r"(?i)\b(based\s+on\s+(?:the\s+)?(?:roadmap|plan|document|file))\b",
    r"(?i)\b(check\s+if|matches?\s+my|mention\s+of)\b",
    r"(?i)\b(architecture|design|pipeline|system|layer|module|component)\b",
    r"(?i)\b(kaise\s+kaam|how\s+does|how\s+it\s+work|explain|batao|samjhao)\b",
    r"(?i)\b(code|function|class|method|config|setting)\b",
    r"(?i)\b(security|safety|crypto|encryption|validation|confirmation)\b",
    r"(?i)\b(dell|asus|node|executor|brain|groq|ollama)\b",
    r"(?i)\b(voice|audio|tts|stt|wake\s*word|speech)\b",
    r"(?i)\b(memory|personality|identity|guardrail|privilege)\b",
    r"(?i)\b(chaari|cherry)\b.*\b(kya|what|about|detail|explain|batao)\b",
    r"(?i)\b(what|kya)\b.*\b(chaari|cherry)\b",
]

RAG_SKIP_KEYWORDS = [
    r"(?i)^(open|close|launch|minimize|maximize|restore|delete|copy|move|kill)\b",
    r"(?i)\b(shutdown|restart|send\s+message|type\s+text|whatsapp|telegram)\b",
    r"(?i)\b(time|date|battery|cpu|ram|disk|weather|temperature)\b",
]

LEVEL_BROAD_KEYWORDS = [
    r"(?i)\b(what\s+is|kya\s+hai|overview|summary|tell\s+me\s+about|introduction)\b",
]

LEVEL_SPECIFIC_KEYWORDS = [
    r"(?i)\b(exact|specific|value|port|number|limit|path|name|line|config)\b",
    r"(?i)\b(kitna|konsa|kaunsa|which|how\s+many|what.*(?:value|number|limit))\b",
]
