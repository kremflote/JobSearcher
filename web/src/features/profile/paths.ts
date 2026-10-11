/** `/profil/<path>` with each segment encoded. */
export const fileUrl = (path: string) => `/profil/${path.split('/').map(encodeURIComponent).join('/')}`

/** File name from a title: lower case, Norwegian letters folded, words joined with `-`. */
export function slugify(name: string) {
  return name
    .trim()
    .toLowerCase()
    .replace(/æ/g, 'ae')
    .replace(/ø/g, 'o')
    .replace(/å/g, 'a')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/\.md$/, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}

export const isYaml = (path: string) => /\.ya?ml$/i.test(path)
