import { useQuery } from "@tanstack/react-query";
import {
  Activity, BedDouble, Bell, Bot, Building2, ClipboardList, LayoutDashboard, LogOut, Menu, Moon, PanelLeftClose, PanelLeftOpen,
  Route, Search, Settings, ShieldCheck, Sun, Users, UserCog, ArrowRightLeft, LogOut as DischargeIcon, Boxes,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { notifications } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { useLiveNotifications } from "@/hooks/useLiveNotifications";
import { useTheme } from "@/hooks/useTheme";
import { cn, humanize } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, perm: "dashboard:read", end: true },
  { to: "/patients", label: "Patients", icon: Users, perm: "patients:read" },
  { to: "/beds", label: "Bed Management", icon: BedDouble, perm: "beds:read" },
  { to: "/resources", label: "Resource Management", icon: Boxes, perm: "resources:read" },
  { to: "/departments", label: "Departments", icon: Building2, perm: "departments:read" },
  { to: "/routing", label: "Patient Routing", icon: Route, perm: "routing:use" },
  { to: "/transfers", label: "Transfers", icon: ArrowRightLeft, perm: "transfers:read" },
  { to: "/discharges", label: "Discharges", icon: DischargeIcon, perm: "discharges:read" },
  { to: "/notifications", label: "Notifications", icon: Bell, perm: "notifications:read", badge: true },
  { to: "/ai", label: "AI Operations Assistant", icon: Bot, perm: "ai:use" },
  { to: "/audit", label: "Audit Logs", icon: ClipboardList, perm: "audit:read" },
  { to: "/users", label: "User Management", icon: UserCog, perm: "users:manage" },
  { to: "/settings", label: "Settings", icon: Settings, perm: "settings:read" },
];

export default function AppLayout() {
  const { user, logout, can } = useAuth();
  const { dark, toggle } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const loc = useLocation();
  const nav = useNavigate();
  const canNotify = can("notifications:read");

  useLiveNotifications(canNotify);
  const unread = useQuery({ queryKey: ["unread"], queryFn: notifications.unread, enabled: canNotify, refetchInterval: 20000 });
  const items = NAV.filter((n) => can(n.perm));
  const current = NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)))?.label ?? (loc.pathname.startsWith("/patients/") ? "Patient Details" : "Hospital Flow Agent");

  const sidebar = (
    <nav aria-label="Main navigation" className="flex h-full flex-col gap-1 p-2">
      <div className="flex h-12 items-center gap-2 px-2 font-semibold">
        <Activity className="h-5 w-5 shrink-0 text-primary" aria-hidden />
        {!collapsed && <span className="truncate">Hospital Flow Agent</span>}
      </div>
      {items.map(({ to, label, icon: Icon, end, badge }) => (
        <NavLink key={to} to={to} end={end} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined}
          className={({ isActive }) => cn("flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-accent", isActive && "bg-accent font-medium text-primary")}>
          <Icon className="h-4 w-4 shrink-0" aria-hidden />
          {!collapsed && <span className="flex-1 truncate">{label}</span>}
          {badge && !!unread.data?.unread && (
            <span className="rounded-full bg-destructive px-1.5 text-xs text-destructive-foreground" aria-label={`${unread.data.unread} unread`}>{unread.data.unread > 99 ? "99+" : unread.data.unread}</span>
          )}
        </NavLink>
      ))}
      <div className="mt-auto hidden md:block">
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={() => setCollapsed((c) => !c)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <><PanelLeftClose className="h-4 w-4" />Collapse</>}
        </Button>
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-card focus:p-2">Skip to content</a>
      <aside className={cn("sticky top-0 hidden h-screen shrink-0 border-r bg-card md:block", collapsed ? "w-16" : "w-64")}>{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 bg-card shadow-lg">{sidebar}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-card px-4">
          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="h-5 w-5" /></Button>
          <h2 className="hidden text-base font-semibold sm:block">{current}</h2>
          <form className="relative ml-auto w-full max-w-xs" role="search" onSubmit={(e) => { e.preventDefault(); if (search.trim()) nav(`/patients?q=${encodeURIComponent(search.trim())}`); }}>
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden />
            <Input className="pl-8" placeholder="Search patients by ID or name…" aria-label="Search patients" value={search} onChange={(e) => setSearch(e.target.value)} disabled={!can("patients:read")} />
          </form>
          <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle dark mode">{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</Button>
          {canNotify && (
            <Button variant="ghost" size="icon" asChild className="relative">
              <Link to="/notifications" aria-label={`Notifications${unread.data?.unread ? `, ${unread.data.unread} unread` : ""}`}>
                <Bell className="h-4 w-4" />
                {!!unread.data?.unread && <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-destructive px-1 text-[10px] leading-4 text-destructive-foreground">{unread.data.unread > 99 ? "99+" : unread.data.unread}</span>}
              </Link>
            </Button>
          )}
          <div className="hidden text-right text-xs leading-tight sm:block">
            <div className="font-medium">{user?.full_name}</div>
            <div className="flex items-center justify-end gap-1 text-muted-foreground"><ShieldCheck className="h-3 w-3" aria-hidden />{humanize(user?.role ?? "")}</div>
          </div>
          <Button variant="outline" size="icon" onClick={() => logout().then(() => nav("/login"))} aria-label="Sign out"><LogOut className="h-4 w-4" /></Button>
        </header>
        <main id="main" className="flex-1 p-4 md:p-6"><Outlet /></main>
      </div>
    </div>
  );
}
