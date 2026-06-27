import { cn } from "@/lib/utils"
import type { TimeSlot } from "@/types/booking"

interface TimeSlotPickerProps {
  slots: TimeSlot[]
  selectedSlot: TimeSlot | null
  onSelectSlot: (slot: TimeSlot) => void
  onConfirm: () => void
}

export function TimeSlotPicker({
  slots,
  selectedSlot,
  onSelectSlot,
  onConfirm,
}: TimeSlotPickerProps) {
  return (
    <div className="flex flex-col gap-4">
      <p className="ds-label">Select a time</p>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {slots.map((slot) => {
          const isSelected = selectedSlot?.index === slot.index

          return (
            <button
              key={slot.index}
              disabled={slot.booked}
              onClick={() => !slot.booked && onSelectSlot(slot)}
              className={cn(
                "rounded-full px-3 py-2 ds-small border transition-colors",
                slot.booked
                  ? "line-through text-muted-foreground/40 cursor-default border-transparent"
                  : isSelected
                  ? "bg-primary text-primary-foreground border-primary cursor-pointer"
                  : "hover:bg-secondary cursor-pointer border-border"
              )}
            >
              {slot.label}
            </button>
          )
        })}
      </div>

      {selectedSlot && (
        <button
          onClick={onConfirm}
          className="rounded-full w-full bg-primary text-primary-foreground py-2.5 ds-label transition-opacity hover:opacity-90"
        >
          Confirm — {selectedSlot.label}
        </button>
      )}
    </div>
  )
}
