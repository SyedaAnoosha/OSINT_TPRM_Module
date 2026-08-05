import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  BookOpen, Gauge, LayoutGrid, Menu, Moon, Scale, ShieldCheck, Sun, SplitSquareHorizontal, X,
} from 'lucide-react'
import { cn } from '../lib/utils.js'
import { useTheme } from '../lib/theme.js'

// Grouped and numbered in wahidai.com's own module pattern — `01 ·`, `02 ·` — because this product
// IS that site's "04 · Third-Party Risk" module opened up, and it should read as the same system
// rather than as a separate application with its own visual identity.
//
// The grouping is also the workflow: look at the book, assess something, act on what came back,
// then answer for the programme.
const NAV = [
  { group: '01 · Portfolio', items: [
    { to: '/', label: 'The book', icon: LayoutGrid, end: true },
  ] },
  { group: '02 · Assess', items: [
    { to: '/assess', label: 'Score a vendor', icon: Gauge },
  ] },
  { group: '03 · Act', items: [
    { to: '/queue', label: 'Adjudication queue', icon: Scale },
    // { to: '/inventory', label: 'Inventory of record', icon: Boxes },
  ] },
  // { group: '04 · Programme', items: [
  //   { to: '/program', label: 'Maturity & KPIs', icon: TrendingUp },
  // ] },
  { group: null, items: [
    { to: '/use-cases', label: 'Use cases', icon: SplitSquareHorizontal },
    { to: '/methodology', label: 'Methodology', icon: BookOpen },
  ] },
]

export default function Layout() {
  const [open, setOpen] = useState(false)
  const { theme, toggle } = useTheme()

  return (
    <div className="min-h-screen bg-background">
      {/* mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-card/80 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-accent" />
          <span className="font-mono text-sm font-semibold">WahidAI</span>
        </div>
        <button className="rounded-md p-2 hover:bg-secondary" onClick={() => setOpen(true)} aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
      </header>

      {/* sidebar (fixed on desktop, slide-over on mobile) */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-sidebar text-sidebar-foreground',
          'transition-transform duration-300 md:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <Sidebar theme={theme} toggle={toggle} onNavigate={() => setOpen(false)} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={() => setOpen(false)} />
      )}

      {/* content */}
      <main className="md:pl-72">
        <div className="mx-auto max-w-7xl px-5 py-8 md:px-10 md:py-12">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function Sidebar({ theme, toggle, onNavigate }) {
  return (
    <div className="flex h-full flex-col p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-accent/15 ring-1 ring-accent/30">
            <ShieldCheck className="h-5 w-5 text-accent" />
          </div>
          <div className="leading-tight">
            <div className="font-mono text-sm font-bold tracking-tight">WahidAI</div>
          </div>
        </div>
        <button className="rounded-md p-2 text-sidebar-muted hover:bg-white/5 md:hidden" onClick={onNavigate} aria-label="Close menu">
          <X className="h-5 w-5" />
        </button>
      </div>

      <nav className="mt-8 flex flex-col gap-5 overflow-y-auto">
        {NAV.map(({ group, items }, gi) => (
          <div key={group || `g${gi}`} className={cn(!group && 'border-t border-sidebar-border pt-4')}>
            {group && (
              <div className="mb-1.5 px-3 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-sidebar-muted">
                {group}
              </div>
            )}
            <div className="flex flex-col gap-0.5">
              {items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition',
                      isActive
                        ? 'bg-[var(--sidebar-active-bg)] text-white'
                        : 'text-sidebar-foreground hover:bg-white/5',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon className={cn('h-[18px] w-[18px]', isActive ? 'text-accent' : 'text-sidebar-muted group-hover:text-accent')} />
                      {label}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-3 border-t border-sidebar-border pt-4">
        <button
          onClick={toggle}
          className="flex items-center justify-between rounded-lg px-3 py-2.5 text-sm text-sidebar-foreground hover:bg-white/5"
        >
          <span className="flex items-center gap-3">
            {theme === 'dark' ? <Moon className="h-[18px] w-[18px] text-accent" /> : <Sun className="h-[18px] w-[18px] text-accent" />}
            {theme === 'dark' ? 'Dark' : 'Light'} mode
          </span>
          <span className="text-[11px] text-sidebar-muted">toggle</span>
        </button>
      </div>
    </div>
  )
}
