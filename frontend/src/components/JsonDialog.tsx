import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import type { Form } from '@/lib/api'

// Any COI JSON (or a saved {id, form, report} envelope) opened as a citizen mockup; nothing is saved.
function parseForm(raw: string): Form {
  const d = JSON.parse(raw)
  const form = d && typeof d === 'object' && 'form' in d && d.form?.tabs ? d.form : d
  if (!form || !Array.isArray(form.tabs)) throw new Error('To nie jest formularz COI: brakuje listy stron (tabs).')
  return form
}

export default function JsonDialog({ open, onOpenChange, onShow }: { open: boolean; onOpenChange: (v: boolean) => void; onShow: (f: Form, name: string) => void }) {
  const [raw, setRaw] = useState('')
  const [error, setError] = useState('')
  const show = (text: string, name: string) => {
    try { onShow(parseForm(text), name); setRaw(''); setError(''); onOpenChange(false) } catch (e) {
      setError(e instanceof SyntaxError ? `Niepoprawny JSON: ${e.message}` : e instanceof Error ? e.message : String(e))
    }
  }
  return (
    <Dialog open={open} onOpenChange={(v) => { setError(''); onOpenChange(v) }}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Podgląd JSON</DialogTitle>
          <DialogDescription>Otwórz dowolny plik JSON formularza COI jako makietę dla obywatela. Nic nie zostanie zapisane.</DialogDescription>
        </DialogHeader>
        <Tabs defaultValue="paste">
          <TabsList>
            <TabsTrigger value="paste">Wklej treść</TabsTrigger>
            <TabsTrigger value="file">Wybierz plik</TabsTrigger>
          </TabsList>
          <TabsContent value="paste" className="space-y-2 pt-2">
            <Label htmlFor="json-raw">Treść JSON</Label>
            <Textarea id="json-raw" rows={12} value={raw} onChange={(e) => setRaw(e.target.value)} className="h-64 max-h-[50vh] [field-sizing:fixed] font-mono text-xs"
              placeholder='{"title": "…", "tabs": [ … ]}' spellCheck={false} aria-invalid={!!error} />
          </TabsContent>
          <TabsContent value="file" className="space-y-2 pt-2">
            <Label htmlFor="json-file">Plik .json</Label>
            <input id="json-file" type="file" accept=".json,application/json"
              className="block w-full text-sm file:mr-3 file:rounded-md file:border file:border-input file:bg-card file:px-3 file:py-1.5 file:text-sm"
              onChange={async (e) => { const f = e.target.files?.[0]; if (f) show(await f.text(), f.name); e.target.value = '' }} />
          </TabsContent>
        </Tabs>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Anuluj</Button>
          <Button disabled={!raw.trim()} onClick={() => show(raw, 'Wklejony JSON')}>Pokaż makietę</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
