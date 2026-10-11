/**
 * Minimal `.docx` writer for the mock `GET /api/drafts/{id}/docx`, so the downloaded file opens in
 * Word during user tests. Stored (uncompressed) zip with three parts; paragraphs, line breaks and
 * `**bold**`. The real export is python-docx in backend phase 3.
 */

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})

function crc32(bytes: Uint8Array) {
  let c = 0xffffffff
  for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff]! ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

/** Zip with stored entries (method 0), enough for Office to read. */
export function zip(files: Record<string, string>): Uint8Array {
  const enc = new TextEncoder()
  const local: number[] = []
  const central: number[] = []
  const u16 = (out: number[], v: number) => out.push(v & 0xff, (v >>> 8) & 0xff)
  const u32 = (out: number[], v: number) => out.push(v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff)
  let count = 0

  for (const [name, text] of Object.entries(files)) {
    const nameBytes = enc.encode(name)
    const data = enc.encode(text)
    const crc = crc32(data)
    const offset = local.length
    const header = (out: number[], sig: number) => {
      u32(out, sig)
      if (sig === 0x02014b50) u16(out, 20) // version made by
      u16(out, 20) // version needed
      u16(out, 0x0800) // UTF-8 names
      u16(out, 0) // stored
      u16(out, 0) // time
      u16(out, 0x21) // date: 1980-01-01
      u32(out, crc)
      u32(out, data.length)
      u32(out, data.length)
      u16(out, nameBytes.length)
      u16(out, 0) // extra
    }
    header(local, 0x04034b50)
    local.push(...nameBytes, ...data)
    header(central, 0x02014b50)
    u16(central, 0) // comment
    u16(central, 0) // disk
    u16(central, 0) // internal attrs
    u32(central, 0) // external attrs
    u32(central, offset)
    central.push(...nameBytes)
    count++
  }

  const end: number[] = []
  u32(end, 0x06054b50)
  u16(end, 0)
  u16(end, 0)
  u16(end, count)
  u16(end, count)
  u32(end, central.length)
  u32(end, local.length)
  u16(end, 0)
  return new Uint8Array([...local, ...central, ...end])
}

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function runs(line: string) {
  return line
    .split(/(\*\*[^*]+\*\*)/g)
    .filter(Boolean)
    .map((part) => {
      const bold = part.startsWith('**') && part.endsWith('**')
      const text = bold ? part.slice(2, -2) : part
      return `<w:r>${bold ? '<w:rPr><w:b/></w:rPr>' : ''}<w:t xml:space="preserve">${esc(text)}</w:t></w:r>`
    })
    .join('')
}

export function markdownToDocx(markdown: string): Uint8Array {
  const paragraphs = markdown
    .trim()
    .split(/\n\s*\n/)
    .map((block) => `<w:p>${block.split('\n').map(runs).join('<w:r><w:br/></w:r>')}</w:p>`)
    .join('')
  const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  return zip({
    '[Content_Types].xml':
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
    '_rels/.rels':
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
    'word/document.xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${W}"><w:body>${paragraphs}<w:sectPr/></w:body></w:document>`,
  })
}
