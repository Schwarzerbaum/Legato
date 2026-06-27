import { useState } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import advisorsData from "../../mock-data/advisors.json"
import companiesData from "../../mock-data/companies.json"
import fieldsData from "../../mock-data/fields.json"
import { getMonthAvailability } from "@/lib/availability"
import { AdvisorProfileCard } from "@/components/booking/AdvisorProfileCard"
import { CalendarView } from "@/components/booking/CalendarView"
import { TimeSlotPicker } from "@/components/booking/TimeSlotPicker"
import { BookingConfirmDialog } from "@/components/booking/BookingConfirmDialog"
import type { Advisor, Company, Field, TimeSlot } from "@/types/booking"

const advisors = advisorsData as Advisor[]
const companies = companiesData as Company[]
const fields = fieldsData as Field[]

export function AdvisorBookingPage() {
  const { advisorId } = useParams<{ advisorId: string }>()
  const navigate = useNavigate()

  const today = new Date()
  const [currentMonth, setCurrentMonth] = useState({
    year: today.getFullYear(),
    month: today.getMonth(),
  })
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  const advisor = advisors.find((e) => e.id === advisorId)

  if (!advisor) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
        <p className="ds-title-sm text-muted-foreground">Advisor not found</p>
        <Link
          to="/"
          className="flex items-center gap-2 rounded-full border px-4 py-2 ds-small hover:bg-secondary transition-colors"
        >
          <ArrowLeft className="size-4" />
          Back to dashboard
        </Link>
      </div>
    )
  }

  const company = companies.find((c) => c.id === advisor.companyId) as Company
  const advisorFields = fields.filter((f) => advisor.fieldIds.includes(f.id))

  const availability = getMonthAvailability(
    advisor.id,
    currentMonth.year,
    currentMonth.month
  )

  function handleSelectDate(date: string) {
    setSelectedDate(date)
    setSelectedSlot(null)
  }

  function handlePrevMonth() {
    const d = new Date(currentMonth.year, currentMonth.month - 1, 1)
    setCurrentMonth({ year: d.getFullYear(), month: d.getMonth() })
    setSelectedDate(null)
    setSelectedSlot(null)
  }

  function handleNextMonth() {
    const d = new Date(currentMonth.year, currentMonth.month + 1, 1)
    setCurrentMonth({ year: d.getFullYear(), month: d.getMonth() })
    setSelectedDate(null)
    setSelectedSlot(null)
  }

  function handleConfirmBooking() {
    setDialogOpen(false)
    navigate("/booking-success", {
      state: { advisor, company, date: selectedDate, slot: selectedSlot },
    })
  }

  const selectedDaySlots = selectedDate ? availability[selectedDate]?.slots ?? [] : []

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-6 py-10">
        {/* Back link */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 ds-small text-muted-foreground hover:text-foreground transition-colors mb-8"
        >
          <ArrowLeft className="size-4" />
          Back
        </Link>

        {/* Two-panel layout */}
        <div className="grid gap-10 lg:grid-cols-[340px_1fr]">
          {/* Left: profile */}
          <AdvisorProfileCard
            advisor={advisor}
            company={company}
            fields={advisorFields}
          />

          {/* Right: calendar + slots */}
          <div className="flex flex-col gap-8">
            <CalendarView
              year={currentMonth.year}
              month={currentMonth.month}
              availability={availability}
              selectedDate={selectedDate}
              onSelectDate={handleSelectDate}
              onPrevMonth={handlePrevMonth}
              onNextMonth={handleNextMonth}
            />

            {selectedDate && selectedDaySlots.length > 0 && (
              <TimeSlotPicker
                slots={selectedDaySlots}
                selectedSlot={selectedSlot}
                onSelectSlot={setSelectedSlot}
                onConfirm={() => setDialogOpen(true)}
              />
            )}
          </div>
        </div>
      </div>

      {selectedDate && selectedSlot && (
        <BookingConfirmDialog
          open={dialogOpen}
          advisor={advisor}
          company={company}
          date={selectedDate}
          slot={selectedSlot}
          onConfirm={handleConfirmBooking}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  )
}
