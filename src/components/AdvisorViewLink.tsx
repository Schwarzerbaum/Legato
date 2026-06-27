import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'

// Persistent in-app switch to the bank/advisor side (rendered on the giver app).
export function AdvisorViewLink() {
  return (
    <Link
      to="/bank/discover"
      className="fixed right-5 top-5 z-30 flex items-center gap-1.5 rounded-full border border-border bg-background/85 px-3.5 py-1.5 ds-caption font-medium text-muted-foreground shadow-sm backdrop-blur-sm transition hover:border-foreground/30 hover:text-foreground"
      title="Open the LBBW advisor view"
    >
      LBBW Advisor view
      <ArrowUpRight className="size-3.5" />
    </Link>
  )
}
