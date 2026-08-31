import { useState, useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  BarChart3,
  LayoutDashboard,
  FileText,
  Users,
  Target,
  UserCircle,
  TrendingUp,
  Clock,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Moon,
  Sun,
  Settings as SettingsIcon,
  Languages,
  type LucideIcon,
} from "lucide-react";
import { setLanguage, type Language } from "../lib/i18n";

const nav = [
  { to: "/", labelKey: "nav.account", icon: LayoutDashboard, end: true },
  { to: "/contracts", labelKey: "nav.contracts", icon: FileText },
  { to: "/opportunities", labelKey: "nav.opportunities", icon: Target },
  { to: "/team", labelKey: "nav.team", icon: Users },
  { to: "/resources", labelKey: "nav.resources", icon: UserCircle },
  { to: "/cost-balancer", labelKey: "nav.costBalancer", icon: TrendingUp },
  { to: "/cost-space", labelKey: "nav.costSpace", icon: BarChart3 },
  { to: "/time-reports", labelKey: "nav.timeReports", icon: Clock },
];

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  collapsed,
}: {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  collapsed: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center ${collapsed ? "justify-center" : "gap-3"} rounded-lg px-3 py-2 text-sm font-medium transition ${
          isActive
            ? "bg-brand-400 text-white shadow"
            : "text-slate-600 hover:bg-brand-50 hover:text-brand-700 dark:text-slate-300 dark:hover:bg-slate-700"
        }`
      }
      title={collapsed ? label : undefined}
    >
      <Icon size={18} />
      {!collapsed && <span>{label}</span>}
    </NavLink>
  );
}

export default function Layout() {
  const { t, i18n } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    // Check localStorage - default to light theme if not set
    const saved = localStorage.getItem('darkMode');
    return saved === 'true'; // Explicitly true, otherwise false (light theme default)
  });

  useEffect(() => {
    // Apply dark mode class on mount and changes
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    // Save preference
    localStorage.setItem('darkMode', darkMode.toString());
  }, [darkMode]);

  // Cleanup on mount - ensure clean state
  useEffect(() => {
    const saved = localStorage.getItem('darkMode');
    if (!saved || saved === 'false') {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const toggleDarkMode = () => {
    setDarkMode(prev => !prev);
  };

  // Claude Chat ora è una pagina dedicata, non più alert

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={`flex ${
          collapsed ? "w-16" : "w-64"
        } flex-col border-r border-slate-200 bg-white transition-all dark:border-slate-700 dark:bg-slate-800`}
      >
        {/* Header with logo */}
        <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-700">
          {!collapsed && (
            <img src="/logo.svg" alt="Control Center" className="h-10 w-16" />
          )}
          {!collapsed && (
            <div className="flex-1">
              <div className="text-base font-bold text-slate-800 dark:text-white">
                Control Center
              </div>
              <div className="text-[10px] leading-tight text-slate-500 dark:text-slate-400">
                Security Account Management
              </div>
            </div>
          )}
          {collapsed && <img src="/favicon.svg" alt="CC" className="h-8 w-8" />}
        </div>

        {/* Navigation */}
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {nav.map((n) => (
            <NavItem
              key={n.to}
              to={n.to}
              label={t(n.labelKey)}
              icon={n.icon}
              end={n.end}
              collapsed={collapsed}
            />
          ))}

          {/* Settings */}
          <NavItem
            to="/settings"
            label={t("nav.settings")}
            icon={SettingsIcon}
            collapsed={collapsed}
          />

          {/* Claude AI Chat */}
          <NavLink
            to="/ai-chat"
            className={({ isActive }) =>
              `mt-4 flex items-center ${collapsed ? "justify-center" : "gap-3"} rounded-lg border-2 px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? "border-brand-500 bg-brand-500 text-white shadow"
                  : "border-brand-300 bg-brand-50 text-brand-700 hover:bg-brand-100 dark:border-brand-600 dark:bg-slate-700 dark:text-brand-400 dark:hover:bg-slate-600"
              }`
            }
            title={collapsed ? t("nav.aiChat") : undefined}
          >
            <MessageSquare size={18} />
            {!collapsed && <span>{t("nav.aiChat")}</span>}
          </NavLink>
        </nav>

        {/* Footer with version + controls */}
        <div className="border-t border-slate-100 p-3 dark:border-slate-700">
          <div className="flex items-center justify-between">
            {!collapsed && (
              <div className="text-xs text-slate-400 dark:text-slate-500">v1.0.8</div>
            )}

            <div className="flex gap-2">
              {/* Language toggle (IT <-> EN) */}
              <button
                onClick={() => setLanguage((i18n.language.startsWith("it") ? "en" : "it") as Language)}
                className="flex items-center gap-1 rounded p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
                title={i18n.language.startsWith("it") ? "English" : "Italiano"}
              >
                <Languages size={16} />
                <span className="text-[10px] font-semibold uppercase">
                  {i18n.language.startsWith("it") ? "it" : "en"}
                </span>
              </button>

              {/* Dark mode toggle */}
              <button
                onClick={toggleDarkMode}
                className="rounded p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
                title={darkMode ? t("common.lightTheme") : t("common.darkTheme")}
              >
                {darkMode ? <Sun size={16} /> : <Moon size={16} />}
              </button>

              {/* Collapse toggle */}
              <button
                onClick={() => setCollapsed(!collapsed)}
                className="rounded p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
                title={collapsed ? "Espandi menu" : "Comprimi menu"}
              >
                {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
              </button>
            </div>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-900">
        <Outlet />
      </main>
    </div>
  );
}
