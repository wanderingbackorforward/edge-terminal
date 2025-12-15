import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Target, AlertTriangle, Activity, Settings } from 'lucide-react';
import { cn } from '../../lib/utils';

interface SidebarProps {
    className?: string;
}

const navItems = [
    { icon: LayoutDashboard, label: '监控大屏', path: '/' },
    { icon: AlertTriangle, label: '告警管理', path: '/warnings' },
    { icon: Target, label: '环数据', path: '/rings' },
    { icon: Activity, label: '数据分析', path: '/analytics' },
    { icon: Settings, label: '系统设置', path: '/settings' },
];

export const Sidebar: React.FC<SidebarProps> = ({ className }) => {
    return (
        <aside className={cn(
            "w-64 border-r border-border bg-surface h-[calc(100vh-4rem)] sticky top-16 hidden md:flex flex-col",
            className
        )}>
            <nav className="flex-1 p-4 space-y-1">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            cn(
                                "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                                isActive
                                    ? "bg-primary/10 text-primary border border-primary/20"
                                    : "text-text-secondary hover:bg-background hover:text-text-primary"
                            )
                        }
                    >
                        <item.icon className="w-5 h-5" />
                        {item.label}
                    </NavLink>
                ))}
            </nav>

            {/* 当前环号状态 */}
            <div className="p-4 border-t border-border">
                <div className="px-4 py-3 rounded-lg bg-background border border-border">
                    <div className="text-xs text-text-muted mb-1">当前环号</div>
                    <div className="text-2xl font-bold font-mono text-primary">#156</div>
                </div>
            </div>
        </aside>
    );
};
