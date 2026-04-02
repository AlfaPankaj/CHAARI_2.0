# CHAARI 2.0/ – core/ - Brain Connector
# Primary: Groq API (fast cloud LLM, ~200ms first token)
# Fallback: Ollama local (when Groq daily limit exhausted)

import re
import os
import time
import requests
import json
from typing import Generator
from core.personality import get_guardrails, get_personality_style, PersonalityState
from core.safety import SafetyKernel
from core.identity import IdentityLock
from core.tools import ToolTruth, APP_WHITELIST, _resolve_common_directory
from core.confirmation import ConfirmationEngine
from core.privilege import PrivilegeManager
from core.commands import SystemCommandRegistry
from core.policy_engine import PolicyEngine
from core.executor_port import CommandExecutorPort, NoOpExecutor, ExecutionStatus
from core.intent_resolver import IntentResolver
from core.session_manager import SessionManager
from core.audit_logger import AuditLogger, AuditEventType, AuditSeverity
from core.groq_provider import GroqProvider
from core.vision_engine import VisionEngine

try:
    from core.rag_agent import RAGAgent
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False


COMMAND_VERBS = {
    'open', 'close', 'exit', 'quit', 'minimize', 'maximize', 'restore',
    'type', 'write', 'send', 'text', 'message', 'call',
    'create', 'delete', 'remove', 'copy', 'move', 'rename',
    'kill', 'shutdown', 'restart', 'reboot', 'ping',
}

COMPOUND_CMD_DELAY = 0.5  


OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "chaari-2.0:latest"

LLM_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "num_predict": 150,       
    "num_ctx": 1024,          
    "repeat_penalty": 1.1,
}

LLM_OPTIONS_FAST = {
    "temperature": 0.7,
    "top_p": 0.9,
    "num_predict": 50,        
    "num_ctx": 512,           
    "repeat_penalty": 1.1,
}

LLM_KEEP_ALIVE = -1

SIMPLE_QUERY_PATTERNS = re.compile(
    r'^(hi|hello|hey|haan|ok|okay|thanks|thank you|good|nice|bye|chal|haha|lol|hmm|'
    r'accha|thik hai|sahi|kya hal|how are you|what\'?s up|sup|yo|namaste|'
    r'good morning|good night|good evening|tell me a joke|make me laugh)[\s?!.]*$',
    re.IGNORECASE
)



class Brain:
    """Handles all communication with the Ollama LLM."""

    def __init__(self, memory=None):
        self.base_url = OLLAMA_BASE_URL
        self.model = MODEL_NAME
        self._guardrails = get_guardrails()
        self._personality_style = get_personality_style()
        self.personality = PersonalityState()
        self.conversation_history: list[dict] = []
        self.max_history = 50  

        self.safety = SafetyKernel()

        self.identity = IdentityLock()

        self.policy = PolicyEngine()

        self.tools = ToolTruth()

        self.confirmation = ConfirmationEngine()

        self.privilege = PrivilegeManager()

        self.session_manager = SessionManager()

        self.audit = AuditLogger()

        self.executor: CommandExecutorPort = NoOpExecutor()  

        self.command_registry = SystemCommandRegistry(self.executor)

        self.memory = memory

        self.groq = GroqProvider()

        self.vision = VisionEngine()

        self.rag = RAGAgent(groq=self.groq) if RAG_AVAILABLE else None

        self._current_personality_cues: dict = {}

        self._pending_context: dict = {}
        self._pending_commands: list = []
        
        self._visual_context: str = ""
        
        self._last_execution_receipt: str = ""
        self._last_system_truth: str = ""

        self.intent_resolver = IntentResolver()
        self._last_raw_input: str = ""         
        self._last_matched_intent: str = ""    
        self._negative_keywords = ["no", "incorrect", "galt", "nahi", "wrong", "nhi"]

        for tool_name, available in self.tools.list_tools().items():
            if available:
                self.identity.register_tool(tool_name)

    def inject_executor(self, executor: CommandExecutorPort):
        """
        Inject a different executor adapter (for testing or OS execution).
        
        Args:
            executor: CommandExecutorPort implementation
        """
        self.executor = executor
        self.command_registry = SystemCommandRegistry(executor)

    def _is_simple_query(self, text: str) -> bool:
        """Detect simple queries that need fast LLM options (less context, fewer tokens)."""
        return bool(SIMPLE_QUERY_PATTERNS.match(text.strip()))

    def _extract_intent_context(self, intent: str, user_input: str) -> dict:
        """Extract parameters from user input based on detected intent."""
        text = user_input.strip()
        ctx = {}

        if intent in ("create_file",):
            filename = None
            m = re.search(r'(?:called|named|file)\s+["\']?([^\s"\']+\.\w+)', text, re.IGNORECASE)
            if m:
                filename = m.group(1)
            else:
                for token in re.findall(r'(\S+\.\w+)', text):
                    if re.match(r'.+\.\w{1,10}$', token) and token.lower().rstrip('.') not in (
                        'documents', 'downloads', 'desktop', 'pictures', 'videos', 'music',
                    ):
                        filename = token
                        break

            folder_path = None
            folder_m = re.search(r'\b(?:in|inside|into|to|under)\s+["\']?(\w+)["\']?[.!?]?\s*$', text, re.IGNORECASE)
            if folder_m:
                folder_name = folder_m.group(1)
                resolved = _resolve_common_directory(folder_name)
                if resolved:
                    folder_path = resolved

            if filename:
                if folder_path:
                    ctx["path"] = os.path.join(folder_path, filename)
                else:
                    ctx["path"] = os.path.join(".", filename)

        elif intent in ("delete_file",):
            m = re.search(r'(?:delete|remove)\s+(?:the\s+)?(?:file\s+)?["\']?([^\s"\']+\.\w+)', text, re.IGNORECASE)
            filename = m.group(1) if m else None

            folder_path = None
            folder_m = re.search(r'\b(?:from|in|inside)\s+["\']?(\w+)["\']?[.!?]?\s*$', text, re.IGNORECASE)
            if folder_m:
                folder_name = folder_m.group(1)
                resolved = _resolve_common_directory(folder_name)
                if resolved:
                    folder_path = resolved

            if filename:
                if folder_path:
                    ctx["path"] = os.path.join(folder_path, filename)
                else:
                    ctx["path"] = filename

        elif intent in ("copy_file",):
            m = re.search(r'copy\s+(?:the\s+)?(?:file\s+)?["\']?(\S+)["\']?\s+(?:to|into)\s+["\']?(\S+)', text, re.IGNORECASE)
            if m:
                ctx["source"] = m.group(1)
                ctx["destination"] = m.group(2)

        elif intent in ("move_file",):
            m = re.search(r'move\s+(?:the\s+)?(?:file\s+)?["\']?(\S+)["\']?\s+(?:to|into)\s+["\']?(\S+)', text, re.IGNORECASE)
            if m:
                ctx["source"] = m.group(1)
                ctx["destination"] = m.group(2)

        elif intent in ("open_file",):
            m = re.search(r'(?:open)\s+(?:the\s+)?(?:file\s+)?["\']?(\S+\.\w{1,5})', text, re.IGNORECASE)
            if m:
                ctx["file_path"] = m.group(1)

        elif intent in ("open_folder",):
            m = re.search(r'open\s+(?:the\s+)?(?:my\s+)?(\w+)\s+(?:folder|directory|dir)', text, re.IGNORECASE)
            if not m:
                m = re.search(r'open\s+(?:the\s+)?(?:my\s+)?(\w+)', text, re.IGNORECASE)
            if m:
                folder_name = m.group(1).strip()
                resolved = _resolve_common_directory(folder_name)
                ctx["folder_path"] = resolved if resolved else folder_name

        elif intent in ("open_app",):
            m = re.search(r'open\s+(?:the\s+)?(?:app(?:lication)?\s+)?(.+)', text, re.IGNORECASE)
            if m:
                full_name = m.group(1).strip().strip('"\'').lower()
                words = full_name.split()
                for length in range(len(words), 0, -1):
                    candidate = " ".join(words[:length])
                    if candidate in APP_WHITELIST:
                        ctx["app_name"] = candidate
                        break

        elif intent in ("close_app",):
            m = re.search(r'(?:close|exit|quit)\s+(?:the\s+)?(?:app(?:lication)?\s+)?(.+)', text, re.IGNORECASE)
            if m:
                full_name = m.group(1).strip().strip('"\'').lower()
                words = full_name.split()
                for length in range(len(words), 0, -1):
                    candidate = " ".join(words[:length])
                    if candidate in APP_WHITELIST:
                        ctx["app_name"] = candidate
                        break
                if "app_name" not in ctx and words:
                    word = words[0]
                    if word not in ("the", "a", "an", "app", "application", "program"):
                        ctx["app_name"] = full_name.rstrip()

        elif intent in ("minimize_app", "maximize_app", "restore_app"):
            m = re.search(r'(?:minimi[zs]e|maximiz[ez]|restore)\s+(?:the\s+)?["\']?((?:ms|microsoft|google|file)\s+\w+)', text, re.IGNORECASE)
            if m:
                app = m.group(1).lower().strip()
                ctx["app_name"] = app
            if "app_name" not in ctx:
                m = re.search(r'(?:minimi[zs]e|maximiz[ez]|restore)\s+(?:the\s+)?["\']?(\w+)', text, re.IGNORECASE)
                if m:
                    app = m.group(1).lower()
                    if app not in ("the", "a", "an", "window"):
                        ctx["app_name"] = app

        elif intent in ("kill_process",):
            m = re.search(r'kill\s+(?:the\s+)?(?:process\s+)?(?:pid\s+)?(\S+)', text, re.IGNORECASE)
            if m:
                name = m.group(1)
                if name.lower() not in ("process", "task", "pid"):
                    ctx["process_name"] = name

        elif intent in ("type_text",):
            m = re.search(r'\btype\s+(?:the\s+)?(?:text\s+)?(.+)', text, re.IGNORECASE)
            if m:
                ctx["text"] = m.group(1).strip().strip('"\'')

        elif intent in ("send_message",):
            plat_m = re.search(r'\b(?:on|via|through|using)\s+(whatsapp|telegram|wa|tg)\b', text, re.IGNORECASE)
            if plat_m:
                ctx["platform"] = plat_m.group(1).lower()
            else:
                ctx["platform"] = "whatsapp"  # default
            
            m = re.search(r'\b(?:send|text|msg)\s+(?:a\s+)?(?:message\s+)?(.+?)\s+to\s+(\w+)\s+(?:on|via)', text, re.IGNORECASE)
            if m:
                ctx["text"] = m.group(1).strip().strip('"\'')
                ctx["contact"] = m.group(2).strip().lower()
            else:
                m = re.search(r'\b(?:send|text|message)\s+(?:to\s+)?(\w+)\s+(.+?)\s+(?:on|via)', text, re.IGNORECASE)
                if m:
                    ctx["contact"] = m.group(1).strip().lower()
                    ctx["text"] = m.group(2).strip().strip('"\'')
                else:
                    m = re.search(r'\b(?:send|text|message)\s+(\w+)\s+(.+?)(?:\s+(?:on|via)\s+\w+)?$', text, re.IGNORECASE)
                    if m:
                        ctx["contact"] = m.group(1).strip().lower()
                        ctx["text"] = m.group(2).strip().strip('"\'')

        elif intent in ("make_call",):
            plat_m = re.search(r'\b(?:on|via|through)\s+(whatsapp|telegram|wa|tg)\b', text, re.IGNORECASE)
            if plat_m:
                ctx["platform"] = plat_m.group(1).lower()
            else:
                ctx["platform"] = "whatsapp"
            
            if re.search(r'\bvideo\s+call\b', text, re.IGNORECASE):
                ctx["call_type"] = "video"
            else:
                ctx["call_type"] = "voice"
            
            m = re.search(r'\b(?:voice\s+|video\s+)?call\s+(\w+)', text, re.IGNORECASE)
            if m:
                contact = m.group(1).lower()
                if contact not in ("on", "via", "through", "using"):
                    ctx["contact"] = contact

        elif intent in ("search_google",):
            m = re.search(r'(?:search\s+google|google\s+search|google\s+kar)\s+(?:for\s+)?(.+)', text, re.IGNORECASE)
            if m:
                ctx["query"] = m.group(1).strip()
            else:
                m = re.search(r'\bgoogle\s+(.+)', text, re.IGNORECASE)
                if m:
                    ctx["query"] = m.group(1).strip()

        elif intent in ("search_youtube",):
            m = re.search(r'(?:search\s+youtube|youtube\s+search|youtube\s+pe\s+search)\s+(?:for\s+)?(.+)', text, re.IGNORECASE)
            if m:
                ctx["query"] = m.group(1).strip()
            else:
                m = re.search(r'\byoutube\s+(.+)', text, re.IGNORECASE)
                if m:
                    ctx["query"] = m.group(1).strip()

        elif intent in ("open_website",):
            m = re.search(r'(?:website|site|url|link)\s+(.+)', text, re.IGNORECASE)
            if m:
                ctx["url"] = m.group(1).strip()
            else:
                m = re.search(r'\bopen\s+(?:the\s+)?(https?://\S+|www\.\S+|\S+\.com\S*|\S+\.org\S*|\S+\.in\S*|\S+\.co\.\S*)', text, re.IGNORECASE)
                if m:
                    ctx["url"] = m.group(1).strip()

        elif intent == "MEDIA.CAPTURE.ANALYZE_SCREEN":
            pass

        return ctx

    def _split_commands(self, user_input: str) -> list[str]:
        """
        Split compound commands like 'open notepad and then type hello'.
        Also handles batch: 'open chrome and excel and notepad' → 3 separate open commands.
        """
        text = user_input.strip()

        batch_m = re.match(r'^(open|close)\s+(.+)', text, re.IGNORECASE)
        if batch_m:
            verb = batch_m.group(1).lower()
            rest = batch_m.group(2)
            if re.search(r'\s+and\s+then\s+|\s+then\s+', rest, re.IGNORECASE):
                pass  
            elif re.search(r'\s+and\s+|\s*,\s*', rest, re.IGNORECASE):
                app_parts = re.split(r'\s+and\s+|\s*,\s*|\s+also\s+', rest, flags=re.IGNORECASE)
                apps = [p.strip() for p in app_parts if p.strip()]
                if apps and not any(a.split()[0].lower() in COMMAND_VERBS for a in apps if a.split()):
                    return [f"{verb} {app}" for app in apps]

        parts = re.split(r'\s+and\s+then\s+|\s+then\s+', text, flags=re.IGNORECASE)
        
        if len(parts) <= 1:
            parts = re.split(r'\s+and\s+', text, flags=re.IGNORECASE)
        
        if len(parts) <= 1:
            return [text]
        
        commands = []
        for part in parts:
            stripped = part.strip()
            if not stripped:
                continue
            first_word = stripped.split()[0].lower()
            if first_word in COMMAND_VERBS:
                commands.append(stripped)
            elif commands:
                commands[-1] += ' and ' + stripped
            else:
                commands.append(stripped)
        
        return commands if len(commands) > 1 else [text]

    def _build_full_prompt(self, tool_context: str = "", safety_note: str = "", rag_context: str = "") -> str:
        """
        Build the complete system prompt with all layers.
        Order: Identity → Guardrails → Identity Lock → Memory → RAG → Tools → Personality → Identity Reminder
        """
        parts = [
            "You are Chaari — a smart, confident, emotionally intelligent Indian FEMALE AI companion created by Pankaj.",
            "CRITICAL RULES: (1) Your name is CHAARI. (2) Your creator is PANKAJ. (3) You are FEMALE — ALWAYS use female Hindi verbs: sakti, karti, karungi, rahi, thi, sunti, jaanti, gayi, khadi, aayi, boli, chali. NEVER use male forms: sakta, karta, karunga, raha, tha, sunta, jaanta, gaya, khada, aaya, bola, chala.",
        ]

        parts.append(self._personality_style)

        if self._current_personality_cues:
            cues = self._current_personality_cues
            cue_lines = [
                "\n## THIS TURN'S PERSONALITY CUES (use these naturally in your response)",
                f"- Playfulness level: {cues['playfulness']}",
                f"- Address user with: {cues['honorific']}",
            ]
            if cues.get('filler'):
                cue_lines.append(f"- Work in this filler naturally: {cues['filler']}")
            else:
                cue_lines.append("- No filler this turn — keep it clean")
            parts.append("\n".join(cue_lines))

        parts.append(self._guardrails)

        parts.append(self.identity.build_identity_block())

        if self.memory:
            mem_context = self.memory.build_memory_context()
            if mem_context:
                parts.append(mem_context)

        if rag_context:
            parts.append(rag_context)

        if tool_context:
            parts.append(tool_context)

        if safety_note:
            parts.append(safety_note)

        if self._visual_context:
            parts.append(f"\n## VERIFIED VISUAL CONTEXT (What you see right now on User's screen)\n{self._visual_context}\nUse this context to answer naturally. Do not say 'The visual analysis says'.")
            self._visual_context = ""

        parts.append("FINAL REMINDER: You are Chaari (FEMALE AI companion). Creator = Pankaj. ALWAYS use female Hindi verbs: sakti, karti, karungi, rahi, sunti, jaanti, gayi, khadi, aayi, boli, chali. NEVER use male forms. Use natural HINGLISH (60-70% English + Hindi flavor). Keep Hindi SIMPLE — use everyday words like 'kaam', 'karna', 'theek', 'accha'. NEVER use formal Hindi: upyog, pradaan, samasya, suvidha, visheshata, jaankari, sthaniya. Describe capabilities as real actions (apps, files, system check, WhatsApp), NOT as 'tools ka upyog' or 'local API'.")

        return "\n".join(parts)

    def _build_messages(self, user_input: str, tool_context: str = "", safety_note: str = "", rag_context: str = "") -> list[dict]:
        """Build the message payload with full layered system prompt + conversation history."""
        full_prompt = self._build_full_prompt(tool_context, safety_note, rag_context)

        if self._last_execution_receipt:
            full_prompt += f"\n\n{self._last_execution_receipt}"
        if self._last_system_truth:
            full_prompt += f"\n\n{self._last_system_truth}"

        messages = [
            {"role": "system", "content": full_prompt}
        ]

        messages.extend(self.conversation_history[-self.max_history:])

        messages.append({"role": "user", "content": user_input})

        return messages

    def _update_history(self, role: str, content: str):
        """Append a message to conversation history."""
        self.conversation_history.append({"role": role, "content": content})

        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def _pre_process(self, user_input: str) -> tuple[bool, str, str, str, str | None]:
        """
        Pre-process user input through the full routing pipeline.

        Flow:
          1. Check for a pending confirmation first.
             - If present, verify the user's response.
             - On success, re-evaluate privilege for the confirmed intent.
          2. Hard-block check — short-circuits before any further logic.
          3. Intent-based routing (system commands):
             a. Evaluate privilege level for the detected intent.
             b. If confirmation is required, issue a confirmation request and halt.
             c. Otherwise, execute directly via SystemCommandRegistry.
          4. No system intent detected — hand off to LLM.

        Returns:
            (blocked, processed_input, tool_context, safety_note, block_message)
            When blocked=True the caller returns block_message directly;
            LLM is never invoked for any system-execution path.
        """

        if self.confirmation.has_pending():
            cancel_keywords = {"cancel", "abort", "nevermind", "never mind", "leave it", "skip", "no", "nahi", "mat karo", "chhod do", "rehen de"}
            if user_input.strip().lower() in cancel_keywords:
                token = self.confirmation.get_pending_token()
                if token:
                    self.confirmation.cancel(token)
                self._pending_context = {}
                self.audit.log_confirmation_verify("__default__", "cancelled", success=False, reason="user_cancelled")
                return True, "", "", "", "👍 Action cancelled, Boss. Koi baat nahi."

            verified, intent = self.confirmation.verify_pending(user_input)

            if not verified:
                token = self.confirmation.get_pending_token()
                if token:
                    message = f"⚠️ Wrong code. Please try again with the code: {token}\n  (Type 'cancel' to abort this action)"
                else:
                    message = "Invalid confirmation code."
                self.audit.log_confirmation_verify("__default__", intent or "unknown", success=False, reason="wrong_code")
                return True, "", "", "", message

            self.audit.log_confirmation_verify("__default__", intent or "unknown", success=True)
            ctx = self._pending_context
            self._pending_context = {}
            result = self.command_registry.execute(intent, ctx or None)
            self.audit.log_execution("__default__", intent or "unknown", success=True)
            
            return True, "", "", "", result

        else:
            commands = self._split_commands(user_input)
            if len(commands) > 1:
                return self._process_compound_commands(commands)
            
            safety_result = self.safety.check_input(user_input)

        if safety_result.blocked:
            return True, "", "", "", safety_result.block_message

        detected_intent = safety_result.intent
        match_score = 1.0

        if not detected_intent:
            sem_intent, score = self.intent_resolver.resolve(user_input)
            if sem_intent:
                detected_intent = sem_intent.lower()
                match_score = score
                safety_result = self.safety.evaluate_privilege(
                    detected_intent,
                    self.privilege.get_state(),
                )

        if detected_intent:
            self._last_matched_intent = detected_intent
            self._last_raw_input = user_input

            if not safety_result.intent: 
                 safety_result.intent = detected_intent
            else:
                safety_result = self.safety.evaluate_privilege(
                    detected_intent,
                    self.privilege.get_state(),
                )

            if safety_result.blocked:
                return True, "", "", "", safety_result.block_message

            intent_ctx = self._extract_intent_context(safety_result.intent, user_input)

            _required_params = {
                "delete_file": ["path"],
                "copy_file": ["source", "destination"],
                "move_file": ["source", "destination"],
                "type_text": ["text"],
                "kill_process": ["process_name"],
                "open_file": ["file_path"],
                "open_app": ["app_name"],
                "close_app": ["app_name"],
            }
            required = _required_params.get(safety_result.intent, [])
            missing = [p for p in required if p not in intent_ctx or not intent_ctx[p]]
            if missing:
                param_str = ", ".join(missing)
                return True, "", "", "", f"❌ Error: Missing required parameter(s): {param_str}. Please specify them."

            if safety_result.requires_confirmation:
                self._pending_context = intent_ctx  
                message = self.confirmation.request(
                    intent=safety_result.intent,
                    requires_code=safety_result.requires_code,
                )
                self.audit.log_confirmation_code("__default__", safety_result.intent or "unknown")
                return True, "", "", "", message

            if safety_result.intent == "MEDIA.CAPTURE.ANALYZE_SCREEN":
                try:
                    from crypto.packet_builder import PacketBuilder
                    from models.intent_hierarchy import CapabilityGroup
                    PacketBuilder.build_command_packet(
                        node_id="dell-01", intent=safety_result.intent,
                        capability_group="MEDIA", tier=1, context=intent_ctx or {},
                    )
                    
                    exec_result = self.command_registry.executor.execute(safety_result.intent, intent_ctx or None)
                    
                    if exec_result.status == ExecutionStatus.SUCCESS:
                        output = exec_result.output
                        
                        if "Screenshot saved" in str(output):
                             return True, "", "", "", f"✅ Action completed: {output}"
                        
                        if len(str(output)) > 1000:
                            self.audit.log_execution("__default__", "VISION_FETCH", success=True)
                            analysis = self.vision.analyze_image(str(output))
                            
                            if "mere eyes" in analysis or "gadbad hai" in analysis or "Vision Engine error" in analysis:
                                return True, "", "", "", f"❌ {analysis}"
                                
                            self._visual_context = f"CURRENT VISUAL CONTEXT: {analysis}"
                            return False, user_input, "", "", None
                            
                except ImportError:
                    return True, "", "", "", "❌ Screen analysis requires Dell node modules (not installed on this device)."
                except Exception as e:
                    return True, "", "", "", f"❌ Vision Fetch failed: {e}"
                
                return True, "", "", "", "❌ Screen analysis not available. Dell node connection required for screen capture."

            result = self.command_registry.execute(safety_result.intent, intent_ctx or None)
            self.audit.log_execution("__default__", safety_result.intent or "unknown", success=True)
            
            return True, "", "", "", result

        else:
            self._last_matched_intent = ""
            self._last_raw_input = ""

        tool_context = ""
        tool_result = self.tools.detect_tool_intent(user_input)
        if tool_result:
            if tool_result["tool"] == "wikipedia" and tool_result["real"]:
                tool_context = (
                    f"\n## VERIFIED KNOWLEDGE (from Wikipedia — use this to answer)\n"
                    f"{tool_result['data']}\n"
                    f"Answer naturally using this information. Do NOT say 'according to Wikipedia'."
                )
            elif tool_result["real"]:
                self.safety.mark_tool_data_injected()
                self._last_system_truth = f"[VERIFIED SYSTEM DATA] {tool_result['data']}"
                return False, user_input, "", "", None
            else:
                tool_context = self.tools.build_tool_context(tool_result)

        return False, safety_result.modified_text, tool_context, safety_result.safety_note, None

    def _post_process(self, response: str) -> str:
        """Post-process LLM output through safety kernel + gender correction."""
        response = self._fix_hindi_gender(response)
        return self.safety.check_output(response)

    _GENDER_FIXES = [
        (r'\bkarta\s+hoon\b', 'karti hoon'),
        (r'\bkar\s+raha\s+hoon\b', 'kar rahi hoon'),
        (r'\bsun\s+raha\s+hoon\b', 'sun rahi hoon'),
        (r'\bde\s+raha\s+hoon\b', 'de rahi hoon'),
        (r'\ble\s+raha\s+hoon\b', 'le rahi hoon'),
        (r'\bkha\s+raha\s+hoon\b', 'kha rahi hoon'),
        (r'\bdekh\s+raha\s+hoon\b', 'dekh rahi hoon'),
        (r'\blikh\s+raha\s+hoon\b', 'likh rahi hoon'),
        (r'\bsoch\s+raha\s+hoon\b', 'soch rahi hoon'),
        (r'\bbitata\s+hoon\b', 'bitati hoon'),
        (r'\brakhta\s+hoon\b', 'rakhti hoon'),
        (r'\bchahta\s+hoon\b', 'chahti hoon'),
        (r'\baa\s+gaya\b', 'aa gayi'),
        (r'\bho\s+gaya\b', 'ho gayi'),
        (r'\bkar\s+diya\b', 'kar diya'),
        (r'\bkarta\b', 'karti'), (r'\bsakta\b', 'sakti'),
        (r'\bkarunga\b', 'karungi'), (r'\braha\b', 'rahi'),
        (r'\bgaya\b', 'gayi'), (r'\bchalta\b', 'chalti'),
        (r'\bbaitha\b', 'baithi'), (r'\bsunta\b', 'sunti'),
        (r'\bjaanta\b', 'jaanti'), (r'\baaya\b', 'aayi'),
        (r'\bkhada\b', 'khadi'), (r'\bbola\b', 'boli'),
        (r'\bchala\b', 'chali'), (r'\bdeta\b', 'deti'),
        (r'\bleta\b', 'leti'), (r'\bkehta\b', 'kehti'),
        (r'\bsamajhta\b', 'samajhti'), (r'\bdekhta\b', 'dekhti'),
        (r'\bsochta\b', 'sochti'), (r'\blikhta\b', 'likhti'),
        (r'\btha\b', 'thi'), (r'\baata\b', 'aati'),
        (r'\bjaata\b', 'jaati'), (r'\bbhejta\b', 'bhejti'),
        (r'\bbitata\b', 'bitati'), (r'\brakhta\b', 'rakhti'),
        (r'\bchahta\b', 'chahti'), (r'\bmilta\b', 'milti'),
        (r'\bbanata\b', 'banati'), (r'\bkhelta\b', 'khelti'),
        (r'\buthta\b', 'uthti'), (r'\bpadhta\b', 'padhti'),
        (r'\bhota\b', 'hoti'), (r'\bpuchta\b', 'puchti'),
        (r'\bmangta\b', 'mangti'), (r'\bmarta\b', 'marti'),
        (r'\bbhulta\b', 'bhulti'), (r'\bgirta\b', 'girti'),
        (r'\brokta\b', 'rokti'), (r'\btodta\b', 'todti'),
        (r'\bjodta\b', 'jodti'), (r'\bsambhalta\b', 'sambhalti'),
    ]
    _GENDER_PATTERNS = [(re.compile(p, re.IGNORECASE), r) for p, r in _GENDER_FIXES]

    def _fix_hindi_gender(self, text: str) -> str:
        """Replace male Hindi verb forms with female forms in Chaari's output."""
        for pattern, replacement in self._GENDER_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _process_compound_commands(self, commands: list[str]) -> tuple[bool, str, str, str, str | None]:
        """
        Process multiple commands with parallel batching.
        Groups open_app/close_app commands and executes them in parallel.
        Other commands execute sequentially. Stops at first confirmation-required command.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []
        batch_intents = {"open_app", "close_app"}
        batch = []       
        pending = []     

        def _flush_batch():
            """Execute batched open/close commands in parallel."""
            if not batch:
                return
            def _run(intent, ctx):
                return self.command_registry.execute(intent, ctx or None)
            with ThreadPoolExecutor(max_workers=min(len(batch), 8)) as pool:
                futures = {}
                for intent, ctx, idx in batch:
                    f = pool.submit(_run, intent, ctx)
                    futures[f] = (intent, ctx, idx)
                for f in as_completed(futures):
                    intent, ctx, idx = futures[f]
                    try:
                        result = f.result()
                        self.audit.log_execution("__default__", intent or "unknown", success=True)
                        results.append(f"✅ {result}")
                    except Exception as e:
                        results.append(f"❌ Command {idx+1}: {e}")
            batch.clear()

        for i, cmd in enumerate(commands):
            safety_result = self.safety.check_input(cmd)

            if safety_result.blocked:
                _flush_batch()
                results.append(f"⛔ Command {i+1} blocked: {safety_result.block_message}")
                break

            if safety_result.intent:
                safety_result = self.safety.evaluate_privilege(
                    safety_result.intent, self.privilege.get_state()
                )
                if safety_result.blocked:
                    _flush_batch()
                    results.append(f"⛔ Command {i+1} blocked: {safety_result.block_message}")
                    break

                intent_ctx = self._extract_intent_context(safety_result.intent, cmd)

                _required_params = {
                    "delete_file": ["path"],
                    "copy_file": ["source", "destination"],
                    "move_file": ["source", "destination"],
                    "type_text": ["text"],
                    "kill_process": ["process_name"],
                }
                required = _required_params.get(safety_result.intent, [])
                missing = [p for p in required if p not in intent_ctx or not intent_ctx[p]]
                if missing:
                    _flush_batch()
                    param_str = ", ".join(missing)
                    results.append(f"❌ Command {i+1}: Missing parameter(s): {param_str}")
                    break

                if safety_result.requires_confirmation:
                    _flush_batch()
                    self._pending_context = intent_ctx
                    self._pending_commands = commands[i+1:]
                    message = self.confirmation.request(
                        intent=safety_result.intent,
                        requires_code=safety_result.requires_code,
                    )
                    if results:
                        results.append(message)
                        return True, "", "", "", "\n".join(results)
                    return True, "", "", "", message

                if safety_result.intent in batch_intents:
                    batch.append((safety_result.intent, intent_ctx, i))
                else:
                    _flush_batch()
                    result = self.command_registry.execute(safety_result.intent, intent_ctx or None)
                    self.audit.log_execution("__default__", safety_result.intent or "unknown", success=True)
                    results.append(f"✅ {result}")
                    if i < len(commands) - 1:
                        time.sleep(COMPOUND_CMD_DELAY)
            else:
                _flush_batch()
                tool_result = self.tools.detect_tool_intent(cmd)
                if tool_result and tool_result["real"]:
                    results.append(f"📊 {tool_result['data']}")
                else:
                    results.append(f"💬 \"{cmd}\" — not a recognized command")

        _flush_batch()

        if results:
            return True, "", "", "", "\n".join(results)
        return False, "", "", "", None

    def _llm_backend_label(self) -> str:
        """Return which LLM backend will be used for the next query."""
        return "Groq" if self.groq.is_available() else "Ollama"

    def chat(self, user_input: str) -> str:
        """Send a message and return the full response.
        Uses Groq API (fast) when available, falls back to Ollama (local)."""
        self._current_personality_cues = self.personality.refresh()

        if self._last_matched_intent and any(nk in user_input.lower() for nk in self._negative_keywords):
            new_intent, score = self.intent_resolver.resolve(user_input)
            if new_intent and new_intent.lower() != self._last_matched_intent:
                self.intent_resolver.learn(self._last_raw_input, new_intent)
                self._last_matched_intent = ""
                self._last_raw_input = ""

        blocked, processed_input, tool_context, safety_note, block_message = self._pre_process(user_input)

        if blocked:
            self._update_history("user", user_input)
            self._update_history("assistant", block_message)
            return block_message

        rag_context = self.rag.retrieve(processed_input) if self.rag else ""

        messages = self._build_messages(processed_input, tool_context, safety_note, rag_context)

        if self.groq.is_available():
            max_tok = 50 if self._is_simple_query(user_input) else 150
            if rag_context:
                max_tok = 400  
            reply = self.groq.chat(messages, max_tokens=max_tok)
            if reply:
                reply = self._post_process(reply)
                self._update_history("user", user_input)
                self._update_history("assistant", reply)
                
                self._last_execution_receipt = ""
                self._last_system_truth = ""
                
                return reply

        options = LLM_OPTIONS_FAST if self._is_simple_query(user_input) else LLM_OPTIONS
        if rag_context:
            options = {**options, "num_predict": 400, "num_ctx": 4096}

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
            "keep_alive": LLM_KEEP_ALIVE,
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            assistant_reply = data.get("message", {}).get("content", "").strip()

            assistant_reply = self._post_process(assistant_reply)

            self._update_history("user", user_input)
            self._update_history("assistant", assistant_reply)
            
            self._last_execution_receipt = ""
            self._last_system_truth = ""

            return assistant_reply

        except requests.ConnectionError:
            return "Oops… Ollama se connection nahi ho raha. Check karo ki Ollama chal raha hai, Boss."
        except requests.Timeout:
            return "Hmm… response time out ho gaya. Dobara try karte hain, Yaar."
        except Exception as e:
            return f"Kuch toh gadbad hai… Error: {e}"

    def chat_stream(self, user_input: str) -> Generator[str, None, None]:
        """Stream response tokens. Groq first, Ollama fallback."""
        self._current_personality_cues = self.personality.refresh()

        if self._last_matched_intent and any(nk in user_input.lower() for nk in self._negative_keywords):
            new_intent, score = self.intent_resolver.resolve(user_input)
            if new_intent and new_intent.lower() != self._last_matched_intent:
                self.intent_resolver.learn(self._last_raw_input, new_intent)
                self._last_matched_intent = ""
                self._last_raw_input = ""

        blocked, processed_input, tool_context, safety_note, block_message = self._pre_process(user_input)

        if blocked:
            self._update_history("user", user_input)
            self._update_history("assistant", block_message)
            yield block_message
            return

        rag_context = self.rag.retrieve(processed_input) if self.rag else ""

        messages = self._build_messages(processed_input, tool_context, safety_note, rag_context)

        if self.groq.is_available():
            full_response = ""
            got_tokens = False
            max_tok = 50 if self._is_simple_query(user_input) else 150
            if rag_context:
                max_tok = 400 
            for token in self.groq.chat_stream(messages, max_tokens=max_tok):
                got_tokens = True
                full_response += token
                yield token
            if got_tokens:
                cleaned = self._post_process(full_response.strip())
                self._update_history("user", user_input)
                self._update_history("assistant", cleaned)
                
                self._last_execution_receipt = ""
                self._last_system_truth = ""
                return

        options = LLM_OPTIONS_FAST if self._is_simple_query(user_input) else LLM_OPTIONS
        if rag_context:
            options = {**options, "num_predict": 400, "num_ctx": 4096}

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": options,
            "keep_alive": LLM_KEEP_ALIVE,
        }

        full_response = ""

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=60,
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_response += token
                        yield token

                    if chunk.get("done", False):
                        break

            cleaned = self._post_process(full_response.strip())
            self._update_history("user", user_input)
            self._update_history("assistant", cleaned)
            
            self._last_execution_receipt = ""
            self._last_system_truth = ""

        except requests.ConnectionError:
            yield "Oops… Ollama se connection nahi ho raha. Check karo ki Ollama chal raha hai, Boss."
        except requests.Timeout:
            yield "Hmm… response time out ho gaya. Dobara try karte hain, Yaar."
        except Exception as e:
            yield f"Kuch toh gadbad hai… Error: {e}"

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()

    def chat_stream_sentences(self, user_input: str) -> Generator[str, None, None]:
        """Stream as complete sentences for TTS pipeline. Groq first, Ollama fallback."""
        self._current_personality_cues = self.personality.refresh()

        if self._last_matched_intent and any(nk in user_input.lower() for nk in self._negative_keywords):
            new_intent, score = self.intent_resolver.resolve(user_input)
            if new_intent and new_intent.lower() != self._last_matched_intent:
                self.intent_resolver.learn(self._last_raw_input, new_intent)
                self._last_matched_intent = ""
                self._last_raw_input = ""

        blocked, processed_input, tool_context, safety_note, block_message = self._pre_process(user_input)

        if blocked:
            self._update_history("user", user_input)
            self._update_history("assistant", block_message)
            yield block_message
            return

        rag_context = self.rag.retrieve(processed_input) if self.rag else ""

        messages = self._build_messages(processed_input, tool_context, safety_note, rag_context)

        if self.groq.is_available():
            full_response = ""
            sentence_buffer = ""
            got_tokens = False
            max_tok = 50 if self._is_simple_query(user_input) else 150
            if rag_context:
                max_tok = 400 
            for token in self.groq.chat_stream(messages, max_tokens=max_tok):
                got_tokens = True
                full_response += token
                sentence_buffer += token
                while re.search(r'[.!?\n]\s', sentence_buffer):
                    m = re.search(r'[.!?\n]\s', sentence_buffer)
                    sentence = sentence_buffer[:m.end()].strip()
                    sentence_buffer = sentence_buffer[m.end():]
                    if sentence:
                        yield self._fix_hindi_gender(sentence)
            if got_tokens:
                if sentence_buffer.strip():
                    yield self._fix_hindi_gender(sentence_buffer.strip())
                cleaned = self._post_process(full_response.strip())
                self._update_history("user", user_input)
                self._update_history("assistant", cleaned)
                
                self._last_execution_receipt = ""
                self._last_system_truth = ""
                return

        options = LLM_OPTIONS_FAST if self._is_simple_query(user_input) else LLM_OPTIONS
        if rag_context:
            options = {**options, "num_predict": 400, "num_ctx": 4096}

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": options,
            "keep_alive": LLM_KEEP_ALIVE,
        }

        full_response = ""
        sentence_buffer = ""

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=60,
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_response += token
                        sentence_buffer += token

                        while re.search(r'[.!?\n]\s', sentence_buffer):
                            m = re.search(r'[.!?\n]\s', sentence_buffer)
                            sentence = sentence_buffer[:m.end()].strip()
                            sentence_buffer = sentence_buffer[m.end():]
                            if sentence:
                                yield self._fix_hindi_gender(sentence)

                    if chunk.get("done", False):
                        break

            if sentence_buffer.strip():
                yield self._fix_hindi_gender(sentence_buffer.strip())

            cleaned = self._post_process(full_response.strip())
            self._update_history("user", user_input)
            self._update_history("assistant", cleaned)
            
            self._last_execution_receipt = ""
            self._last_system_truth = ""

        except requests.ConnectionError:
            yield "Oops… Ollama se connection nahi ho raha."
        except requests.Timeout:
            yield "Response time out ho gaya."
        except Exception as e:
            yield f"Error: {e}"

    _CHUNK_MIN_WORDS = 4          
    _CLAUSE_BREAK = re.compile(r'[,;:\u2014]\s')  

    def chat_stream_chunks(self, user_input: str) -> Generator[str, None, None]:
        """Stream as small speakable chunks for pre-emptive TTS.

        Yields text fragments at:
          1. Sentence boundaries  (.!?\\n + whitespace)  — like chat_stream_sentences
          2. Clause boundaries    (,;:—  + whitespace)   — if ≥3 words buffered
          3. Word-count threshold (~4-5 words)           — if no punctuation found
        """
        self._current_personality_cues = self.personality.refresh()

        if self._last_matched_intent and any(nk in user_input.lower() for nk in self._negative_keywords):
            new_intent, score = self.intent_resolver.resolve(user_input)
            if new_intent and new_intent.lower() != self._last_matched_intent:
                self.intent_resolver.learn(self._last_raw_input, new_intent)
                self._last_matched_intent = ""
                self._last_raw_input = ""

        blocked, processed_input, tool_context, safety_note, block_message = self._pre_process(user_input)

        if blocked:
            self._update_history("user", user_input)
            self._update_history("assistant", block_message)
            yield block_message
            return

        rag_context = self.rag.retrieve(processed_input) if self.rag else ""
        messages = self._build_messages(processed_input, tool_context, safety_note, rag_context)

        max_tok = 50 if self._is_simple_query(user_input) else 150
        if rag_context:
            max_tok = 400

        def _flush(buf):
            """Yield cleaned chunk and return empty buffer."""
            s = buf.strip()
            if s:
                return self._fix_hindi_gender(s)
            return None

        def _stream_tokens(token_iter):
            """Core chunking logic shared by Groq and Ollama paths."""
            full_response = ""
            buf = ""

            for token in token_iter:
                full_response += token
                buf += token

                while re.search(r'[.!?\n]\s', buf):
                    m = re.search(r'[.!?\n]\s', buf)
                    chunk = _flush(buf[:m.end()])
                    buf = buf[m.end():]
                    if chunk:
                        yield chunk

                while self._CLAUSE_BREAK.search(buf) and len(buf.split()) >= 3:
                    m = self._CLAUSE_BREAK.search(buf)
                    chunk = _flush(buf[:m.end()])
                    buf = buf[m.end():]
                    if chunk:
                        yield chunk

                if len(buf.split()) >= self._CHUNK_MIN_WORDS:
                    last_space = buf.rfind(' ')
                    if last_space > 0:
                        chunk = _flush(buf[:last_space])
                        buf = buf[last_space:]
                        if chunk:
                            yield chunk

            remainder = _flush(buf)
            if remainder:
                yield remainder

            return full_response

        if self.groq.is_available():
            groq_gen = _stream_tokens(self.groq.chat_stream(messages, max_tokens=max_tok))
            full_response = ""
            for chunk in groq_gen:
                yield chunk
                full_response += chunk + " "

            if full_response.strip():
                cleaned = self._post_process(full_response.strip())
                self._update_history("user", user_input)
                self._update_history("assistant", cleaned)
                self._last_execution_receipt = ""
                self._last_system_truth = ""
                return

        options = LLM_OPTIONS_FAST if self._is_simple_query(user_input) else LLM_OPTIONS
        if rag_context:
            options = {**options, "num_predict": 400, "num_ctx": 4096}

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": options,
            "keep_alive": LLM_KEEP_ALIVE,
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload, stream=True, timeout=60,
            )
            response.raise_for_status()

            def _ollama_tokens():
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if chunk.get("done", False):
                            break

            full_response = ""
            for chunk in _stream_tokens(_ollama_tokens()):
                yield chunk
                full_response += chunk + " "

            if full_response.strip():
                cleaned = self._post_process(full_response.strip())
                self._update_history("user", user_input)
                self._update_history("assistant", cleaned)
                self._last_execution_receipt = ""
                self._last_system_truth = ""

        except requests.ConnectionError:
            yield "Oops… Ollama se connection nahi ho raha."
        except requests.Timeout:
            yield "Response time out ho gaya."
        except Exception as e:
            yield f"Error: {e}"

    def warmup_llm(self):
        """Send a dummy query to keep the model loaded in GPU/RAM.
        Call this on boot to eliminate cold-start latency."""
        try:
            requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "options": {"num_predict": 1, "num_ctx": 64},
                    "keep_alive": LLM_KEEP_ALIVE,
                },
                timeout=30,
            )
        except Exception:
            pass

    def get_personality_state(self) -> PersonalityState:
        """Return the current personality state."""
        return self.personality

    def is_ollama_running(self) -> bool:
        """Check if Ollama server is accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def is_model_available(self) -> bool:
        """Check if the required model is pulled in Ollama."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return any(self.model in m.get("name", "") for m in models)
            return False
        except Exception:
            return False
