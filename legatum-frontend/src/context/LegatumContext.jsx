import { createContext, useContext, useState, useEffect } from 'react'

const Ctx = createContext(null)

function load(key, fallback) {
  try {
    const v = localStorage.getItem(key)
    return v ? JSON.parse(v) : fallback
  } catch { return fallback }
}

function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch {}
}

export function LegatumProvider({ children }) {
  const [persona, _setPersona]           = useState(() => load('lg_persona', null))
  const [selectedNGOs, _setNGOs]         = useState(() => load('lg_ngos', []))
  const [monthly, _setMonthly]           = useState(() => load('lg_monthly', 200))
  const [badgesEarned, _setBadges]       = useState(() => new Set(load('lg_badges', [])))
  const [passportMinted, _setMinted]     = useState(() => load('lg_minted', false))
  const [advisorNotified, _setAdvised]   = useState(() => load('lg_advised', false))

  const setPersona = (v) => { save('lg_persona', v); _setPersona(v) }
  const setSelectedNGOs = (v) => { save('lg_ngos', v); _setNGOs(v) }
  const setMonthly = (v) => { save('lg_monthly', v); _setMonthly(v) }
  const setPassportMinted = (v) => { save('lg_minted', v); _setMinted(v) }
  const setAdvisorNotified = (v) => { save('lg_advised', v); _setAdvised(v) }

  const earnBadge = (badge) => {
    _setBadges(prev => {
      const next = new Set([...prev, badge])
      save('lg_badges', [...next])
      return next
    })
  }

  const resetAll = () => {
    ['lg_persona','lg_ngos','lg_monthly','lg_badges','lg_minted','lg_advised']
      .forEach(k => localStorage.removeItem(k))
    _setPersona(null); _setNGOs([]); _setMonthly(200)
    _setBadges(new Set()); _setMinted(false); _setAdvised(false)
  }

  return (
    <Ctx.Provider value={{
      persona, setPersona,
      selectedNGOs, setSelectedNGOs,
      monthly, setMonthly,
      badgesEarned, earnBadge,
      passportMinted, setPassportMinted,
      advisorNotified, setAdvisorNotified,
      resetAll,
    }}>
      {children}
    </Ctx.Provider>
  )
}

export const useLegatum = () => useContext(Ctx)
