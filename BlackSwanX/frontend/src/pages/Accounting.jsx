import { useState, useEffect, useCallback } from 'react'

const API = '/api'

export default function Accounting() {
  const [fiscalYears, setFiscalYears] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [skrVariant, setSkrVariant] = useState('SKR03')
  const [euerData, setEuerData] = useState(null)
  const [bookings, setBookings] = useState([])
  const [reflexMode, setReflexMode] = useState(true)
  const [analysisResults, setAnalysisResults] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const [importLoading, setImportLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [invoiceOpen, setInvoiceOpen] = useState(false)
  const [invoice, setInvoice] = useState({
    customer_name: '',
    customer_address: '',
    items: [{ description: '', quantity: 1, unit_price: 0, tax_rate: 19 }],
  })
  const [invoiceLoading, setInvoiceLoading] = useState(false)
  const [invoiceResult, setInvoiceResult] = useState(null)

  // Fetch fiscal years on mount
  useEffect(() => {
    fetch(`${API}/datev/fiscal-years`)
      .then(r => r.json())
      .then(data => {
        const years = Array.isArray(data) ? data : data.fiscal_years || []
        setFiscalYears(years)
        if (years.length > 0) setSelectedYear(years[0].id)
      })
      .catch(() => {})
  }, [])

  // Fetch EUeR data when fiscal year changes
  useEffect(() => {
    if (!selectedYear) return
    fetch(`${API}/accounting/euer/${selectedYear}`)
      .then(r => r.json())
      .then(setEuerData)
      .catch(() => setEuerData(null))
  }, [selectedYear])

  // Fetch bookings when fiscal year or reflex mode changes
  const fetchBookings = useCallback(() => {
    if (!selectedYear) return
    const url = `${API}/datev/bookings?fiscal_year_id=${selectedYear}${reflexMode ? '&reflex=true' : ''}`
    fetch(url)
      .then(r => r.json())
      .then(data => setBookings(Array.isArray(data) ? data : data.bookings || []))
      .catch(() => setBookings([]))
  }, [selectedYear, reflexMode])

  useEffect(() => { fetchBookings() }, [fetchBookings])

  // DATEV file import
  const handleFileUpload = async (file) => {
    if (!file) return
    setImportLoading(true)
    setImportResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API}/datev/import`, { method: 'POST', body: formData })
      const result = await res.json()
      setImportResult(result)
      fetchBookings()
    } catch (err) {
      setImportResult({ error: err.message })
    } finally {
      setImportLoading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    handleFileUpload(file)
  }

  // Run AI analysis
  const runAnalysis = async () => {
    if (!selectedYear) return
    setAnalysisLoading(true)
    setAnalysisResults(null)
    try {
      const res = await fetch(`${API}/datev/analyze/${selectedYear}`, { method: 'POST' })
      const data = await res.json()
      setAnalysisResults(data)
    } catch (err) {
      setAnalysisResults({ error: err.message })
    } finally {
      setAnalysisLoading(false)
    }
  }

  // Invoice helpers
  const addLineItem = () => {
    setInvoice(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0, tax_rate: 19 }],
    }))
  }

  const removeLineItem = (idx) => {
    setInvoice(prev => ({
      ...prev,
      items: prev.items.filter((_, i) => i !== idx),
    }))
  }

  const updateLineItem = (idx, field, value) => {
    setInvoice(prev => ({
      ...prev,
      items: prev.items.map((item, i) => i === idx ? { ...item, [field]: value } : item),
    }))
  }

  const invoiceSubtotal = invoice.items.reduce((sum, it) => sum + it.quantity * it.unit_price, 0)
  const invoiceTax = invoice.items.reduce((sum, it) => sum + it.quantity * it.unit_price * (it.tax_rate / 100), 0)
  const invoiceTotal = invoiceSubtotal + invoiceTax

  const createInvoice = async () => {
    setInvoiceLoading(true)
    setInvoiceResult(null)
    try {
      const res = await fetch(`${API}/accounting/invoice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invoice),
      })
      const data = await res.json()
      setInvoiceResult(data)
    } catch (err) {
      setInvoiceResult({ error: err.message })
    } finally {
      setInvoiceLoading(false)
    }
  }

  const fmt = (n) => typeof n === 'number' ? n.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' }) : '—'

  const glowClass = (intensity) => {
    if (intensity > 0.7) return 'shadow-[0_0_15px_rgba(239,68,68,0.6)]'
    if (intensity > 0.3) return 'shadow-[0_0_10px_rgba(245,158,11,0.4)]'
    if (intensity > 0.1) return 'shadow-[0_0_5px_rgba(6,182,212,0.3)]'
    return ''
  }

  return (
    <div className="max-w-7xl space-y-6">
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Accounting</h1>
          <p className="text-gray-400 text-sm mt-1">Living Dashboard — Biomimetic Financial Organism</p>
        </div>
        <div className="flex items-center gap-4">
          <select
            value={selectedYear || ''}
            onChange={e => setSelectedYear(e.target.value)}
            className="bg-[#111118] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-cyan-500"
          >
            {fiscalYears.map(fy => (
              <option key={fy.id} value={fy.id}>{fy.name || fy.year || fy.id}</option>
            ))}
            {fiscalYears.length === 0 && <option value="">No fiscal years</option>}
          </select>
          <div className="flex bg-[#111118] border border-gray-700 rounded-lg overflow-hidden">
            {['SKR03', 'SKR04'].map(v => (
              <button
                key={v}
                onClick={() => setSkrVariant(v)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  skrVariant === v ? 'bg-cyan-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Revenue" value={fmt(euerData?.total_revenue)} color="text-green-400" />
        <StatCard label="Total Expenses" value={fmt(euerData?.total_expenses)} color="text-red-400" />
        <StatCard
          label="Profit / Loss"
          value={fmt(euerData?.profit_loss)}
          color={euerData?.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <StatCard label="USt Zahllast" value={fmt(euerData?.ust_zahllast)} color="text-cyan-400" />
      </div>

      {/* DATEV Import Panel */}
      <div className="bg-[#111118] border border-gray-800 rounded-xl p-5">
        <h2 className="text-lg font-semibold text-white mb-3">DATEV Import</h2>
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            dragOver ? 'border-cyan-500 bg-cyan-500/5' : 'border-gray-700'
          }`}
        >
          <p className="text-gray-400 mb-3">Drag & drop a DATEV CSV file here</p>
          <label className="cursor-pointer bg-cyan-600 hover:bg-cyan-500 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors">
            Choose File
            <input
              type="file"
              accept=".csv,.txt"
              className="hidden"
              onChange={e => handleFileUpload(e.target.files[0])}
            />
          </label>
        </div>
        {importLoading && <p className="text-cyan-400 text-sm mt-3 animate-pulse">Importing...</p>}
        {importResult && !importResult.error && (
          <div className="mt-3 text-sm text-green-400">
            Imported {importResult.imported_count ?? 0} bookings.
            {importResult.errors?.length > 0 && (
              <span className="text-red-400 ml-2">{importResult.errors.length} errors</span>
            )}
          </div>
        )}
        {importResult?.error && (
          <p className="mt-3 text-sm text-red-400">Error: {importResult.error}</p>
        )}
      </div>

      {/* Bookings Table */}
      <div className="bg-[#111118] border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Bookings</h2>
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={reflexMode}
              onChange={e => setReflexMode(e.target.checked)}
              className="accent-cyan-500"
            />
            Reflex Mode
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-left border-b border-gray-800">
                <th className="pb-2 pr-3 font-medium">#</th>
                <th className="pb-2 pr-3 font-medium">Date</th>
                <th className="pb-2 pr-3 font-medium">Debit</th>
                <th className="pb-2 pr-3 font-medium">Credit</th>
                <th className="pb-2 pr-3 font-medium text-right">Amount</th>
                <th className="pb-2 pr-3 font-medium">Description</th>
                <th className="pb-2 font-medium text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {bookings.length === 0 ? (
                <tr><td colSpan={7} className="py-6 text-center text-gray-600">No bookings found.</td></tr>
              ) : (
                bookings.map((b, i) => (
                  <tr
                    key={b.id || i}
                    className={`border-b border-gray-800/50 hover:bg-white/5 transition-all rounded-lg ${glowClass(b.pheromone_intensity || 0)}`}
                  >
                    <td className="py-2 pr-3 text-gray-500">{i + 1}</td>
                    <td className="py-2 pr-3 text-gray-300">{b.date}</td>
                    <td className="py-2 pr-3 text-gray-300">{b.debit_account}</td>
                    <td className="py-2 pr-3 text-gray-300">{b.credit_account}</td>
                    <td className="py-2 pr-3 text-right text-white font-mono">{fmt(b.amount)}</td>
                    <td className="py-2 pr-3 text-gray-400 max-w-xs truncate">{b.description}</td>
                    <td className="py-2 text-center">
                      {b.locked ? (
                        <span className="text-yellow-500" title="Locked">🔒</span>
                      ) : (
                        <span className="text-gray-600" title="Open">○</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Financial AI Panel */}
      <div className="bg-[#111118] border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Financial AI Analysis</h2>
          <button
            onClick={runAnalysis}
            disabled={analysisLoading || !selectedYear}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {analysisLoading ? 'Analyzing...' : 'Run Analysis'}
          </button>
        </div>
        <div className="grid grid-cols-5 gap-3">
          <AICard
            title="Fraud Score"
            value={analysisResults?.fraud_score}
            loading={analysisLoading}
            accent="red"
            icon="⚠"
          />
          <AICard
            title="Tax Optimization"
            value={analysisResults?.tax_optimization}
            loading={analysisLoading}
            accent="green"
            icon="✦"
          />
          <AICard
            title="Cash Flow Forecast"
            value={analysisResults?.cash_flow_forecast}
            loading={analysisLoading}
            accent="blue"
            icon="◈"
          />
          <AICard
            title="Audit Risk"
            value={analysisResults?.audit_risk}
            loading={analysisLoading}
            accent="orange"
            icon="◉"
          />
          <AICard
            title="Regulatory Changes"
            value={analysisResults?.regulatory_changes}
            loading={analysisLoading}
            accent="purple"
            icon="§"
          />
        </div>
        {analysisResults?.error && (
          <p className="mt-3 text-sm text-red-400">Error: {analysisResults.error}</p>
        )}
      </div>

      {/* Invoice Quick-Create */}
      <div className="bg-[#111118] border border-gray-800 rounded-xl">
        <button
          onClick={() => setInvoiceOpen(prev => !prev)}
          className="w-full flex items-center justify-between p-5 text-left"
        >
          <h2 className="text-lg font-semibold text-white">Invoice Quick-Create</h2>
          <span className="text-gray-500 text-xl">{invoiceOpen ? '▾' : '▸'}</span>
        </button>
        {invoiceOpen && (
          <div className="px-5 pb-5 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Customer Name</label>
                <input
                  type="text"
                  value={invoice.customer_name}
                  onChange={e => setInvoice(prev => ({ ...prev, customer_name: e.target.value }))}
                  className="w-full bg-[#0a0a0f] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Customer Address</label>
                <input
                  type="text"
                  value={invoice.customer_address}
                  onChange={e => setInvoice(prev => ({ ...prev, customer_address: e.target.value }))}
                  className="w-full bg-[#0a0a0f] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* Line Items */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-500">Line Items</label>
                <button onClick={addLineItem} className="text-cyan-400 text-xs hover:text-cyan-300">+ Add Item</button>
              </div>
              <div className="space-y-2">
                {invoice.items.map((item, idx) => (
                  <div key={idx} className="flex gap-2 items-center">
                    <input
                      type="text"
                      placeholder="Description"
                      value={item.description}
                      onChange={e => updateLineItem(idx, 'description', e.target.value)}
                      className="flex-1 bg-[#0a0a0f] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-cyan-500"
                    />
                    <input
                      type="number"
                      min="1"
                      value={item.quantity}
                      onChange={e => updateLineItem(idx, 'quantity', Number(e.target.value))}
                      className="w-20 bg-[#0a0a0f] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm text-right focus:outline-none focus:border-cyan-500"
                      placeholder="Qty"
                    />
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.unit_price}
                      onChange={e => updateLineItem(idx, 'unit_price', Number(e.target.value))}
                      className="w-28 bg-[#0a0a0f] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm text-right focus:outline-none focus:border-cyan-500"
                      placeholder="Price"
                    />
                    <select
                      value={item.tax_rate}
                      onChange={e => updateLineItem(idx, 'tax_rate', Number(e.target.value))}
                      className="w-24 bg-[#0a0a0f] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-cyan-500"
                    >
                      <option value={19}>19%</option>
                      <option value={7}>7%</option>
                      <option value={0}>0%</option>
                    </select>
                    {invoice.items.length > 1 && (
                      <button
                        onClick={() => removeLineItem(idx)}
                        className="text-red-400 hover:text-red-300 text-sm px-2"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Totals */}
            <div className="flex justify-end">
              <div className="text-sm space-y-1 text-right">
                <div className="text-gray-400">Subtotal: <span className="text-white font-mono">{fmt(invoiceSubtotal)}</span></div>
                <div className="text-gray-400">Tax: <span className="text-white font-mono">{fmt(invoiceTax)}</span></div>
                <div className="text-gray-300 font-semibold">Total: <span className="text-cyan-400 font-mono">{fmt(invoiceTotal)}</span></div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={createInvoice}
                disabled={invoiceLoading || !invoice.customer_name}
                className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                {invoiceLoading ? 'Creating...' : 'Create Invoice'}
              </button>
              {invoiceResult && !invoiceResult.error && (
                <span className="text-green-400 text-sm">Invoice created: {invoiceResult.invoice_number || invoiceResult.id}</span>
              )}
              {invoiceResult?.error && (
                <span className="text-red-400 text-sm">Error: {invoiceResult.error}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ---------- Sub-components ---------- */

function StatCard({ label, value, color }) {
  return (
    <div className="bg-[#111118] border border-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  )
}

function AICard({ title, value, loading, accent, icon }) {
  const colors = {
    red: 'border-red-900/50 text-red-400',
    green: 'border-green-900/50 text-green-400',
    blue: 'border-blue-900/50 text-blue-400',
    orange: 'border-orange-900/50 text-orange-400',
    purple: 'border-purple-900/50 text-purple-400',
  }
  const bgColors = {
    red: 'bg-red-500/5',
    green: 'bg-green-500/5',
    blue: 'bg-blue-500/5',
    orange: 'bg-orange-500/5',
    purple: 'bg-purple-500/5',
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[accent]} ${bgColors[accent]}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icon}</span>
        <span className="text-xs font-medium uppercase tracking-wide">{title}</span>
      </div>
      {loading ? (
        <div className="h-8 flex items-center">
          <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
            <div className="h-full bg-cyan-500/50 rounded-full animate-pulse w-3/4" />
          </div>
        </div>
      ) : value !== undefined && value !== null ? (
        <div className="text-lg font-bold font-mono">
          {typeof value === 'object' ? (
            <div className="text-xs font-normal space-y-1">
              {Object.entries(value).map(([k, v]) => (
                <div key={k}><span className="text-gray-500">{k}:</span> {String(v)}</div>
              ))}
            </div>
          ) : (
            String(value)
          )}
        </div>
      ) : (
        <div className="text-gray-600 text-sm">Awaiting analysis</div>
      )}
    </div>
  )
}
