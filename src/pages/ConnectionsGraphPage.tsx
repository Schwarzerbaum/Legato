import { useAppStore } from '@/store/useAppStore'
import { MultiTopicFlow, MultiTopicFlowEmptyState } from '@/components/graph/MultiTopicFlow'

export function ConnectionsGraphPage() {
  const { bookmarkedTopicIds } = useAppStore()

  if (bookmarkedTopicIds.length === 0) {
    return <MultiTopicFlowEmptyState />
  }

  return (
    <div className="h-full w-full">
      <MultiTopicFlow topicIds={bookmarkedTopicIds} />
    </div>
  )
}
