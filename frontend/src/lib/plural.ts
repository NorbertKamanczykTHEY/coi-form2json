const rules = new Intl.PluralRules('pl-PL')

// Polish count + noun: plural(1, 'uwaga', 'uwagi', 'uwag') = "1 uwaga", 3 → "3 uwagi", 5/12/22.5 → "5 uwag" (fractions take the genitive too).
export function plural(n: number, one: string, few: string, many: string) {
  const form = rules.select(n)
  return `${n} ${form === 'one' ? one : form === 'few' ? few : many}`
}
