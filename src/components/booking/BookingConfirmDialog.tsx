import { CalendarDays, Clock, Video } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
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

interface BookingConfirmDialogProps {
  open: boolean
  advisor: Advisor
  company: Company
  date: string
  slot: TimeSlot
  onConfirm: () => void
  onOpenChange: (open: boolean) => void
}

export function BookingConfirmDialog({
  open,
  advisor,
  company,
  date,
  slot,
  onConfirm,
  onOpenChange,
}: BookingConfirmDialogProps) {
  const initials = advisor.firstName[0] + advisor.lastName[0]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Confirm your booking</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          {/* Advisor summary */}
          <div className="flex items-center gap-3 rounded-lg bg-secondary p-3">
            <Avatar size="lg" className="size-12">
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
            <div>
              <p className="ds-label">{advisor.firstName} {advisor.lastName}</p>
              <p className="ds-caption text-muted-foreground">{advisor.title}</p>
              <p className="ds-caption text-muted-foreground">{company.name}</p>
            </div>
          </div>

          {/* Booking details */}
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

        <DialogFooter>
          <button
            onClick={onConfirm}
            className="rounded-full bg-primary text-primary-foreground px-6 py-2.5 ds-label hover:opacity-90 transition-opacity"
          >
            Confirm booking
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
