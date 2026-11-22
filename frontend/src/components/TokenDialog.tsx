import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { token } from '@/lib/api'

export default function TokenDialog({ open, onOpenChange, onSaved }: { open: boolean; onOpenChange: (v: boolean) => void; onSaved: () => void }) {
  const [value, setValue] = useState('')
  return (
    <Dialog open={open} onOpenChange={(v) => { setValue(''); onOpenChange(v) }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Token dostępu</DialogTitle>
          <DialogDescription>
            Wklej token JWT od administratora. Zostaje tylko w tej karcie przeglądarki i znika po jej zamknięciu.
          </DialogDescription>
        </DialogHeader>
        <form id="token-form" className="space-y-2" onSubmit={(e) => { e.preventDefault(); token.set(value); onSaved(); onOpenChange(false) }}>
          <Label htmlFor="token">Token</Label>
          <Textarea id="token" rows={4} value={value} onChange={(e) => setValue(e.target.value)} placeholder="eyJhbGciOi…"
            className="max-h-40 font-mono text-xs break-all" autoComplete="off" spellCheck={false} />
        </form>
        <DialogFooter>
          {token.get() && <Button variant="ghost" onClick={() => { token.set(''); onSaved(); onOpenChange(false) }}>Usuń token</Button>}
          <Button type="submit" form="token-form" disabled={!value.trim()}>Zapisz token</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
