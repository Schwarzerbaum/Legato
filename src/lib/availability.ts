import type { DayAvailability, TimeSlot } from "@/types/booking"

/** djb2 hash → stable 0–1 float */
function seededRandom(seed: string): number {
  let h = 5381
  for (let i = 0; i < seed.length; i++) {
    h = ((h << 5) + h) ^ seed.charCodeAt(i)
    h = h >>> 0 // keep as unsigned 32-bit
  }
  return (h % 10000) / 10000
}

const SLOT_TIMES = [
  "09:00", "09:30", "10:00", "10:30",
  "11:00", "11:30", "12:00", "12:30",
  "13:00", "13:30", "14:00", "14:30",
  "15:00", "15:30", "16:00", "16:30",
]

export function getAvailability(advisorId: string, isoDate: string): DayAvailability {
  const date = new Date(isoDate)
  const dayOfWeek = date.getUTCDay() // 0=Sun, 6=Sat

  // Weekends always unavailable
  if (dayOfWeek === 0 || dayOfWeek === 6) {
    return { date: isoDate, available: false, slots: [] }
  }

  // ~20% of weekdays are "day off"
  const dayRng = seededRandom(`${advisorId}-${isoDate}-dayoff`)
  if (dayRng < 0.2) {
    return { date: isoDate, available: false, slots: [] }
  }

  const slots: TimeSlot[] = SLOT_TIMES.map((label, index) => {
    const slotRng = seededRandom(`${advisorId}-${isoDate}-slot-${index}`)
    return {
      label,
      index,
      booked: slotRng < 0.25,
    }
  })

  return { date: isoDate, available: true, slots }
}

export function getMonthAvailability(
  advisorId: string,
  year: number,
  month: number // 0-based
): Record<string, DayAvailability> {
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const result: Record<string, DayAvailability> = {}

  for (let day = 1; day <= daysInMonth; day++) {
    const isoDate = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
    result[isoDate] = getAvailability(advisorId, isoDate)
  }

  return result
}
