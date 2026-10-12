import { describe, expect, it } from 'vitest'
import { freePath, guessLanguage, sampleFile } from './WritingSampleDialog'

describe('writing sample', () => {
  it('guesses the language', () => {
    expect(guessLanguage('Jeg søker på stillingen og er motivert for å lære.')).toBe('no')
    expect(guessLanguage('I am applying for the position and I want to learn with the team.')).toBe('en')
    expect(guessLanguage('')).toBe('no')
  })

  it('writes the template frontmatter', () => {
    const file = sampleFile(
      { type: 'søknad', language: 'no', target: 'Utvikler, "Firma" AS', byMe: true, text: '  Hei!  ' },
      new Date(2026, 9, 12),
    )
    expect(file).toBe(
      '---\ntype: "søknad"\nlanguage: no\nwritten: "2026-10"\ntarget: "Utvikler, \\"Firma\\" AS"\noutcome: "ukjent"\nwritten_by_me: true\n---\n\nHei!\n',
    )
  })

  it('finds a free file name', () => {
    expect(freePath('firma-utvikler', new Set())).toBe('writing_samples/firma-utvikler.md')
    expect(freePath('firma-utvikler', new Set(['writing_samples/firma-utvikler.md']))).toBe('writing_samples/firma-utvikler-2.md')
    expect(freePath('', new Set())).toBe('writing_samples/skriveeksempel.md')
  })
})
