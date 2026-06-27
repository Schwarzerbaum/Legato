import { useRef, useEffect } from 'react'

export default function BlackSwanXMap() {
  const svgRef = useRef(null)

  // D3 visualization will be added when data flows in
  useEffect(() => {
    if (!svgRef.current) return
    // Placeholder — D3 force graph will render here
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-2">BlackSwanX Map</h1>
      <p className="text-gray-400 mb-6 text-sm">
        Track how ideas flow across platforms: Reddit → X → YouTube
      </p>

      <div className="bg-[#111118] border border-gray-800 rounded-xl p-6 min-h-[500px] flex items-center justify-center">
        <svg ref={svgRef} className="w-full h-[500px]">
          {/* D3 renders here */}
        </svg>
        <div className="absolute text-gray-600 text-sm">
          Run an analysis to see cross-platform blackswanx flows
        </div>
      </div>

      {/* Platform Legend */}
      <div className="flex gap-6 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-orange-500" />
          <span className="text-gray-400">Reddit</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-sky-500" />
          <span className="text-gray-400">X / Twitter</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-gray-400">YouTube</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-gray-400">Web / News</span>
        </div>
      </div>
    </div>
  )
}
