// How many files the import queue sends at once; the rest wait in order. VITE_BATCH_CONCURRENCY overrides it at build time.
export const IMPORT_CONCURRENCY = Math.max(1, Number(import.meta.env.VITE_BATCH_CONCURRENCY) || 2)
