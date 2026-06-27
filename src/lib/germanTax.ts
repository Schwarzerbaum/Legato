// German charitable-donation tax engine (Legato).
//
// Donations to recognised gemeinnützige organisations are deductible as
// "Sonderausgaben" under § 10b EStG: up to 20 % of the donor's total annual
// income, with any excess carried forward to future years (Spendenvortrag).
// The real benefit equals the drop in income tax (plus church tax / Soli)
// caused by lowering taxable income — so we compute it from the progressive
// 2025 income-tax schedule (§ 32a EStG) directly, which correctly captures the
// progression and any bracket change, rather than a flat marginal rate.
//
// Figures are realistic but illustrative — not tax advice.

/** Maximum share of annual income deductible as donations in one year (§ 10b). */
export const DONATION_CAP_RATE = 0.2

/** Church-tax rates by region. Baden-Württemberg & Bayern: 8 %, rest: 9 %. */
export const CHURCH_TAX_RATE_BW = 0.08
export const CHURCH_TAX_RATE_OTHER = 0.09

/**
 * German income tax for a single filer (Grundtarif), 2025 schedule (§ 32a EStG).
 * `zvE` = zu versteuerndes Einkommen (taxable income), in euros.
 */
export function incomeTaxSingle2025(zvE: number): number {
  const x = Math.floor(Math.max(0, zvE))
  if (x <= 12_096) return 0
  if (x <= 17_443) {
    const y = (x - 12_096) / 10_000
    return (932.3 * y + 1_400) * y
  }
  if (x <= 68_480) {
    const z = (x - 17_443) / 10_000
    return (176.64 * z + 2_397) * z + 1_015.13
  }
  if (x <= 277_825) return 0.42 * x - 10_911.92
  return 0.45 * x - 19_246.67
}

/**
 * Income tax for the household. Married couples are assessed under the
 * Splittingtarif: tax on half the joint income, doubled.
 */
export function incomeTax2025(zvE: number, married: boolean): number {
  const tax = married
    ? 2 * incomeTaxSingle2025(zvE / 2)
    : incomeTaxSingle2025(zvE)
  return Math.max(0, tax)
}

/**
 * Solidaritätszuschlag (5.5 % of income tax) with the 2025 Freigrenze and
 * Milderungszone. Most taxpayers no longer pay it — only higher incomes do.
 */
export function soli2025(incomeTax: number, married: boolean): number {
  const freigrenze = married ? 39_900 : 19_950
  if (incomeTax <= freigrenze) return 0
  return Math.min(0.055 * incomeTax, 0.119 * (incomeTax - freigrenze))
}

/** The marginal income-tax rate (Grenzsteuersatz) at a given taxable income. */
export function marginalRate2025(zvE: number, married: boolean): number {
  const delta = 100
  return (incomeTax2025(zvE + delta, married) - incomeTax2025(zvE, married)) / delta
}

export interface DonationSaving {
  /** Gross donation requested this year. */
  donation: number
  /** Portion deductible this year after the 20 %-of-income cap. */
  deductibleNow: number
  /** Excess carried forward to later years (Spendenvortrag). */
  carryForward: number
  /** Income tax saved by the deduction. */
  incomeTaxSaved: number
  /** Solidarity surcharge saved. */
  soliSaved: number
  /** Church tax saved (0 if not a church-tax payer). */
  churchSaved: number
  /** Total money returned via the tax system. */
  totalSaved: number
  /** What the donor actually pays out of pocket after the refund. */
  netCost: number
  /** Refund as a share of the donation (the "the state co-funds X %" figure). */
  effectiveRate: number
}

export interface TaxInputs {
  /** Annual taxable income (zu versteuerndes Einkommen). */
  income: number
  /** Gross annual donation. */
  donation: number
  married: boolean
  /** Church-tax rate (0 if the donor pays none). */
  churchRate: number
}

/**
 * Compute the one-year tax benefit of a donation. The saving is the difference
 * between the tax owed without and with the deduction, so the progressive
 * schedule (and any bracket change) is captured exactly.
 */
export function donationSaving({ income, donation, married, churchRate }: TaxInputs): DonationSaving {
  const cap = income * DONATION_CAP_RATE
  const deductibleNow = Math.min(Math.max(0, donation), cap)
  const carryForward = Math.max(0, donation - deductibleNow)

  const taxBefore = incomeTax2025(income, married)
  const taxAfter = incomeTax2025(income - deductibleNow, married)
  const incomeTaxSaved = Math.max(0, taxBefore - taxAfter)

  const soliSaved = soli2025(taxBefore, married) - soli2025(taxAfter, married)
  const churchSaved = churchRate * incomeTaxSaved

  const totalSaved = incomeTaxSaved + Math.max(0, soliSaved) + churchSaved
  const netCost = Math.max(0, donation - totalSaved)
  const effectiveRate = donation > 0 ? totalSaved / donation : 0

  return {
    donation,
    deductibleNow,
    carryForward,
    incomeTaxSaved,
    soliSaved: Math.max(0, soliSaved),
    churchSaved,
    totalSaved,
    netCost,
    effectiveRate,
  }
}

export interface ProjectionPoint {
  year: number
  cumulativeDonated: number
  cumulativeSaved: number
  cumulativeNetCost: number
}

/**
 * Multi-year projection of recurring annual giving. The yearly gift grows by
 * `growthRate` (e.g. 0.02 = +2 %/yr), so over a long horizon the cumulative
 * curves bend upward instead of running perfectly straight — at 2 % the year-50
 * gift is ~2.7× the first year's. Carry-forward from the 20 % cap is rolled into
 * the next year, so the donor still realises the benefit of everything they gave.
 */
export function givingProjection(
  inputs: TaxInputs,
  years: number,
  growthRate = 0,
): ProjectionPoint[] {
  const points: ProjectionPoint[] = []
  let cumulativeDonated = 0
  let cumulativeSaved = 0
  let pending = 0 // carried-forward, not-yet-deducted donations

  const cap = inputs.income * DONATION_CAP_RATE

  for (let year = 1; year <= years; year++) {
    const thisYearGift = inputs.donation * Math.pow(1 + growthRate, year - 1)
    cumulativeDonated += thisYearGift
    pending += thisYearGift

    const deductibleNow = Math.min(pending, cap)
    pending -= deductibleNow

    const { totalSaved } = donationSaving({ ...inputs, donation: deductibleNow })
    // donationSaving re-applies the cap, but deductibleNow is already within it.
    cumulativeSaved += totalSaved

    points.push({
      year,
      cumulativeDonated,
      cumulativeSaved,
      cumulativeNetCost: cumulativeDonated - cumulativeSaved,
    })
  }
  return points
}
