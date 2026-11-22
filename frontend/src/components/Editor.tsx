import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, BookMarked, Check, ChevronDown, CircleAlert, Download, Loader2, RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import ConditionDialog, { ConditionMark } from '@/components/ConditionDialog'
import Preview, { type Editing, type Review } from '@/Preview'
import { api, ApiError, type Envelope, type Form, type Proposal } from '@/lib/api'
import { accepted, applyProposal, fieldsOf, isRequired, points, setRequired, tabsOf, text, TYPE_LABEL, walk, type Field, type Point, type Q } from '@/lib/form'
import { cn } from '@/lib/utils'
import { plural } from '@/lib/plural'

const OVERVIEW = '__form'

export default function Editor({ id, onBack, onChanged }: { id: string; onBack: () => void; onChanged: () => void }) {
  const [env, setEnv] = useState<Envelope | null>(null)
  const [loadError, setLoadError] = useState('')
  const [draft, setDraft] = useState<Form | null>(null)
  const [resolved, setResolved] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<{ path?: string; message?: string }[]>([])
  const [page, setPage] = useState(OVERVIEW)
  const [leave, setLeave] = useState(false)
  const [cond, setCond] = useState<{ fieldId: string; index: number | null } | null>(null)

  const load = (e: Envelope) => { setEnv(e); setDraft(e.form); setResolved(e.editor?.resolved ?? []); setErrors([]) }
  useEffect(() => { api.get(id).then(load).catch((e) => setLoadError(e instanceof Error ? e.message : String(e))) }, [id])

  const formDirty = useMemo(() => !!env && !!draft && JSON.stringify(env.form) !== JSON.stringify(draft), [env, draft])
  const resolvedDirty = !!env && JSON.stringify(env.editor?.resolved ?? []) !== JSON.stringify(resolved)
  const dirty = formDirty || resolvedDirty
  useEffect(() => {
    const guard = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault() }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [dirty])

  const pts = useMemo(() => (env && draft ? points(env, draft) : []), [env, draft])
  const done = new Set(resolved)
  const open = pts.filter((p) => !done.has(p.key))
  const byField = new Map<string, Point[]>()
  for (const p of pts) if (p.fieldId) byField.set(p.fieldId, [...(byField.get(p.fieldId) ?? []), p])

  if (loadError) return <Shell onBack={onBack}><p role="alert" className="text-sm text-destructive">Nie udało się wczytać projektu: {loadError}</p></Shell>
  if (!env || !draft) return <Shell onBack={onBack}><p className="text-sm text-muted-foreground" aria-live="polite">Wczytuję projekt…</p></Shell>

  const tabs = tabsOf(draft)
  const openOn = (qs: Q[]) => walk(qs).reduce((n, f) => n + (byField.get(f.id) ?? []).filter((p) => !done.has(p.key)).length, 0)
  const general = pts.filter((p) => !p.fieldId)
  const proposals = env.editor?.proposals ?? []
  const pendingProposals = proposals.filter((p) => !accepted(draft, p))
  const overviewOpen = general.filter((p) => !done.has(p.key)).length + pendingProposals.length

  const edit = (fn: (f: Form) => void) => setDraft((d) => { const c = structuredClone(d!); fn(c); return c })
  // a correction of the field settles its review points
  const settle = (fid: string) => {
    const keys = (byField.get(fid) ?? []).map((p) => p.key).filter((k) => !done.has(k))
    if (keys.length) setResolved((r) => [...new Set([...r, ...keys])])
  }
  const editField = (fid: string, fn: (f: Field) => void) => {
    edit((c) => { const f = fieldsOf(c).find((x) => x.id === fid); if (f) fn(f) })
    settle(fid)
  }
  const editing: Editing = {
    change: (fn, o = {}) => {
      const prev = draft
      edit(fn)
      if (o.fieldId) settle(o.fieldId)
      if (o.undo) toast(o.undo, { action: { label: 'Cofnij', onClick: () => setDraft(prev) } })
    },
    condition: (fieldId, index) => setCond({ fieldId, index }),
  }
  const condField = cond ? fieldsOf(draft).find((f) => f.id === cond.fieldId) : undefined
  const setStates = (fn: (s: NonNullable<Field['states']>) => void) =>
    editField(cond!.fieldId, (f) => { f.states = [...(f.states ?? [])]; fn(f.states) })
  const toggle = (keys: string[], on: boolean) => setResolved((r) => (on ? [...new Set([...r, ...keys])] : r.filter((k) => !keys.includes(k))))

  async function save(form = draft!, keys = resolved) {
    setSaving(true)
    setErrors([])
    try {
      let saved = env!.form
      if (JSON.stringify(form) !== JSON.stringify(env!.form)) saved = await api.save(id, form)
      const res = JSON.stringify(keys) !== JSON.stringify(env!.editor?.resolved ?? []) ? (await api.resolve(id, keys)).resolved : keys
      setEnv((e) => ({ ...e!, form: saved, editor: { ...e!.editor, resolved: res } }))
      setDraft(saved)
      setResolved(res)
      toast.success('Zapisano zmiany')
      onChanged()
      return true
    } catch (e) {
      if (e instanceof ApiError && e.errors.length) setErrors(e.errors)
      toast.error(e instanceof ApiError && e.status === 422 ? 'Formularz ma błędy, nie zapisano. Popraw je i zapisz ponownie.' : `Nie zapisano: ${e instanceof Error ? e.message : e}`)
      return false
    } finally {
      setSaving(false)
    }
  }

  async function acceptProposal(p: Proposal) {
    try {
      await api.createDictionary(p.dictionary)
      const next = applyProposal(draft!, p)
      setDraft(next)
      if (await save(next)) toast.success(`Słownik „${p.dictionary.name}” przyjęty`)
    } catch (e) {
      toast.error(`Słownik nie został utworzony: ${e instanceof Error ? e.message : e}`)
    }
  }

  function download() {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' }))
    a.download = `${(draft as { title?: string }).title || 'formularz'}.json`.replace(/[\\/:*?"<>|]/g, '_')
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const review: Review = new Map(open.filter((p) => p.fieldId).map((p) => [p.fieldId!, p.why]))
  const current = tabs.find((t) => t.id === page)
  const title = (draft as { title?: string }).title ?? ''

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="sticky top-14 z-20 border-b bg-card/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <Button variant="ghost" size="sm" onClick={() => (dirty ? setLeave(true) : onBack())}><ArrowLeft />Projekty</Button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg leading-tight font-semibold" title={title}>{title || 'Formularz bez tytułu'}</h1>
            <p className="truncate text-xs text-muted-foreground">
              {open.length ? <span className="font-medium text-review" data-testid="open-count">{plural(open.length, 'uwaga', 'uwagi', 'uwag')} do decyzji</span> : <span className="text-ok">Wszystkie uwagi rozstrzygnięte</span>}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={download}><Download />Pobierz JSON</Button>
          <Button size="sm" onClick={() => save()} disabled={!dirty || saving} data-testid="save">
            {saving ? <Loader2 className="animate-spin" /> : dirty ? <Save /> : <Check />}{dirty ? 'Zapisz zmiany' : 'Zapisano'}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="edit" className="mx-auto w-full max-w-7xl flex-1 gap-0 px-4 pt-4 sm:px-6">
        <TabsList>
          <TabsTrigger value="edit">Pola i uwagi</TabsTrigger>
          <TabsTrigger value="preview">Makieta dla obywatela</TabsTrigger>
        </TabsList>

        {errors.length > 0 && (
          <div role="alert" className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
            <p className="font-medium text-destructive">Zmiany nie zostały zapisane. Popraw te miejsca:</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">{errors.slice(0, 12).map((e, i) => <li key={i}><code className="text-xs">{e.path}</code> {e.message}</li>)}</ul>
          </div>
        )}

        <TabsContent value="edit" className="grid gap-6 py-4 md:grid-cols-[15rem_minmax(0,1fr)]">
          <nav aria-label="Strony formularza" className="md:sticky md:top-32 md:self-start">
            <ul className="flex gap-1 overflow-x-auto md:flex-col">
              <PageLink active={page === OVERVIEW} onClick={() => setPage(OVERVIEW)} label="Cały formularz" open={overviewOpen} />
              {tabs.map((t) => <PageLink key={t.id} active={page === t.id} onClick={() => setPage(t.id)} label={t.title} open={openOn(t.questions)} />)}
            </ul>
          </nav>

          <div className="min-w-0 space-y-4">
            {page === OVERVIEW || !current ? (
              <Overview title={title} onTitle={(v) => edit((c) => { (c as { title?: string }).title = v })}
                general={general} done={done} toggle={toggle} proposals={proposals} draft={draft} onAccept={acceptProposal}
                env={env} dirty={dirty} onRegenerated={(e) => { load(e); onChanged(); toast.success('Formularz przebudowany') }} />
            ) : (
              <>
                <div>
                  <Label htmlFor="page-title" className="text-xs text-muted-foreground">Tytuł strony</Label>
                  <Input id="page-title" value={current.title} className="mt-1 h-10 text-base font-semibold"
                    onChange={(e) => edit((c) => { tabsOf(c).find((t) => t.id === current.id)!.title = e.target.value })} />
                </div>
                <ul className="space-y-2">
                  {current.questions.slice().sort((a, b) => a.y - b.y || a.x - b.x).map((q) => (
                    <FieldRow key={q.field.id} f={q.field} depth={0} byField={byField} done={done} toggle={toggle} editField={editField} form={draft} onCondition={editing.condition} />
                  ))}
                </ul>
              </>
            )}
          </div>
        </TabsContent>

        <TabsContent value="preview" className="-mx-4 py-4 sm:-mx-6">
          <Preview form={draft} review={review} editing={editing} />
        </TabsContent>
      </Tabs>

      {cond && condField && (
        <ConditionDialog form={draft} owner={condField} state={cond.index == null ? null : condField.states?.[cond.index] ?? null} onClose={() => setCond(null)}
          onSave={(st) => { setStates((l) => { if (cond.index == null) l.push(st); else l[cond.index] = st }); setCond(null) }}
          onRemove={cond.index == null ? undefined : () => { setStates((l) => { l.splice(cond.index!, 1) }); setCond(null) }} />
      )}

      <AlertDialog open={leave} onOpenChange={setLeave}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Wyjść bez zapisu?</AlertDialogTitle>
            <AlertDialogDescription>Masz niezapisane zmiany w tym projekcie. Po wyjściu przepadną.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Zostań</AlertDialogCancel>
            <AlertDialogAction variant="outline" onClick={onBack}>Wyjdź bez zapisu</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function Shell({ onBack, children }: { onBack: () => void; children: React.ReactNode }) {
  return <div className="mx-auto w-full max-w-7xl space-y-4 px-4 py-6 sm:px-6"><Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft />Projekty</Button>{children}</div>
}

function PageLink({ active, onClick, label, open }: { active: boolean; onClick: () => void; label: string; open: number }) {
  return (
    <li className="shrink-0">
      <button type="button" onClick={onClick} aria-current={active ? 'page' : undefined} data-testid="page-link" data-open={open}
        className={cn('flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
          active ? 'bg-accent font-medium text-accent-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {open > 0 && <span className="flex items-center gap-1 text-xs font-medium text-review tabular-nums" data-testid="red-dot">
          <span className="size-2 rounded-full bg-review" aria-hidden /><span aria-hidden>{open}</span><span className="sr-only">{plural(open, 'nierozstrzygnięta uwaga', 'nierozstrzygnięte uwagi', 'nierozstrzygniętych uwag')}</span>
        </span>}
      </button>
    </li>
  )
}

function Points({ items, done, toggle }: { items: Point[]; done: Set<string>; toggle: (keys: string[], on: boolean) => void }) {
  const keys = [...new Set(items.map((p) => p.key))]
  const isOpen = keys.some((k) => !done.has(k))
  return (
    <div className={cn('rounded-md px-3 py-2 text-sm', isOpen ? 'bg-review-soft text-foreground' : 'bg-ok-soft')} data-testid={isOpen ? 'review-open' : 'review-done'}>
      <ul className="space-y-1">
        {items.map((p, i) => (
          <li key={i} className="flex gap-2">
            {isOpen ? <CircleAlert className="mt-0.5 size-4 shrink-0 text-review" aria-hidden /> : <Check className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />}
            <span>{p.why}{p.fails.map((f, j) => <span key={j} className="mt-0.5 block text-xs text-muted-foreground">{f}</span>)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex flex-wrap items-center gap-2 pl-6">
        {isOpen
          ? <><Button size="xs" variant="outline" className="bg-card" onClick={() => toggle(keys, true)} data-testid="accept-point">Akceptuję bez zmian</Button>
              <span className="text-xs text-muted-foreground">albo popraw pole, to też rozstrzyga uwagę</span></>
          : <><span className="text-xs font-medium text-ok">Rozstrzygnięte</span>
              <Button size="xs" variant="ghost" onClick={() => toggle(keys, false)}><RotateCcw />Cofnij</Button></>}
      </div>
    </div>
  )
}

function FieldRow({ f, depth, byField, done, toggle, editField, form, onCondition }: {
  f: Field; depth: number; byField: Map<string, Point[]>; done: Set<string>; toggle: (keys: string[], on: boolean) => void
  editField: (id: string, fn: (f: Field) => void) => void; form: Form; onCondition: (fieldId: string, index: number | null) => void
}) {
  const pts = byField.get(f.id) ?? []
  const isOpen = pts.some((p) => !done.has(p.key))
  const [expanded, setExpanded] = useState(false)
  const children = f.repeatingSectionGrid?.slice().sort((a, b) => a.y - b.y || a.x - b.x) ?? []
  const container = f.type === 'SECTION' || f.type === 'REPEATING_SECTION'
  const choice = (f.type === 'RADIO' || f.type === 'CHECKBOX' || f.type === 'SELECT') && !f.dictionaryName
  const panel = `field-${f.id}`

  return (
    <li data-testid="field-row" data-review={isOpen ? 'open' : pts.length ? 'done' : 'none'}>
      <div className={cn('rounded-lg border bg-card', isOpen && 'border-review ring-1 ring-review', container && 'bg-muted/40')}>
        <button type="button" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded} aria-controls={panel}
          className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
          <ChevronDown className={cn('size-4 shrink-0 text-muted-foreground transition-transform', !expanded && '-rotate-90')} aria-hidden />
          <span className="min-w-0 flex-1">
            <span className={cn('block truncate text-sm', container ? 'font-semibold' : 'font-medium')}>
              {f.title || <span className="text-muted-foreground italic">bez etykiety</span>}{isRequired(f) && <span className="text-destructive" aria-label="wymagane"> *</span>}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {TYPE_LABEL[f.type] ?? f.type}{f.dictionaryName ? `, słownik ${f.dictionaryName}` : ''}{f.states?.some((s) => s.type === 'SHOW') ? ', pokazywane warunkowo' : ''}
            </span>
          </span>
          {isOpen && <CircleAlert className="size-5 shrink-0 text-review" aria-label="Wymaga decyzji" />}
          {!isOpen && pts.length > 0 && <Check className="size-5 shrink-0 text-ok" aria-label="Uwaga rozstrzygnięta" />}
        </button>
        {f.states?.some((s) => s.query) && <div className="px-3"><ConditionMark form={form} f={f} onEdit={(i) => onCondition(f.id, i)} /></div>}
        {pts.length > 0 && <div className="px-3 pb-3"><Points items={pts} done={done} toggle={toggle} /></div>}
        {expanded && (
          <div id={panel} className="grid gap-3 border-t px-3 py-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor={`${panel}-t`}>Etykieta</Label>
              <Input id={`${panel}-t`} className="mt-1" value={f.title ?? ''} onChange={(e) => editField(f.id, (x) => { x.title = e.target.value })} />
            </div>
            {!container && f.type !== 'TEXT_BLOCK' && <>
              <div className="sm:col-span-2">
                <Label htmlFor={`${panel}-d`}>Podpowiedź pod polem</Label>
                <Textarea id={`${panel}-d`} rows={2} className="mt-1" value={text(f.description)} onChange={(e) => editField(f.id, (x) => { x.description = e.target.value })} />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <Switch checked={isRequired(f)} onCheckedChange={(v) => editField(f.id, (x) => setRequired(x, v))} />Pole wymagane
              </label>
              <p className="text-xs text-muted-foreground sm:text-right">Nazwa techniczna: <code>{f.techName}</code></p>
              {!f.states?.length && <Button size="xs" variant="outline" className="justify-self-start" onClick={() => onCondition(f.id, null)}>Dodaj warunek</Button>}
            </>}
            {f.type === 'TEXT_BLOCK' && (
              <div className="sm:col-span-2">
                <Label htmlFor={`${panel}-d`}>Treść</Label>
                <Textarea id={`${panel}-d`} rows={3} className="mt-1" value={text(f.description)} onChange={(e) => editField(f.id, (x) => { x.description = e.target.value })} />
              </div>
            )}
            {choice && (
              <div className="sm:col-span-2">
                <Label htmlFor={`${panel}-o`}>Opcje (jedna w wierszu)</Label>
                <Textarea id={`${panel}-o`} rows={Math.min(8, (f.options?.length ?? 0) + 1)} className="mt-1" value={(f.options ?? []).map((o) => o.name).join('\n')}
                  onChange={(e) => editField(f.id, (x) => {
                    const old = x.options ?? []
                    x.options = e.target.value.split('\n').map((name, i) => ({ id: old[i]?.id ?? crypto.randomUUID(), name }))
                  })} />
              </div>
            )}
          </div>
        )}
        {children.length > 0 && (
          <ul className="space-y-2 px-3 pb-3">
            {children.map((q) => <FieldRow key={q.field.id} f={q.field} depth={depth + 1} byField={byField} done={done} toggle={toggle} editField={editField} form={form} onCondition={onCondition} />)}
          </ul>
        )}
      </div>
    </li>
  )
}

function Overview({ title, onTitle, general, done, toggle, proposals, draft, onAccept, env, dirty, onRegenerated }: {
  title: string; onTitle: (v: string) => void; general: Point[]; done: Set<string>; toggle: (keys: string[], on: boolean) => void
  proposals: Proposal[]; draft: Form; onAccept: (p: Proposal) => Promise<void>; env: Envelope; dirty: boolean; onRegenerated: (e: Envelope) => void
}) {
  const [busy, setBusy] = useState('')
  const byId = new Map(fieldsOf(draft).map((f) => [f.id, f]))
  return (
    <div className="space-y-6">
      <div>
        <Label htmlFor="form-title" className="text-xs text-muted-foreground">Tytuł formularza</Label>
        <Input id="form-title" value={title} onChange={(e) => onTitle(e.target.value)} className="mt-1 h-10 text-base font-semibold" />
      </div>

      {general.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-semibold">Uwagi do całego formularza</h2>
          <Points items={general} done={done} toggle={toggle} />
        </section>
      )}

      <section className="space-y-2">
        <h2 className="font-semibold">Proponowane słowniki</h2>
        {proposals.length === 0 && <p className="text-sm text-muted-foreground">Dla tego formularza nie ma propozycji nowych słowników.</p>}
        {proposals.map((p) => {
          const ok = accepted(draft, p)
          return (
            <div key={p.dictionary.id} className={cn('rounded-lg border bg-card p-4', !ok && 'border-primary/40')} data-testid="proposal">
              <div className="flex flex-wrap items-start gap-3">
                <BookMarked className="mt-0.5 size-5 text-primary" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{p.dictionary.name} <code className="text-xs text-muted-foreground">{p.dictionary.id}</code></p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {plural(p.dictionary.items.length, 'pozycja', 'pozycje', 'pozycji')}: {p.dictionary.items.slice(0, 6).map((i) => (i as { name?: string }).name).join(', ')}{p.dictionary.items.length > 6 ? '…' : ''}
                  </p>
                  <p className="mt-1 text-sm">Pola: {p.fieldIds.map((fid) => byId.get(fid)?.title ?? fid).join(', ')}</p>
                </div>
                {ok ? <Badge variant="secondary" className="bg-ok-soft text-ok"><Check />Przyjęty</Badge>
                  : <Button size="sm" disabled={!!busy} onClick={async () => { setBusy(p.dictionary.id); await onAccept(p); setBusy('') }}>
                      {busy === p.dictionary.id && <Loader2 className="animate-spin" />}Przyjmij słownik
                    </Button>}
              </div>
            </div>
          )
        })}
      </section>

      <SelfOnly env={env} dirty={dirty} onDone={onRegenerated} />
    </div>
  )
}

// "Only in person" switch (ADR 0027): rebuilds the form on the server, which replaces manual edits.
function SelfOnly({ env, dirty, onDone }: { env: Envelope; dirty: boolean; onDone: (e: Envelope) => void }) {
  const [ask, setAsk] = useState(false)
  const [busy, setBusy] = useState(false)
  const s = env.editor?.applicant_self_only
  if (!s) return null
  const from = s.source === 'dokument' ? `z dokumentu${s.quote ? `: „${s.quote}”` : ''}` : s.source === 'edytor' ? 'ustawione ręcznie' : 'ustawienie domyślne'
  async function go() {
    setBusy(true)
    try { onDone(await api.regenerate(env.id, !s!.value)); setAsk(false) } catch (e) {
      toast.error(e instanceof ApiError && e.status === 409 ? 'Ten projekt powstał przed tą funkcją. Zaimportuj plik ponownie, żeby go przebudować.' : `Nie przebudowano: ${e instanceof Error ? e.message : e}`)
    } finally { setBusy(false) }
  }
  return (
    <section className="space-y-2">
      <h2 className="font-semibold">Sposób składania</h2>
      <div className="flex items-start gap-3 rounded-lg border bg-card p-4 text-sm">
        <Switch id="self-only" checked={s.value} disabled={busy || dirty} onCheckedChange={() => setAsk(true)} />
        <div>
          <Label htmlFor="self-only">Wniosek składa się tylko osobiście (bez pełnomocnika)</Label>
          <p className="mt-0.5 text-muted-foreground">Źródło: {from}.{dirty && ' Zapisz zmiany, zanim to przełączysz.'}</p>
        </div>
      </div>
      <AlertDialog open={ask} onOpenChange={(v) => !busy && setAsk(v)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Przebudować formularz?</AlertDialogTitle>
            <AlertDialogDescription>Formularz zostanie zbudowany od nowa z tym ustawieniem. Ręczne poprawki pól zostaną zastąpione.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Anuluj</AlertDialogCancel>
            <AlertDialogAction disabled={busy} onClick={(e) => { e.preventDefault(); go() }}>{busy ? 'Przebudowuję…' : 'Przebuduj formularz'}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
