import { useRef } from 'react'

const BADGE_META = {
  SEEKER:            { icon: '🌱', label: 'Seeker' },
  CATALYST:          { icon: '🔥', label: 'Catalyst' },
  GUARDIAN:          { icon: '🛡', label: 'Guardian' },
  EXPLORER:          { icon: '🧭', label: 'Explorer' },
  ARCHITECT:         { icon: '🏗', label: 'Architect' },
  FIRST_RIPPLE:      { icon: '💧', label: 'First Ripple' },
  WAVE_MAKER:        { icon: '🌊', label: 'Wave Maker' },
  IMPACT_MULTIPLIER: { icon: '⚡', label: 'Impact Multiplier' },
  TRUTH_SEEKER:      { icon: '🔍', label: 'Truth Seeker' },
  VERIFIED_GIVER:    { icon: '🛡', label: 'Verified Giver' },
  WATCHDOG:          { icon: '👁', label: 'Watchdog' },
  STORY_BUILDER:     { icon: '📖', label: 'Story Builder' },
  FOUNDATION_READY:  { icon: '🏛', label: 'Foundation Ready' },
  STIFTER:           { icon: '👑', label: 'Stifter' },
}

const PERSONA_HEADLINE = {
  CATALYST:  "I'm building systemic change.",
  GUARDIAN:  "I'm protecting what matters most.",
  EXPLORER:  "I'm discovering where help is needed.",
  ARCHITECT: "I'm designing the infrastructure of change.",
}

const LINKEDIN_SHARE_URL = 'https://www.linkedin.com/sharing/share-offsite/'

export default function ShareCard({
  persona,
  mbtiType,
  earnedBadges,
  beneficiaries,
  ngoCount,
  contributed,
  onClose,
}) {
  const cardRef = useRef(null)
  const personaMeta = BADGE_META[persona] ?? { icon: '🌱', label: persona }
  const headline = PERSONA_HEADLINE[persona] ?? "I'm giving with purpose."

  // Badges to display on card (exclude persona-specific identity duplicates)
  const displayBadges = [...earnedBadges]
    .filter(b => b !== 'SEEKER' && b !== persona)
    .slice(0, 4)

  const shareText = [
    `${personaMeta.icon} ${personaMeta.label} Giver`,
    headline,
    `${beneficiaries} people · ${ngoCount} causes · €${contributed} contributed`,
    `Verified on Polygon · Legatum by LBBW`,
    `Start your impact journey → legatum.bwbank.de`,
  ].join('\n\n')

  const handleLinkedIn = () => {
    const url = `${LINKEDIN_SHARE_URL}?url=${encodeURIComponent('https://legatum.bwbank.de')}&summary=${encodeURIComponent(shareText)}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(shareText).catch(() => {})
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="w-full max-w-sm space-y-4"
        onClick={e => e.stopPropagation()}
      >
        {/* The shareable card */}
        <div
          ref={cardRef}
          className="relative overflow-hidden rounded-2xl border border-cyan-500/40 bg-gradient-to-br from-[#0d1520] via-[#0a1a2e] to-[#0f1e14] p-6"
        >
          {/* Glow */}
          <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-teal-500/5 pointer-events-none" />

          {/* Header */}
          <div className="flex items-center gap-3 mb-4">
            <span className="text-4xl">{personaMeta.icon}</span>
            <div>
              <p className="text-[10px] text-cyan-400/70 uppercase tracking-widest">Legatum Impact Passport</p>
              <h2 className="text-lg font-bold text-white leading-tight">
                {personaMeta.label} Giver
              </h2>
              <p className="text-xs text-gray-400">{mbtiType}</p>
            </div>
          </div>

          {/* Headline */}
          <p className="text-sm text-gray-200 italic mb-5">
            "{headline}"
          </p>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-2 mb-5">
            {[
              { value: beneficiaries, label: 'people' },
              { value: ngoCount, label: 'causes' },
              { value: `€${contributed}`, label: 'contributed' },
            ].map(({ value, label }) => (
              <div key={label} className="text-center">
                <div className="text-xl font-bold text-cyan-400">{value}</div>
                <div className="text-[10px] text-gray-500">{label}</div>
              </div>
            ))}
          </div>

          {/* Badges */}
          {displayBadges.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-5">
              {displayBadges.map(b => {
                const m = BADGE_META[b]
                if (!m) return null
                return (
                  <span
                    key={b}
                    className="text-xs text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 rounded-full px-2 py-0.5"
                  >
                    {m.icon} {m.label}
                  </span>
                )
              })}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between pt-3 border-t border-white/5">
            <div>
              <p className="text-[10px] text-gray-500">Verified on Polygon · Legatum</p>
              <p className="text-[10px] text-gray-600">Powered by LBBW</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-cyan-400/70">Start your journey →</p>
              <p className="text-[10px] text-gray-500">legatum.bwbank.de</p>
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            onClick={handleLinkedIn}
            className="flex-1 flex items-center justify-center gap-2 text-sm font-semibold text-white bg-[#0a66c2] hover:bg-[#0957a8] rounded-xl py-3 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            Share on LinkedIn
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center justify-center gap-1.5 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-xl px-4 py-3 transition-colors"
          >
            📋 Copy
          </button>
          <button
            onClick={onClose}
            className="flex items-center justify-center text-gray-500 hover:text-gray-300 border border-gray-800 hover:border-gray-700 rounded-xl px-3 py-3 transition-colors"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  )
}
