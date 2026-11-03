import { useEffect, useState } from 'react';

/** A phone or tablet: the primary pointer is a finger (a laptop with a touch screen keeps its mouse layout). */
export function isTouchDevice() {
  if (typeof window === 'undefined') return false;
  return !!window.matchMedia?.('(pointer: coarse)').matches;
}

/** Touch layout on: from the start on touch devices, or from the first touch (a laptop's touch screen). */
export function useTouch() {
  const [touch, setTouch] = useState(isTouchDevice);
  useEffect(() => {
    if (touch) return;
    const on = () => setTouch(true);
    window.addEventListener('touchstart', on, { once: true, passive: true });
    return () => window.removeEventListener('touchstart', on);
  }, [touch]);
  return touch;
}
