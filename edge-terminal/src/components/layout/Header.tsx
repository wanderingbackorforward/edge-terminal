import React from 'react';
import { Shield, Bell, Settings } from 'lucide-react';
import { cn } from '../../lib/utils';

interface HeaderProps {
    className?: string;
}

export const Header: React.FC<HeaderProps> = ({ className }) => {
    return (
        <header className={cn(
            "h-16 border-b border-border bg-surface flex items-center justify-between px-6 sticky top-0 z-10",
            className
        )}>
            {/* Logo区域 */}
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Shield className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <h1 className="text-lg font-bold text-text-primary">盾构监控系统</h1>
                    <p className="text-xs text-text-muted">边缘计算终端</p>
                </div>
            </div>

            {/* 状态指示 */}
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-success/10 border border-success/20">
                    <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                    <span className="text-xs font-medium text-success">系统正常</span>
                </div>

                {/* 操作按钮 */}
                <div className="flex items-center gap-2">
                    <button className="p-2 rounded-lg hover:bg-background transition-colors text-text-secondary hover:text-text-primary">
                        <Bell className="w-5 h-5" />
                    </button>
                    <button className="p-2 rounded-lg hover:bg-background transition-colors text-text-secondary hover:text-text-primary">
                        <Settings className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </header>
    );
};
