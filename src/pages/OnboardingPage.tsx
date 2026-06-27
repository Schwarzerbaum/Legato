import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight, Heart, Check, Sparkles, ArrowUpRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'
import { CAUSE_THEMES } from '@/data/themes'
import { HelpMeDecideChat } from '@/components/HelpMeDecideChat'
import legatoLogo from '@/assets/legato.svg'
import heroBg from '@/assets/hero.png'

// Bank/advisor app URL — set VITE_BANK_URL at build time to enable the link.
const BANK_URL = import.meta.env.VITE_BANK_URL as string | undefined

const GIVING_STYLES = [
  'Start small & flexible',
  'Give every month',
  'Make a major commitment',
  'Build my own Impact Hub',
]

export function OnboardingPage() {
  const {
    selectedThemeKeys,
    toggleTheme,
    giverStyle: givingStyle,
    setGivingStyle,
    enterGraph,
  } = useAppStore()

  const hasThemes = selectedThemeKeys.length > 0
  const canProceed = hasThemes && !!givingStyle

  // "Help me decide" — opens a side chat that suggests + selects cards.
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-y-auto bg-background px-6 py-12">
      {/* Background image */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `url(${heroBg})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: 'blur(8px)',
        }}
      />

      {/* Logo top-left */}
      <div className="fixed left-6 top-6 z-20">
        <img src={legatoLogo} alt="Legato" className="h-6" />
      </div>

      {/* Bank/advisor app link top-right — set VITE_BANK_URL at build time */}
      {BANK_URL && (
        <a
          href={BANK_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="fixed right-6 top-6 z-20 flex items-center gap-1.5 ds-caption font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          LBBW Advisor view
          <ArrowUpRight className="size-3.5" />
        </a>
      )}

      {/* Card */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative z-10 w-full max-w-4xl space-y-8"
      >
        {/* Heading */}
        <div className="space-y-3 text-center">
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Heart className="size-4" />
            <span className="ds-caption">LBBW · The Future of Giving</span>
          </div>
          <h1 className="ds-title-xl">
            Discover your{' '}
            <span className="text-ai">Giver-Identity</span>
          </h1>
          <p className="ds-body text-muted-foreground mx-auto max-w-xl">
            Pick the causes that move you most — we'll map a personalised landscape
            of impact projects worth your first euro.
          </p>
        </div>

        {/* Cause grid — two rows of four */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-0.5">
            <Label className="ds-label">What moves you most?</Label>
            <div className="flex items-center gap-3">
              <span className="ds-caption text-muted-foreground">
                {hasThemes ? `${selectedThemeKeys.length} selected` : 'Choose one or more'}
              </span>
              <button
                type="button"
                onClick={() => setChatOpen(o => !o)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-3 py-1 ds-caption font-medium transition',
                  chatOpen
                    ? 'border-primary text-foreground'
                    : 'border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground',
                )}
              >
                <Sparkles className="size-3.5 text-amber-500" />
                Help me decide
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {CAUSE_THEMES.map((theme, i) => {
              const selected = selectedThemeKeys.includes(theme.key)
              const Icon = theme.icon
              return (
                <motion.button
                  key={theme.key}
                  type="button"
                  onClick={() => toggleTheme(theme.key)}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: 0.04 * i }}
                  className={cn(
                    'group relative aspect-[4/3] overflow-hidden rounded-xl border text-left transition',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                    selected
                      ? 'border-primary ring-2 ring-primary'
                      : 'border-border hover:border-foreground/30',
                  )}
                >
                  <img
                    src={theme.image}
                    alt=""
                    className={cn(
                      'absolute inset-0 size-full object-cover transition duration-300 group-hover:scale-[1.06]',
                      selected ? 'brightness-100' : 'brightness-[0.92]',
                    )}
                  />
                  {/* legibility gradient */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-black/10" />

                  {/* icon top-left */}
                  <div className="absolute left-2.5 top-2.5 flex size-7 items-center justify-center rounded-md bg-white/15 backdrop-blur-sm">
                    <Icon className="size-4 text-white" />
                  </div>

                  {/* selected check top-right */}
                  <AnimatePresence>
                    {selected && (
                      <motion.div
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0, opacity: 0 }}
                        transition={{ duration: 0.18 }}
                        className="absolute right-2.5 top-2.5 flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground shadow"
                      >
                        <Check className="size-3.5" strokeWidth={3} />
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* label */}
                  <div className="absolute inset-x-0 bottom-0 p-3">
                    <p className="ds-label leading-tight text-white">{theme.label}</p>
                    <p className="ds-caption mt-0.5 leading-tight text-white/70">{theme.blurb}</p>
                  </div>
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* Giving style — revealed after a cause is picked */}
        <AnimatePresence>
          {hasThemes && (
            <motion.div
              key="style-select"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25 }}
              className="mx-auto max-w-md space-y-2"
            >
              <Label htmlFor="style" className="ds-label">
                How do you want to give?
              </Label>
              <Select value={givingStyle ?? ''} onValueChange={setGivingStyle}>
                <SelectTrigger id="style" className="h-11 w-full">
                  <SelectValue placeholder="Choose your giving style…" />
                </SelectTrigger>
                <SelectContent>
                  {GIVING_STYLES.map(s => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </motion.div>
          )}
        </AnimatePresence>

        {/* CTA */}
        <AnimatePresence>
          {canProceed && (
            <motion.div
              key="cta"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="mx-auto max-w-md"
            >
              <Button
                size="lg"
                className="h-12 w-full rounded-xl text-base font-medium"
                onClick={enterGraph}
              >
                Explore impact
                <ArrowRight className="size-4" />
              </Button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Footer hint */}
        <p className="ds-caption text-center text-muted-foreground/60">
          Your selection shapes the graph — only the causes you pick and their projects appear.
        </p>
      </motion.div>

      {/* "Help me decide" side chat */}
      <HelpMeDecideChat open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  )
}
