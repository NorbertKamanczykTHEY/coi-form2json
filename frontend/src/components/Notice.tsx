import { toast } from 'sonner'
import type { Msg } from '@/lib/messages'
import { cn } from '@/lib/utils'

// One review note or error: title, why, what to do; the original backend text stays available for context.
export default function Notice({ m, className, children }: { m: Msg; className?: string; children?: React.ReactNode }) {
  return (
    <div className={cn('min-w-0 text-sm', className)} data-testid="notice">
      <p className="font-medium">{m.title}</p>
      <p className="text-muted-foreground">{m.why}</p>
      <p className="mt-0.5"><span className="font-medium">Co zrobić: </span>{m.action}</p>
      {m.original && m.original !== m.why && <p className="mt-0.5 text-xs break-words text-muted-foreground" title="Oryginalny komunikat">Szczegóły: {m.original}</p>}
      {children}
    </div>
  )
}

export const toastError = (m: Msg) => toast.error(m.title, { description: `${m.why} Co zrobić: ${m.action}`, duration: 10_000 })
