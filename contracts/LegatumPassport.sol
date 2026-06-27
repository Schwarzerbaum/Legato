// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * LEGATUM Impact Passport
 * Soulbound NFT — non-transferable giving identity for philanthropic journeys.
 * Minted once per address on persona completion; badges accumulate through the
 * 9-layer LEGATUM pipeline gates.
 *
 * Deployed on Polygon Mumbai for HackXplore 2026 (LBBW).
 */
contract LegatumPassport {

    // ─── Structs ─────────────────────────────────────────────────────────────

    struct Badge {
        string badgeType;   // e.g. "SEEKER", "FIRST_RIPPLE", "FOUNDATION_READY"
        string metadata;    // persona name, amount, ngo count, etc.
        uint256 earnedAt;
        uint8   tier;       // 1=Identity, 2=Impact, 3=Verification, 4=Journey
    }

    struct Passport {
        address owner;
        string  persona;    // "Catalyst" | "Guardian" | "Explorer" | "Architect"
        string  mbtiType;   // "INTJ" | "ENFP" | etc.
        Badge[] badges;
        uint256 createdAt;
        bool    exists;
    }

    // ─── State ────────────────────────────────────────────────────────────────

    mapping(address => Passport) private _passports;
    uint256 public totalPassports;

    // ─── Events ───────────────────────────────────────────────────────────────

    event PassportCreated(address indexed owner, string persona, uint256 timestamp);
    event BadgeEarned(address indexed owner, string badgeType, uint8 tier, uint256 timestamp);

    // ─── Badge type constants (for frontend mapping) ─────────────────────────

    // Tier 1 — Identity
    string public constant BADGE_SEEKER       = "SEEKER";
    string public constant BADGE_CATALYST     = "CATALYST";
    string public constant BADGE_GUARDIAN     = "GUARDIAN";
    string public constant BADGE_EXPLORER     = "EXPLORER";
    string public constant BADGE_ARCHITECT    = "ARCHITECT";

    // Tier 2 — Impact
    string public constant BADGE_FIRST_RIPPLE        = "FIRST_RIPPLE";
    string public constant BADGE_WAVE_MAKER          = "WAVE_MAKER";
    string public constant BADGE_IMPACT_MULTIPLIER   = "IMPACT_MULTIPLIER";

    // Tier 3 — Verification
    string public constant BADGE_TRUTH_SEEKER        = "TRUTH_SEEKER";
    string public constant BADGE_VERIFIED_GIVER      = "VERIFIED_GIVER";
    string public constant BADGE_WATCHDOG            = "WATCHDOG";

    // Tier 4 — Journey
    string public constant BADGE_STORY_BUILDER       = "STORY_BUILDER";
    string public constant BADGE_FOUNDATION_READY    = "FOUNDATION_READY";
    string public constant BADGE_STIFTER             = "STIFTER";

    // ─── Core functions ───────────────────────────────────────────────────────

    /**
     * Mint passport. Called once when user completes the 12-question
     * persona engine (Layer 2). Auto-awards SEEKER + persona-specific badge.
     */
    function createPassport(
        string memory persona,
        string memory mbtiType
    ) external {
        require(!_passports[msg.sender].exists, "Passport already exists");

        Passport storage p = _passports[msg.sender];
        p.owner     = msg.sender;
        p.persona   = persona;
        p.mbtiType  = mbtiType;
        p.createdAt = block.timestamp;
        p.exists    = true;

        // Tier 1a: universal seeker badge
        p.badges.push(Badge({
            badgeType: BADGE_SEEKER,
            metadata:  "",
            earnedAt:  block.timestamp,
            tier:      1
        }));

        // Tier 1b: persona-specific badge
        p.badges.push(Badge({
            badgeType: persona,   // "CATALYST" | "GUARDIAN" | "EXPLORER" | "ARCHITECT"
            metadata:  mbtiType,
            earnedAt:  block.timestamp,
            tier:      1
        }));

        totalPassports++;

        emit PassportCreated(msg.sender, persona, block.timestamp);
        emit BadgeEarned(msg.sender, BADGE_SEEKER, 1, block.timestamp);
        emit BadgeEarned(msg.sender, persona, 1, block.timestamp);
    }

    /**
     * Award a badge. Called at each pipeline gate by the LEGATUM backend.
     * Tier 2 (impact), Tier 3 (verification), Tier 4 (journey).
     */
    function awardBadge(
        string memory badgeType,
        string memory metadata,
        uint8         tier
    ) external {
        require(_passports[msg.sender].exists, "Create passport first");
        require(tier >= 1 && tier <= 4, "Invalid tier");

        _passports[msg.sender].badges.push(Badge({
            badgeType: badgeType,
            metadata:  metadata,
            earnedAt:  block.timestamp,
            tier:      tier
        }));

        emit BadgeEarned(msg.sender, badgeType, tier, block.timestamp);
    }

    // ─── Read functions ───────────────────────────────────────────────────────

    function getPassport(address owner)
        external view
        returns (
            string  memory persona,
            string  memory mbtiType,
            Badge[] memory badges,
            uint256        createdAt
        )
    {
        Passport storage p = _passports[owner];
        require(p.exists, "No passport found");
        return (p.persona, p.mbtiType, p.badges, p.createdAt);
    }

    function hasBadge(address owner, string memory badgeType)
        external view returns (bool)
    {
        Passport storage p = _passports[owner];
        if (!p.exists) return false;
        for (uint i = 0; i < p.badges.length; i++) {
            if (keccak256(bytes(p.badges[i].badgeType)) == keccak256(bytes(badgeType))) {
                return true;
            }
        }
        return false;
    }

    function getBadgeCount(address owner) external view returns (uint256) {
        if (!_passports[owner].exists) return 0;
        return _passports[owner].badges.length;
    }

    function hasPassport(address owner) external view returns (bool) {
        return _passports[owner].exists;
    }

    // ─── Soulbound enforcement ────────────────────────────────────────────────

    function transfer() external pure {
        revert("Legatum Passport is soulbound and non-transferable");
    }

    function transferFrom() external pure {
        revert("Legatum Passport is soulbound and non-transferable");
    }

    function approve() external pure {
        revert("Legatum Passport is soulbound and non-transferable");
    }
}
