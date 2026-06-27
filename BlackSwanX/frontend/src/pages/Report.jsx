import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

export default function Report() {
  const [report, setReport] = useState(null)

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold text-white mb-2">Decision-Ready Map</h1>
      <p className="text-gray-400 mb-6 text-sm">
        Not what happened — where the future could change.
      </p>

      {!report ? (
        <div className="bg-[#111118] border border-gray-800 rounded-xl p-12 text-center">
          <p className="text-4xl text-gray-700 mb-4">▤</p>
          <p className="text-gray-500">
            Complete a simulation to generate a Decision-Ready Map.
          </p>
          <p className="text-gray-600 text-sm mt-2">
            The report shows Pressure Points, Prediction Scenarios, and Action Items.
          </p>
        </div>
      ) : (
        <div className="bg-[#111118] border border-gray-800 rounded-xl p-8">
          <article className="prose prose-invert prose-cyan max-w-none">
            <ReactMarkdown>{report.content_md}</ReactMarkdown>
          </article>

          {/* Pressure Points */}
          {report.pressure_points && (
            <div className="mt-8 border-t border-gray-800 pt-6">
              <h2 className="text-lg font-semibold text-cyan-400 mb-4">Pressure Points</h2>
              <div className="grid grid-cols-2 gap-3">
                {report.pressure_points.map((pp, i) => (
                  <div key={i} className="bg-[#0a0a0f] border border-gray-800 rounded-lg p-3">
                    <div className="text-sm font-medium text-white">{pp.point}</div>
                    <div className="text-xs text-gray-500 mt-1">{pp.why}</div>
                    <div className={`text-xs mt-2 ${
                      pp.actionability === 'high' ? 'text-red-400' :
                      pp.actionability === 'medium' ? 'text-yellow-400' : 'text-gray-400'
                    }`}>
                      {pp.actionability} actionability
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
