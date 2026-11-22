import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, BookMarked, Check, CircleAlert, Download, Loader2, RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import ConditionDialog from '@/components/ConditionDialog'
import Notice, { toastError } from '@/components/Notice'
import Preview, { type Editing, type Review } from '@/Preview'
import { api, ApiError, type Envelope, type Form, type Proposal } from '@/lib/api'
import { accepted, applyProposal, fieldsOf, points, tabsOf, walk, type Field, type Point, type Q } from '@/lib/form'
import { apiMsg, reviewMsg, validationMsg, type Msg } from '@/lib/messages'
import { cn } from '@/lib/utils'
import { plural } from '@/lib/plural'

const OVERVIEW = '__form'
type SaveError = { m: Msg; fieldId?: string }

// Field id at a validator JSON pointer (/tabs/0/questions/2/field/...): the deepest object on the path that is a field.
function fieldAt(form: Form, path = '') {
  let o: unknown = form
  let id: string | undefined
  for (const k of path.split('/').filter(Boolean)) {
    o = (o as Record<string, unknown> | undefined)?.[k]
    if (o && typeof o === 'object' && 'techName' in o && 'type' in o) id = (o as Field).id
  }
  return id
}

export default function Editor({ id, onBack, onChanged }: { id: string; onBack: () => void; onChanged: () => void }) {
  const [env, setEnv] = useState<Envelope | null>(null)
  const [loadError, setLoadError] = useState<Msg | null>(null)
  const [draft, setDraft] = useState<Form | null>(null)
  const [resolved, setResolved] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<SaveError[]>([])
  const [page, setPage] = useState('')
  const [leave, setLeave] = useState(false)
  const [cond, setCond] = useState<{ fieldId: string; index: number | null } | null>(null)

  const load = (e: Envelope) => { setEnv(e); setDraft(e.form); setResolved(e.editor?.resolved ?? []); setErrors([]) }
  useEffect(() => { api.get(id).then(load).catch((e) => setLoadError(apiMsg(e))) }, [id])

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

  if (loadError) return <Shell onBack={onBack}><div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-4"><Notice m={loadError} /></div></Shell>
  if (!env || !draft) return <Shell onBack={onBack}><p className="text-sm text-muted-foreground" aria-live="polite">Wczytuję projekt…</p></Shell>

  const tabs = tabsOf(draft)
  const cur = page || tabs[0]?.id || OVERVIEW
  const openOn = (qs: Q[]) => walk(qs).reduce((n, f) => n + (byField.get(f.id) ?? []).filter((p) => !done.has(p.key)).length + errors.filter((e) => e.fieldId === f.id).length, 0)
  const general = pts.filter((p) => !p.fieldId)
  const proposals = env.editor?.proposals ?? []
  const pendingProposals = proposals.filter((p) => !accepted(draft, p))
  const overviewOpen = general.filter((p) => !done.has(p.key)).length + pendingProposals.length

  const edit = (fn: (f: Form) => void) => setDraft((d) => { const c = structuredClone(d!); fn(c); return c })
  // a correction of the field settles its review points and clears its save errors
  const settle = (fid: string) => {
    const keys = (byField.get(fid) ?? []).map((p) => p.key).filter((k) => !done.has(k))
    if (keys.length) setResolved((r) => [...new Set([...r, ...keys])])
    setErrors((l) => (l.some((e) => e.fieldId === fid) ? l.filter((e) => e.fieldId !== fid) : l))
  }
  const toggle = (keys: string[], on: boolean) => setResolved((r) => (on ? [...new Set([...r, ...keys])] : r.filter((k) => !keys.includes(k))))
  const editing: Editing = {
    change: (fn, o = {}) => {
      const prev = draft
      edit(fn)
      if (o.fieldId) settle(o.fieldId)
      if (o.undo) toast(o.undo, { action: { label: 'Cofnij', onClick: () => setDraft(prev) } })
    },
    condition: (fieldId, index) => setCond({ fieldId, index }),
    notes: (fid) => {
      const fp = byField.get(fid) ?? []
      const fe = errors.filter((e) => e.fieldId === fid)
      if (!fp.length && !fe.length) return null
      return <div className="mt-2 space-y-2">
        {fe.map((e, i) => <div key={i} className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2" data-testid="save-error-field"><Notice m={e.m} /></div>)}
        {fp.length > 0 && <Points items={fp} done={done} toggle={toggle} />}
      </div>
    },
  }
  const condField = cond ? fieldsOf(draft).find((f) => f.id === cond.fieldId) : undefined
  const setStates = (fn: (s: NonNullable<Field['states']>) => void) => {
    edit((c) => { const f = fieldsOf(c).find((x) => x.id === cond!.fieldId); if (f) { f.states = [...(f.states ?? [])]; fn(f.states) } })
    settle(cond!.fieldId)
  }

  // Jump to a field: open its page, scroll to it and flash it.
  const jump = (fid: string) => {
    const t = tabs.find((x) => walk(x.questions).some((f) => f.id === fid))
    if (t) setPage(t.id)
    setTimeout(() => {
      const el = document.querySelector<HTMLElement>(`[data-field="${fid}"], [data-section="${fid}"]`)
      if (!el) return
      el.scrollIntoView({ block: 'center', behavior: 'smooth' })
      el.classList.add('ring-2', 'ring-destructive')
      setTimeout(() => el.classList.remove('ring-2', 'ring-destructive'), 2500)
    }, 60)
  }

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
      if (e instanceof ApiError && e.errors.length) {
        const list = e.errors.map((x) => ({ m: validationMsg(x), fieldId: fieldAt(form, x.path) }))
        setErrors(list)
        const first = list.find((x) => x.fieldId)
        if (first) jump(first.fieldId!)
      }
      toastError(apiMsg(e))
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
      toastError(apiMsg(e))
    }
  }

  function download() {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' }))
    a.download = `${(draft as { title?: string }).title || 'formularz'}.json`.replace(/[\\/:*?"<>|]/g, '_')
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const review: Review = new Map(open.filter((p) => p.fieldId).map((p) => { const m = reviewMsg(p.why); return [p.fieldId!, `${m.title}. ${m.action}`] }))
  const title = (draft as { title?: string }).title ?? ''
  const fieldTitle = new Map(fieldsOf(draft).map((f) => [f.id, f.title || f.techName]))

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

      <div className="mx-auto w-full max-w-7xl flex-1 px-4 pt-4 sm:px-6">
        {errors.length > 0 && (
          <div role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm" data-testid="save-errors">
            <p className="font-medium text-destructive">Zmiany nie zostały zapisane. Popraw {plural(errors.length, 'to miejsce', 'te miejsca', 'tych miejsc')}:</p>
            <ul className="mt-2 space-y-2">{errors.slice(0, 12).map((e, i) => (
              <li key={i} className="flex flex-wrap items-start gap-3 rounded-md bg-card px-3 py-2">
                <Notice m={e.m} className="flex-1" />
                {e.fieldId && <Button size="xs" variant="outline" onClick={() => jump(e.fieldId!)}>Pokaż pole „{fieldTitle.get(e.fieldId)}”</Button>}
              </li>
            ))}</ul>
          </div>
        )}

        <div className="grid gap-6 pb-4 md:grid-cols-[15rem_minmax(0,1fr)]">
          <nav aria-label="Strony formularza" className="md:sticky md:top-32 md:self-start">
            <ul className="flex gap-1 overflow-x-auto md:flex-col">
              <PageLink active={cur === OVERVIEW} onClick={() => setPage(OVERVIEW)} label="Cały formularz" open={overviewOpen} />
              {tabs.map((t) => <PageLink key={t.id} active={cur === t.id} onClick={() => setPage(t.id)} label={t.title} open={openOn(t.questions)} />)}
            </ul>
          </nav>

          <div className="min-w-0">
            {cur === OVERVIEW ? (
              <Overview title={title} onTitle={(v) => edit((c) => { (c as { title?: string }).title = v })}
                general={general} done={done} toggle={toggle} proposals={proposals} draft={draft} onAccept={acceptProposal}
                env={env} dirty={dirty} onRegenerated={(e) => { load(e); onChanged(); toast.success('Formularz przebudowany') }} />
            ) : (
              <div className="-mx-4 sm:mx-0 sm:overflow-hidden sm:rounded-xl"><Preview form={draft} review={review} editing={editing} page={cur} onPage={setPage} /></div>
            )}
          </div>
        </div>
      </div>

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
            <Notice m={reviewMsg(p.why)}>{p.fails.map((f, j) => <span key={j} className="mt-0.5 block text-xs text-muted-foreground">{f}</span>)}</Notice>
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
      toastError(apiMsg(e))
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
