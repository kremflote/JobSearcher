import { useRef, useState, type MouseEvent, type PointerEvent } from 'react'

export type SwipeDirection = 'left' | 'right'

/** Fraction of the row width a swipe must pass to count (FRONTEND §5.2). */
export const SWIPE_THRESHOLD = 0.3

/**
 * Horizontal swipe on a list row. Vertical movement is left to the browser (`touch-action: pan-y`)
 * and a click that ends a swipe is swallowed, so the row's link doesn't open.
 */
export function useSwipe(onSwipe: (dir: SwipeDirection) => void, enabled: boolean) {
  const [offset, setOffset] = useState(0)
  const [dragging, setDragging] = useState(false)
  const start = useRef<{ x: number; y: number; id: number; width: number } | null>(null)
  const locked = useRef(false)
  const swallowClick = useRef(false)

  const reset = () => {
    start.current = null
    locked.current = false
    setDragging(false)
    setOffset(0)
  }

  const handlers = enabled
    ? {
        onPointerDown: (e: PointerEvent<HTMLElement>) => {
          if (e.button !== 0) return
          start.current = { x: e.clientX, y: e.clientY, id: e.pointerId, width: e.currentTarget.offsetWidth }
          swallowClick.current = false
        },
        onPointerMove: (e: PointerEvent<HTMLElement>) => {
          const s = start.current
          if (!s || s.id !== e.pointerId) return
          const dx = e.clientX - s.x
          const dy = e.clientY - s.y
          if (!locked.current) {
            if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) return reset()
            if (Math.abs(dx) < 10) return
            locked.current = true
            swallowClick.current = true
            setDragging(true)
            e.currentTarget.setPointerCapture?.(e.pointerId)
          }
          setOffset(dx)
        },
        onPointerUp: (e: PointerEvent<HTMLElement>) => {
          const s = start.current
          if (!s || s.id !== e.pointerId) return
          const dx = e.clientX - s.x
          const passed = locked.current && Math.abs(dx) >= s.width * SWIPE_THRESHOLD
          reset()
          if (passed) onSwipe(dx > 0 ? 'right' : 'left')
        },
        onPointerCancel: reset,
        onClickCapture: (e: MouseEvent) => {
          if (!swallowClick.current) return
          swallowClick.current = false
          e.preventDefault()
          e.stopPropagation()
        },
      }
    : {}

  return { offset, dragging, handlers }
}
