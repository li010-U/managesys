declare module 'nprogress' {
  export function start(): void
  export function done(): void
  export function configure(options: {
    showSpinner?: boolean
    speed?: number
    trickle?: boolean
    trickleSpeed?: number
    parent?: string
    template?: string
  }): void
  const nprogress: {
    start: () => void
    done: () => void
    configure: (options: {
      showSpinner?: boolean
      speed?: number
      trickle?: boolean
      trickleSpeed?: number
      parent?: string
      template?: string
    }) => void
  }
  export default nprogress
}
