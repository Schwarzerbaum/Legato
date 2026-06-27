import { ArrowUpRight } from 'lucide-react'

// Persistent "switch to the bank/advisor app" button. In production it needs
// VITE_BANK_URL (else it hides, never pointing nowhere); in local dev it defaults
// to the bank app's port (npm run dev runs it on :3000) so it's testable as-is.
const BANK_URL =
  (import.meta.env.VITE_BANK_URL as string | undefined) ??
  (import.meta.env.DEV ? 'http://localhost:3000' : undefined)

export function AdvisorViewLink() {
  if (!BANK_URL) return null
  return (
    <a
      href={BANK_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="fixed right-5 top-5 z-30 flex items-center gap-1.5 rounded-full border border-border bg-background/85 px-3.5 py-1.5 ds-caption font-medium text-muted-foreground shadow-sm backdrop-blur-sm transition hover:border-foreground/30 hover:text-foreground"
      title="Open the LBBW advisor view"
    >
      LBBW Advisor view
      <ArrowUpRight className="size-3.5" />
    </a>
  )
}
