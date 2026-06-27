'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const INK    = '#0f172a'
const PARCH  = '#ffffff'
const NGO_C  = '#7c3aed'
const CORP_C = '#2563eb'
const GREEN  = '#059669'

const CLIENTS = [
  {
    id: 'c1',
    name: 'Dr. Miriam Hoffmann',
    tier: 'Private Banking',
    aum: 4_800_000,
    givingBudget: 120_000,
    deployed: 87_000,
    sdgs: [4, 13, 15],
    pillars: ['Climate', 'Education'],
    status: 'active',
    lastContact: '2026-06-18',
    allocations: [
      { org: 'BUND e.V.',         type: 'ngo',  amount: 40_000, sdg: 15, progress: 82 },
      { org: 'BW Stiftung',       type: 'ngo',  amount: 30_000, sdg: 4,  progress: 56 },
      { org: 'Robert Bosch GmbH', type: 'corp', amount: 17_000, sdg: 4,  progress: 34 },
    ],
    notes: 'Wants quarterly impact reports. Prefers BW-region NGOs. SDG 13 anchor.',
  },
  {
    id: 'c2',
    name: 'Familie Breitner-Koch',
    tier: 'Wealth Management',
    aum: 12_200_000,
    givingBudget: 350_000,
    deployed: 210_000,
    sdgs: [2, 10, 16],
    pillars: ['Poverty', 'Human Rights', 'Food Security'],
    status: 'review',
    lastContact: '2026-05-30',
    allocations: [
      { org: 'Welthungerhilfe', type: 'ngo',  amount: 120_000, sdg: 2,  progress: 90 },
      { org: 'PHINEO gAG',      type: 'ngo',  amount: 55_000,  sdg: 17, progress: 68 },
      { org: 'Porsche AG',      type: 'corp', amount: 35_000,  sdg: 8,  progress: 44 },
    ],
    notes: 'Stiftung interest raised in last call — flag for /found. Annual SDG 2 priority.',
  },
  {
    id: 'c3',
    name: 'Stefan Walczak',
    tier: 'Private Banking',
    aum: 2_100_000,
    givingBudget: 50_000,
    deployed: 12_000,
    sdgs: [10, 11],
    pillars: ['Digital Inclusion', 'Cities'],
    status: 'onboarding',
    lastContact: '2026-06-22',
    allocations: [
      { org: 'Aktion Mensch', type: 'ngo',  amount: 12_000, sdg: 10, progress: 24 },
    ],
    notes: 'New client — impact strategy not finalised. Schedule Discover session.',
  },
  {
    id: 'c4',
    name: 'Ingrid von Saalfeld',
    tier: 'Ultra High Net Worth',
    aum: 38_500_000,
    givingBudget: 900_000,
    deployed: 900_000,
    sdgs: [3, 4, 5, 13, 15],
    pillars: ['Health', 'Education', 'Climate', 'Gender'],
    status: 'foundation',
    lastContact: '2026-06-10',
    allocations: [
      { org: 'SOS-Kinderdorf',    type: 'ngo',  amount: 300_000, sdg: 3,  progress: 100 },
      { org: 'Welthungerhilfe',   type: 'ngo',  amount: 200_000, sdg: 2,  progress: 100 },
      { org: 'BUND e.V.',         type: 'ngo',  amount: 250_000, sdg: 15, progress: 100 },
      { org: 'Mercedes-Benz AG',  type: 'corp', amount: 150_000, sdg: 13, progress: 100 },
    ],
    notes: 'Delegated foundation granted 2026-04. Quarterly stewardship call only.',
  },
]

const STATUS_META: Record<string, { label: string; color: string }> = {
  active:      { label: 'Active',       color: GREEN },
  review:      { label: 'Needs Review', color: '#C48A00' },
  onboarding:  { label: 'Onboarding',   color: '#1A3A5C' },
  foundation:  { label: 'Foundation',   color: '#6B1A8B' },
}

function fmt(n: number) {
  return '€' + (n >= 1_000_000
    ? (n / 1_000_000).toFixed(1) + 'M'
    : (n / 1_000).toFixed(0) + 'k')
}

function MiniBar({ value, color = INK }: { value: number; color?: string }) {
  return (
    <div style={{ height: 3, background: `${INK}0D`, borderRadius: 2, overflow: 'hidden' }}>
      <motion.div initial={{ width: 0 }} animate={{ width: `${value}%` }}
        transition={{ duration: 0.7 }}
        style={{ height: '100%', background: color, opacity: 0.65, borderRadius: 2 }} />
    </div>
  )
}

export default function ManagePage() {
  const [selected, setSelected] = useState<string | null>(null)
  const client = CLIENTS.find(c => c.id === selected)
  const deployedTotal = CLIENTS.reduce((a, c) => a + c.deployed, 0)
  const budgetTotal   = CLIENTS.reduce((a, c) => a + c.givingBudget, 0)

  return (
    <div style={{ paddingTop: 40 }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 8, letterSpacing:'-0.01em',
          textTransform:'none', color: INK, opacity: 0.3, marginBottom: 8 }}>
          Advisor Dashboard · LBBW Philanthropic Services
        </div>
        <h1 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 30, fontWeight: 500,
          color: INK, margin: 0, marginBottom: 4 }}>
          Client Portfolio
        </h1>
        <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 15, color: INK,
          opacity: 0.45, fontStyle:'italic', margin: 0 }}>
          {CLIENTS.length} active advisories · {fmt(deployedTotal)} deployed of {fmt(budgetTotal)} mandated
        </p>
      </div>

      {/* Summary strip */}
      <div style={{ display:'flex', gap: 1, marginBottom: 32 }}>
        {[
          { label: 'Active', val: CLIENTS.filter(c=>c.status==='active').length, color: GREEN },
          { label: 'Review', val: CLIENTS.filter(c=>c.status==='review').length, color: '#C48A00' },
          { label: 'Onboarding', val: CLIENTS.filter(c=>c.status==='onboarding').length, color: NGO_C },
          { label: 'Foundation', val: CLIENTS.filter(c=>c.status==='foundation').length, color: '#6B1A8B' },
        ].map(s => (
          <div key={s.label} style={{ flex:1, padding:'12px 16px',
            background:'#fff', border:`1px solid ${INK}10` }}>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 18, color: s.color,
              fontWeight: 500 }}>{s.val}</div>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 11,
              color: INK, opacity: 0.4, marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={{ display:'flex', gap: 20 }}>
        {/* Client list */}
        <div style={{ flex: 1, display:'flex', flexDirection:'column', gap: 1 }}>
          {CLIENTS.map(c => {
            const sm = STATUS_META[c.status]
            const pct = Math.round(c.deployed / c.givingBudget * 100)
            const isSel = selected === c.id
            return (
              <motion.div key={c.id}
                onClick={() => setSelected(isSel ? null : c.id)}
                whileHover={{ x: 2 }}
                style={{
                  background: isSel ? `${INK}06` : '#fff',
                  border: `1px solid ${isSel ? INK + '22' : INK + '0D'}`,
                  padding: '16px 18px',
                  cursor: 'pointer',
                  borderLeft: `2px solid ${sm.color}`,
                }}>
                <div style={{ display:'flex', justifyContent:'space-between',
                  alignItems:'flex-start', marginBottom: 8 }}>
                  <div>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 16,
                      color: INK, marginBottom: 2 }}>{c.name}</div>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 7,
                      letterSpacing:'0em', textTransform:'none',
                      color: INK, opacity: 0.3 }}>{c.tier}</div>
                  </div>
                  <div style={{ textAlign:'right' }}>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 7.5,
                      letterSpacing:'0em', color: sm.color,
                      textTransform:'uppercase' }}>{sm.label}</div>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 12,
                      color: INK, opacity: 0.38, marginTop: 2 }}>
                      AUM {fmt(c.aum)}
                    </div>
                  </div>
                </div>

                <div style={{ marginBottom: 6 }}>
                  <MiniBar value={pct} color={pct === 100 ? GREEN : INK} />
                </div>

                <div style={{ display:'flex', justifyContent:'space-between',
                  fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 11,
                  color: INK, opacity: 0.4 }}>
                  <span>{fmt(c.deployed)} deployed</span>
                  <span style={{ color: pct < 50 ? CORP_C : GREEN, opacity: 1 }}>{pct}% of {fmt(c.givingBudget)}</span>
                </div>

                <div style={{ display:'flex', gap: 5, marginTop: 10, flexWrap:'wrap' }}>
                  {c.pillars.map(p => (
                    <span key={p} style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 6.5,
                      letterSpacing:'0em', textTransform:'none',
                      border:`1px solid ${INK}22`, padding:'2px 7px',
                      color: INK, opacity: 0.45 }}>{p}</span>
                  ))}
                  {c.status === 'review' && (
                    <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 6.5,
                      letterSpacing:'0em', textTransform:'none',
                      border:`1px solid #C48A0066`, padding:'2px 7px',
                      color:'#C48A00' }}>⚠ Action needed</span>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Detail panel */}
        <AnimatePresence>
          {client && (
            <motion.div key={client.id}
              initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ type:'spring', damping: 28, stiffness: 260 }}
              style={{ width: 310, flexShrink: 0 }}>
              <div style={{ background:'#fff', border:`1px solid ${INK}12`,
                padding:'20px 18px', position:'sticky', top: 20 }}>
                <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 7.5,
                  letterSpacing:'0em', textTransform:'none',
                  color: STATUS_META[client.status].color, marginBottom: 12 }}>
                  {STATUS_META[client.status].label}
                </div>
                <h2 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 20,
                  fontWeight: 500, color: INK, margin:'0 0 3px' }}>{client.name}</h2>
                <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 12,
                  color: INK, opacity: 0.4, marginBottom: 16,
                  fontStyle:'italic' }}>{client.tier}</div>

                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr',
                  gap: 10, marginBottom: 18 }}>
                  {[
                    { l:'AUM',     v: fmt(client.aum) },
                    { l:'Budget',  v: fmt(client.givingBudget) },
                    { l:'Deployed',v: fmt(client.deployed) },
                    { l:'Last contact', v: client.lastContact },
                  ].map(row => (
                    <div key={row.l}>
                      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 6.5,
                        letterSpacing:'0em', textTransform:'none',
                        color: INK, opacity: 0.28, marginBottom: 3 }}>{row.l}</div>
                      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 14,
                        color: INK, opacity: 0.75 }}>{row.v}</div>
                    </div>
                  ))}
                </div>

                <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 6.5,
                  letterSpacing:'0em', textTransform:'none',
                  color: INK, opacity: 0.28, marginBottom: 10 }}>Allocations</div>

                <div style={{ display:'flex', flexDirection:'column', gap: 8, marginBottom: 18 }}>
                  {client.allocations.map(a => (
                    <div key={a.org}>
                      <div style={{ display:'flex', justifyContent:'space-between',
                        marginBottom: 4 }}>
                        <div>
                          <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 8,
                            color: a.type === 'ngo' ? NGO_C : CORP_C,
                            marginRight: 5 }}>{a.type === 'ngo' ? '◇' : '⬡'}</span>
                          <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 13,
                            color: INK }}>{a.org}</span>
                        </div>
                        <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 7.5,
                          color: INK, opacity: 0.5 }}>{fmt(a.amount)}</span>
                      </div>
                      <MiniBar value={a.progress}
                        color={a.type === 'ngo' ? NGO_C : CORP_C} />
                    </div>
                  ))}
                </div>

                <div style={{ border:`1px solid ${INK}12`, padding:'10px 12px',
                  marginBottom: 16, background:`${INK}02` }}>
                  <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 6,
                    letterSpacing:'0em', textTransform:'none',
                    color: INK, opacity: 0.28, marginBottom: 5 }}>Advisor Notes</div>
                  <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 12.5,
                    color: INK, opacity: 0.6, lineHeight: 1.75,
                    fontStyle:'italic', margin: 0 }}>{client.notes}</p>
                </div>

                <div style={{ display:'flex', flexDirection:'column', gap: 6 }}>
                  <button style={{ padding:'10px 0', background: INK, color: PARCH,
                    border:'none', cursor:'pointer', borderRadius: 2,
                    fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 7.5,
                    letterSpacing:'0.2em', textTransform:'uppercase' }}>
                    Open Discover Session
                  </button>
                  {client.status === 'review' && (
                    <button style={{ padding:'10px 0', background:'transparent',
                      color:'#C48A00', border:`1px solid #C48A0055`,
                      cursor:'pointer', borderRadius: 2,
                      fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 7.5,
                      letterSpacing:'0.2em', textTransform:'uppercase' }}>
                      Schedule Review Call
                    </button>
                  )}
                  {(client.aum >= 5_000_000 || client.status === 'foundation') && (
                    <button style={{ padding:'10px 0', background:'transparent',
                      color:'#6B1A8B', border:`1px solid #6B1A8B44`,
                      cursor:'pointer', borderRadius: 2,
                      fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize: 7.5,
                      letterSpacing:'0.2em', textTransform:'uppercase' }}>
                      ◇ Explore Foundation Path
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
