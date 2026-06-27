import { ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import type { DayAvailability } from "@/types/booking"

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
]

interface CalendarViewProps {
  year: number
  month: number // 0-based
  availability: Record<string, DayAvailability>
  selectedDate: string | null
  onSelectDate: (date: string) => void
  onPrevMonth: () => void
  onNextMonth: () => void
}

export function CalendarView({
  year,
  month,
  availability,
  selectedDate,
  onSelectDate,
  onPrevMonth,
  onNextMonth,
}: CalendarViewProps) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const firstDayOfMonth = new Date(year, month, 1).getDay() // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const isCurrentMonth =
    year === today.getFullYear() && month === today.getMonth()

  // Build grid cells: leading nulls + day numbers
  const cells: (number | null)[] = [
    ...Array(firstDayOfMonth).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onPrevMonth}
          disabled={isCurrentMonth}
          className={cn(
            "flex size-8 items-center justify-center rounded-full transition-colors",
            isCurrentMonth
              ? "text-muted-foreground/30 cursor-default"
              : "hover:bg-secondary cursor-pointer"
          )}
        >
          <ChevronLeft className="size-4" />
        </button>
        <span className="ds-label">
          {MONTH_NAMES[month]} {year}
        </span>
        <button
          onClick={onNextMonth}
          className="flex size-8 items-center justify-center rounded-full hover:bg-secondary cursor-pointer transition-colors"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 text-center">
        {DAY_NAMES.map((d) => (
          <div key={d} className="ds-caption text-muted-foreground py-1">
            {d}
          </div>
        ))}
      </div>

      {/* Day grid */}
      <div className="grid grid-cols-7 gap-y-1 text-center">
        {cells.map((day, i) => {
          if (day === null) {
            return <div key={`empty-${i}`} />
          }

          const isoDate = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
          const cellDate = new Date(year, month, day)
          const isPast = cellDate < today
          const dayData = availability[isoDate]
          const isAvailable = !isPast && dayData?.available === true
          const isSelected = selectedDate === isoDate

          return (
            <div key={isoDate} className="flex items-center justify-center py-0.5">
              <button
                onClick={() => isAvailable && onSelectDate(isoDate)}
                disabled={!isAvailable}
                className={cn(
                  "flex size-9 items-center justify-center rounded-full ds-small transition-colors",
                  isSelected
                    ? "bg-primary text-primary-foreground"
                    : isAvailable
                    ? "hover:bg-secondary cursor-pointer"
                    : "text-muted-foreground/40 cursor-default"
                )}
              >
                {day}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
