/** Invented cover-letter text for the mock writer and reviser (FRONTEND §5.5). */
import type { JobDetail } from '@/api/types'

export const draftText = (job: JobDetail) => `Hei,

Jeg søker på stillingen som ${job.title.toLowerCase()} hos ${job.company}. Jeg er nyutdannet utvikler og har de siste årene bygget flere prosjekter med ${job.evaluation?.tech.slice(0, 2).join(' og ') || 'moderne verktøy'}.

I bachelorprosjektet ledet jeg arbeidet med backend og testoppsett, og jeg liker å jobbe tett med teamet for å levere noe som faktisk blir brukt. Det dere skriver om kodegjennomgang og hyppige leveranser passer godt med hvordan jeg liker å jobbe.

Jeg ser frem til å høre fra dere.

Med vennlig hilsen
Ola Nordmann`

export const DRAFT_CLAIMS = [
  '"ledet arbeidet med backend": stemmer det med CV-en?',
  '"kodegjennomgang og hyppige leveranser": står det i annonsen?',
]

/** The mock reviser: "kortere" drops a sentence from the longest paragraph, anything else adds one. */
export function reviseText(text: string, instruction: string): { content: string; summary: string } {
  const paras = text.split(/\n\s*\n/)
  let i = 0
  paras.forEach((p, k) => {
    if (p.length > paras[i]!.length) i = k
  })
  const sentences = paras[i]!.match(/[^.!?]+[.!?]+\s*/g) ?? [paras[i]!]
  if (/kort|stram|kutt/i.test(instruction) && sentences.length > 1) {
    paras[i] = sentences.slice(0, -1).join('').trim()
    return { content: paras.join('\n\n'), summary: `Kuttet siste setning i avsnitt ${i + 1}.` }
  }
  paras[i] = `${paras[i]!.trim()} (Mock-endring etter instruksjonen «${instruction.trim()}».)`
  return { content: paras.join('\n\n'), summary: `La til en setning i avsnitt ${i + 1}.` }
}

/** The mock reviser answers instead of revising when the message looks like a question. */
export const isQuestion = (text: string) =>
  text.trim().endsWith('?') || /^(hvorfor|hva|hvordan|hvem|hvilke|hvor|kommer|er|kan|bør|skal|stemmer)(?=\s|$)/i.test(text.trim())

export const MOCK_ANSWER =
  'Mock-svar: her forklarer agenten uten å endre brevet, for eksempel hvor en påstand kommer fra (profilen, annonsen eller ingen kilde). Ingen ny versjon.'
