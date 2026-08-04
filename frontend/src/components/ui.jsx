import { cn } from '../lib/utils.js'

// Small shadcn-style primitives (Tailwind + tokens), hand-built to avoid the CLI/Radix tree.

export function Button({ className, variant = 'default', size = 'default', ...props }) {
  const variants = {
    default: 'bg-primary text-primary-foreground hover:opacity-95 hover:shadow-md shadow-sm active:scale-[0.98]',
    accent: 'bg-accent text-accent-foreground hover:opacity-95 hover:shadow-md shadow-sm active:scale-[0.98]',
    outline: 'border border-border bg-card/60 backdrop-blur-sm hover:bg-secondary hover:border-accent/40 shadow-xs active:scale-[0.98]',
    ghost: 'hover:bg-secondary/80 text-muted-foreground hover:text-foreground active:scale-[0.98]',
  }
  const sizes = {
    default: 'h-11 px-5 text-sm',
    sm: 'h-9 px-3.5 text-xs',
    icon: 'h-10 w-10',
  }
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-150 cursor-pointer',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
        'disabled:pointer-events-none disabled:opacity-50',
        variants[variant], sizes[size], className,
      )}
      {...props}
    />
  )
}

export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-border/80 bg-card text-card-foreground shadow-sm transition-all duration-200 hover:border-border',
        className
      )}
      {...props}
    />
  )
}

export function Badge({ className, style, children }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide border border-border/40 bg-secondary/60 text-secondary-foreground shadow-2xs',
        className
      )}
      style={style}
    >
      {children}
    </span>
  )
}

/** A thin progress bar. `value` is 0..100. */
export function Progress({ value = 0, className, barClassName }) {
  return (
    <div className={cn('h-2 w-full overflow-hidden rounded-full bg-secondary/80 p-0.5 shadow-inner', className)}>
      <div
        className={cn('h-full rounded-full bg-accent transition-all duration-500 ease-out shadow-xs', barClassName)}
        style={{ width: `${Math.max(2, Math.min(100, value))}%` }}
      />
    </div>
  )
}

export function Meter({ value = 0, color }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/80 p-0.5 shadow-inner">
      <div className="h-full rounded-full transition-all duration-500 ease-out shadow-2xs"
        style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
    </div>
  )
}
