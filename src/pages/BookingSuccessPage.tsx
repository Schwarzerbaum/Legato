import { useLocation, Link } from "react-router-dom"
import { CalendarDays, CheckCircle, Clock, Video } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import type { Advisor, Company, TimeSlot } from "@/types/booking"

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
]
const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number)
  const date = new Date(year, month - 1, day)
  return `${DAY_NAMES[date.getDay()]}, ${MONTH_NAMES[month - 1]} ${day}, ${year}`
}

interface SuccessState {
  advisor: Advisor
  company: Company
  date: string
  slot: TimeSlot
}

export function BookingSuccessPage() {
  const location = useLocation()
  const state = location.state as SuccessState | null

  if (!state) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
        <p className="ds-title-sm text-muted-foreground">No booking found.</p>
        <Link
          to="/"
          className="rounded-full border px-4 py-2 ds-small hover:bg-secondary transition-colors"
        >
          Back to dashboard
        </Link>
      </div>
    )
  }

  const { advisor, company, date, slot } = state
  const initials = advisor.firstName[0] + advisor.lastName[0]

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6 py-16">
      <div className="flex flex-col items-center gap-8 w-full max-w-md">
        {/* Success icon */}
        <div className="flex flex-col items-center gap-3 text-center">
          <CheckCircle className="size-12 text-primary" strokeWidth={1.5} />
          <h1 className="ds-title-md">You're booked!</h1>
          <p className="ds-small text-muted-foreground">
            A calendar invite and video call link will be sent to your email.
          </p>
        </div>

        {/* Booking summary card */}
        <div className="w-full rounded-xl border bg-card p-6 flex flex-col gap-5 shadow-none">
          {/* Advisor */}
          <div className="flex items-center gap-3">
            <Avatar size="lg" className="size-12">
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
            <div>
              <p className="ds-label">{advisor.firstName} {advisor.lastName}</p>
              <p className="ds-caption text-muted-foreground">{advisor.title}</p>
              <p className="ds-caption text-muted-foreground">{company.name}</p>
            </div>
          </div>

          <div className="border-t" />

          {/* Details */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 ds-small text-muted-foreground">
              <CalendarDays className="size-4 shrink-0" />
              <span>{formatDate(date)}</span>
            </div>
            <div className="flex items-center gap-2 ds-small text-muted-foreground">
              <Clock className="size-4 shrink-0" />
              <span>{slot.label} · 30 minutes</span>
            </div>
            <div className="flex items-center gap-2 ds-small text-muted-foreground">
              <Video className="size-4 shrink-0" />
              <span>Video call — link sent by email</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 w-full">
          <Link
            to="/"
            className="flex-1 text-center rounded-full bg-primary text-primary-foreground py-2.5 ds-label hover:opacity-90 transition-opacity"
          >
            Back to dashboard
          </Link>
          <Link
            to={`/schedule/${advisor.id}`}
            className="flex-1 text-center rounded-full border py-2.5 ds-label hover:bg-secondary transition-colors"
          >
            Book another time
          </Link>
        </div>
      </div>
    </div>
  )
}
