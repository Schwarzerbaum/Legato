import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight, Heart, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { useAppStore } from '@/store/useAppStore'
import { fields } from '@/data/index'
import { suggestCauseAreas } from '@/lib/suggestFields'
import legatoLogo from '@/assets/legato.svg'
import heroBg from '@/assets/hero.png'

// Giver-Identity inputs. We reuse the store's two onboarding string slots
// (giverMotivation = motivation, giverStyle = giving style).
const MOTIVATIONS = [
  'The planet & climate',
  'Children & education',
  'Health & medical breakthroughs',
  'Poverty & social inclusion',
  'Animals & nature',
  'Humanitarian crises & relief',
  'Arts, culture & community',
  'Equality & human rights',
]

const GIVING_STYLES = [
  'Start small & flexible',
  'Give every month',
  'Make a major commitment',
  'Build my own foundation',
]

export function OnboardingPage() {
  const {
    giverMotivation: motivation,
    giverStyle: givingStyle,
    setMotivation,
    setGivingStyle,
    enterGraph,
    suggestionsLoading,
    setSuggestedFieldIds,
    setSuggestionsLoading,
  } = useAppStore()

  const canProceed = !!motivation && !!givingStyle

  async function handleStyleChange(style: string) {
    setGivingStyle(style)
    if (!motivation) return

    setSuggestionsLoading(true)
    try {
      const ids = await suggestCauseAreas(
        motivation,
        style,
        fields.map(f => f.name),
        fields.map(f => f.id),
      )
      setSuggestedFieldIds(ids)
    } catch {
      setSuggestedFieldIds([])
    } finally {
      setSuggestionsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-6">
      {/* Background image */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `url(${heroBg})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: 'blur(8px)',
        }}
      />

      {/* Logo top-left */}
      <div className="absolute left-6 top-6">
        <img src={legatoLogo} alt="Legato" className="h-6" />
      </div>

      {/* Card */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative z-10 w-full max-w-md space-y-8"
      >
        {/* Heading */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Heart className="size-4" />
            <span className="ds-caption">LBBW · The Future of Giving</span>
          </div>
          <h1 className="ds-title-xl">
            Discover your{' '}
            <span className="text-ai">Giver-Identity</span>
          </h1>
          <p className="ds-body text-muted-foreground">
            Tell us what matters to you and how you like to give — we'll map a
            personalised landscape of impact projects worth your first euro.
          </p>
        </div>

        {/* Form */}
        <div className="space-y-5">
          {/* Motivation */}
          <div className="space-y-2">
            <Label htmlFor="motivation" className="ds-label">
              What moves you most?
            </Label>
            <Select
              value={motivation ?? ''}
              onValueChange={setMotivation}
            >
              <SelectTrigger id="motivation" className="h-11 w-full">
                <SelectValue placeholder="Choose what matters to you…" />
              </SelectTrigger>
              <SelectContent>
                {MOTIVATIONS.map(m => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Giving style — revealed after motivation selection */}
          <AnimatePresence>
            {motivation && (
              <motion.div
                key="style-select"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.25 }}
                className="space-y-2"
              >
                <Label htmlFor="style" className="ds-label flex items-center gap-2">
                  How do you want to give?
                  {suggestionsLoading && (
                    <Sparkles className="size-3.5 animate-pulse text-amber-500" />
                  )}
                </Label>
                <Select
                  value={givingStyle ?? ''}
                  onValueChange={handleStyleChange}
                >
                  <SelectTrigger id="style" className="h-11 w-full">
                    <SelectValue placeholder="Choose your giving style…" />
                  </SelectTrigger>
                  <SelectContent>
                    {GIVING_STYLES.map(s => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* CTA */}
        <AnimatePresence>
          {canProceed && (
            <motion.div
              key="cta"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              <Button
                size="lg"
                className="w-full h-12 rounded-xl text-base font-medium"
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
          Navigate the graph to discover foundations, corporate partners, and impact projects.
        </p>
      </motion.div>
    </div>
  )
}
