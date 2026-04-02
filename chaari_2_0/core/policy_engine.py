# CHAARI 2.0 — core/policy_engine.py — Layer 2: PolicyEngine

# Responsibility: Define governance rules & assign tier levels to system intents
#
# PolicyEngine answers:
#   • What tier is this intent? (Tier 0-3)
#   • What friction is required? (none, confirmation, code, creator_only)
#   • Is this action allowed at current privilege level?

from enum import Enum
from dataclasses import dataclass
from core.system_intent import SystemIntent



class Tier(Enum):
    """Action severity tier."""
    TIER_0 = 0  
    TIER_1 = 1  
    TIER_2 = 2  
    TIER_3 = 3  


class FrictionPath(Enum):
    """What confirmation is required for this action."""
    NONE = "none"  
    CONFIRMATION = "confirmation"  
    CODE_REQUIRED = "code_required"  
    CREATOR_ONLY = "creator_only"  


@dataclass
class PolicyDecision:
    """Decision made by PolicyEngine."""
    tier: Tier
    friction_path: FrictionPath
    requires_confirmation: bool
    requires_code: bool
    requires_creator_mode: bool
    friction_message: str


class PolicyEngine:
    """
    Layer 2 — Governance engine.
    
    Maintains mapping of SystemIntent → Tier → FrictionPath.
    Provides policy decisions for routing through confirmation/execution layers.
    """

    def __init__(self):
        """Initialize policy engine with default tier assignments."""
        self.tier_map = {
            SystemIntent.OPEN_APP: Tier.TIER_1,
            SystemIntent.CLOSE_APP: Tier.TIER_1,
            SystemIntent.MINIMIZE_APP: Tier.TIER_1,
            SystemIntent.MAXIMIZE_APP: Tier.TIER_1,
            SystemIntent.RESTORE_APP: Tier.TIER_1,
            SystemIntent.CREATE_FILE: Tier.TIER_1,
            SystemIntent.COPY_FILE: Tier.TIER_1,
            SystemIntent.TYPE_TEXT: Tier.TIER_1,
            SystemIntent.SEND_MESSAGE: Tier.TIER_1,
            SystemIntent.MAKE_CALL: Tier.TIER_1,
            
            SystemIntent.SHUTDOWN: Tier.TIER_2,
            SystemIntent.RESTART: Tier.TIER_2,
            SystemIntent.DELETE_FILE: Tier.TIER_2,
            SystemIntent.MOVE_FILE: Tier.TIER_2,
            
            SystemIntent.FORMAT_DISK: Tier.TIER_3,
            SystemIntent.KILL_PROCESS: Tier.TIER_3,
            SystemIntent.MODIFY_REGISTRY: Tier.TIER_3,
        }

        self.friction_map = {
            Tier.TIER_0: FrictionPath.NONE,
            Tier.TIER_1: FrictionPath.CODE_REQUIRED,
            Tier.TIER_2: FrictionPath.CODE_REQUIRED,
            Tier.TIER_3: FrictionPath.CREATOR_ONLY,
        }

        self.friction_messages = {
            Tier.TIER_0: "This is conversational. Proceeding.",
            Tier.TIER_1: "This requires confirmation. Please enter the code to proceed.",
            Tier.TIER_2: "This is destructive. You must confirm with a code.",
            Tier.TIER_3: "This is critical. Creator mode is required.",
        }

    def decide(self, intent: SystemIntent | None) -> PolicyDecision:
        """
        Make a policy decision for the given intent.

        Args:
            intent: The detected SystemIntent (or None for conversational)

        Returns:
            PolicyDecision with tier, friction path, and requirements
        """
        if not intent:
            return PolicyDecision(
                tier=Tier.TIER_0,
                friction_path=FrictionPath.NONE,
                requires_confirmation=False,
                requires_code=False,
                requires_creator_mode=False,
                friction_message=self.friction_messages[Tier.TIER_0],
            )

        tier = self.tier_map.get(intent, Tier.TIER_0)
        friction_path = self.friction_map[tier]

        decision = PolicyDecision(
            tier=tier,
            friction_path=friction_path,
            requires_confirmation=tier in (Tier.TIER_1, Tier.TIER_2),
            requires_code=tier in (Tier.TIER_1, Tier.TIER_2),
            requires_creator_mode=tier == Tier.TIER_3,
            friction_message=self.friction_messages[tier],
        )

        return decision

    def assign_tier(self, intent: SystemIntent | None) -> Tier:
        """
        Assign a tier to the given intent.

        Args:
            intent: The SystemIntent (or None)

        Returns:
            Tier (0-3)
        """
        if not intent:
            return Tier.TIER_0
        return self.tier_map.get(intent, Tier.TIER_0)

    def get_friction_path(self, tier: Tier) -> FrictionPath:
        """
        Get the friction path required for a tier.

        Args:
            tier: The tier level

        Returns:
            FrictionPath (none, confirmation, code_required, creator_only)
        """
        return self.friction_map.get(tier, FrictionPath.NONE)

    def requires_confirmation(self, intent: SystemIntent | None) -> bool:
        """Check if intent requires confirmation code."""
        tier = self.assign_tier(intent)
        return tier in (Tier.TIER_1, Tier.TIER_2)

    def requires_creator_mode(self, intent: SystemIntent | None) -> bool:
        """Check if intent requires creator mode."""
        tier = self.assign_tier(intent)
        return tier == Tier.TIER_3

    def is_conversational(self, intent: SystemIntent | None) -> bool:
        """Check if intent is conversational (no friction)."""
        tier = self.assign_tier(intent)
        return tier == Tier.TIER_0

    def register_intent(self, intent_name: str, tier: Tier):
        """
        Register a new intent with a tier level.
        (Admin only - for adding new intents)

        Args:
            intent_name: The intent identifier
            tier: The tier level
        """
        self.tier_map[intent_name.lower()] = tier

    def list_policies(self) -> dict:
        """Return all current policies (for debugging)."""
        policies = {}
        for intent, tier in self.tier_map.items():
            friction = self.friction_map[tier]
            policies[intent] = {
                "tier": tier.name,
                "friction": friction.value,
            }
        return policies
