import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Braces, FileUp, KeyRound, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import Editor from '@/components/Editor'
import ImportDialog from '@/components/ImportDialog'
import JsonDialog from '@/components/JsonDialog'
import ProjectList from '@/components/ProjectList'
import TokenDialog from '@/components/TokenDialog'
import Preview from '@/Preview'
import { api, ApiError, token, type Form, type Info, type ListItem } from '@/lib/api'
import { fresh, useQueue } from '@/lib/queue'

// #/ = project list, #/projekt/<id> = editor; a pasted JSON preview is in memory only.
const route = () => decodeURIComponent(location.hash.match(/^#\/projekt\/(.+)$/)?.[1] ?? '')

export default function App() {
  const [info, setInfo] = useState<Info | null>(null)
  const [items, setItems] = useState<ListItem[] | null>(null)
  const [listError, setListError] = useState('')
  const [formId, setFormId] = useState(route)
  const [preview, setPreview] = useState<{ form: Form; name: string } | null>(null)
  const [dialog, setDialog] = useState<'' | 'import' | 'json' | 'token'>(token.get() ? '' : 'token')
  const [hasToken, setHasToken] = useState(!!token.get())
  const jobs = useQueue()
  const busy = jobs.filter((j) => j.status === 'running' || j.status === 'waiting').length
  const finished = jobs.filter((j) => j.status === 'done').length

  const refresh = useCallback(() => {
    if (!token.get()) return
    api.list().then((r) => { setItems(r); setListError('') }).catch((e) => {
      setListError(e instanceof ApiError && e.status === 401 ? (token.configured ? 'Token demo wygasł. Uruchom ponownie ./run-them-all.sh.' : 'Token jest nieważny albo wygasł. Wklej nowy token.') : `Nie udało się wczytać projektów: ${e.message}`)
    })
  }, [])

  useEffect(() => { api.info().then(setInfo).catch(() => setInfo(null)) }, [])
  useEffect(refresh, [refresh, hasToken, finished])
  useEffect(() => {
    const on = () => { setFormId(route()); setPreview(null) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const open = (id: string) => { location.hash = `/projekt/${encodeURIComponent(id)}`; setDialog('') }
  const home = () => { location.hash = '/'; setPreview(null) }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex min-h-svh flex-col">
        <header className="sticky top-0 z-30 h-14 border-b bg-card">
          <div className="mx-auto flex h-full max-w-7xl items-center gap-2 px-4 sm:px-6">
            <button type="button" onClick={home} className="mr-auto flex items-center gap-2.5 rounded-md text-left">
              <span className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground" aria-hidden>
                <svg viewBox="0 0 20 20" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M5 2.5h7l3 3v12H5z" /><path d="M8 9h4M8 12h4M8 15h2" /></svg>
              </span>
              <span className="leading-tight">
                <span className="block text-sm font-semibold">Formularze cyfrowe</span>
                <span className="hidden text-xs text-muted-foreground sm:block">z papieru do e-usługi</span>
              </span>
            </button>
            {!token.configured && (
              <Button variant="ghost" size="sm" onClick={() => setDialog('token')} aria-label="Token dostępu" className={hasToken ? '' : 'text-review'}>
                <KeyRound /><span className="hidden lg:inline">{hasToken ? 'Token' : 'Wklej token'}</span>
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setDialog('json')}><Braces /><span className="hidden sm:inline">Podgląd JSON</span></Button>
            <Button size="sm" onClick={() => setDialog('import')} data-testid="open-import">
              {busy ? <Loader2 className="animate-spin" /> : <FileUp />}
              <span>{busy ? `Import: ${busy} w toku` : 'Importuj pliki'}</span>
            </Button>
          </div>
        </header>

        <main className="flex flex-1 flex-col">
          {preview ? (
            <div>
              <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
                <Button variant="ghost" size="sm" onClick={home}><ArrowLeft />Projekty</Button>
                <p className="text-sm text-muted-foreground">Podgląd: <span className="font-medium text-foreground">{preview.name}</span>, bez zapisu</p>
                <Button variant="outline" size="sm" className="ml-auto" onClick={() => setDialog('json')}>Otwórz inny JSON</Button>
              </div>
              <Preview key={preview.name + JSON.stringify(preview.form).length} form={preview.form} />
            </div>
          ) : formId ? (
            <Editor key={formId} id={formId} onBack={home} onChanged={refresh} />
          ) : (
            <ProjectList items={hasToken ? items : null} fresh={fresh()} error={hasToken ? listError : 'Wklej token dostępu, żeby zobaczyć projekty.'} onOpen={open} onImport={() => setDialog('import')} onChanged={refresh} />
          )}
        </main>
      </div>

      <ImportDialog open={dialog === 'import'} onOpenChange={(v) => setDialog(v ? 'import' : '')} info={info} onOpenForm={open} />
      <JsonDialog open={dialog === 'json'} onOpenChange={(v) => setDialog(v ? 'json' : '')} onShow={(form, name) => setPreview({ form, name })} />
      <TokenDialog open={dialog === 'token'} onOpenChange={(v) => setDialog(v ? 'token' : '')} onSaved={() => setHasToken(!!token.get())} />
      <Toaster position="bottom-right" richColors />
    </TooltipProvider>
  )
}
