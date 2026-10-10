import { useCallback, useSyncExternalStore } from 'react'

/** Tracks a CSS media query. Breakpoints from FRONTEND §4.1. */
export function useMediaQuery(query: string) {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query)
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    },
    [query],
  )
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches)
}

/** ≥ 768 px: sidebar instead of bottom tabs. */
export const useIsTabletUp = () => useMediaQuery('(min-width: 768px)')
/** ≥ 1024 px: master-detail on Jobber. */
export const useIsWide = () => useMediaQuery('(min-width: 1024px)')
