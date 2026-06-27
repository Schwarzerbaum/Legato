import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Bookmark, BookmarkCheck } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'
import { ACADEMIC, INDUSTRY } from '@/components/graph/colors'

interface TopicNodeData {
  topicId: string
  label: string
  sourceName: string
  degreeTags: string
  isAcademic: boolean
}

export const TopicNode = memo(function TopicNode({ data }: { data: TopicNodeData }) {
  const { activeTopicId, bookmarkedTopicIds, toggleBookmark } = useAppStore()
  const isActive = activeTopicId === data.topicId
  const isBookmarked = bookmarkedTopicIds.includes(data.topicId)

  const colors = data.isAcademic ? ACADEMIC : INDUSTRY

  return (
    <div
      className={cn(
        'group relative flex w-[170px] cursor-pointer flex-col justify-center rounded-xl border px-4 py-3 pr-9 shadow-sm select-none',
        'transition-all duration-150 hover:shadow-md hover:scale-[1.03]'
      )}
      style={isActive
        ? { borderColor: colors.border, backgroundColor: colors.selectedBg, color: '#fff' }
        : { borderColor: colors.border, backgroundColor: colors.bg, color: 'var(--foreground)' }
      }
    >
      <p className="ds-label leading-tight line-clamp-2">{data.label}</p>
      <p
        className="ds-caption mt-0.5 leading-tight truncate"
        style={{ color: isActive ? 'rgba(255,255,255,0.7)' : 'var(--muted-foreground)' }}
      >
        {data.sourceName} · {data.degreeTags}
      </p>

      {/* Bookmark button */}
      <button
        onClick={e => {
          e.stopPropagation()
          toggleBookmark(data.topicId)
        }}
        className="absolute right-2 top-2 flex size-6 items-center justify-center rounded-md transition-colors"
        style={{ color: isActive ? 'rgba(255,255,255,0.7)' : 'var(--muted-foreground)' }}
        aria-label={isBookmarked ? 'Remove bookmark' : 'Bookmark'}
      >
        {isBookmarked ? (
          <BookmarkCheck
            className="size-3.5"
            style={{ color: isActive ? '#fff' : colors.text }}
          />
        ) : (
          <Bookmark className="size-3.5" />
        )}
      </button>

      <Handle type="source" position={Position.Top} className="opacity-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Top} className="opacity-0 !w-0 !h-0" />
    </div>
  )
})
