import React from 'react';
import { Card, CardContent } from '../ui/Card';
import { cn, formatNumber } from '../../lib/utils';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
    title: string;
    value: string | number;
    unit?: string;
    icon: LucideIcon;
    trend?: {
        value: number;
        label: string;
        direction: 'up' | 'down' | 'neutral';
    };
    status?: 'normal' | 'warning' | 'alarm';
    className?: string;
    onClick?: () => void;
}

export const StatCard: React.FC<StatCardProps> = ({
    title,
    value,
    unit,
    icon: Icon,
    trend,
    status = 'normal',
    className,
    onClick,
}) => {
    const statusColors = {
        normal: 'text-primary bg-primary/10',
        warning: 'text-warning bg-warning/10',
        alarm: 'text-error bg-error/10',
    };

    const trendColors = {
        up: 'text-success',
        down: 'text-error',
        neutral: 'text-text-secondary',
    };

    return (
        <Card
            className={cn(
                "hover:border-primary/50 transition-colors cursor-pointer group",
                className
            )}
            onClick={onClick}
        >
            <CardContent className="p-6">
                <div className="flex justify-between items-start mb-4">
                    <div className={cn("p-2 rounded-lg", statusColors[status])}>
                        <Icon className="w-5 h-5" />
                    </div>
                    {trend && (
                        <div className={cn("text-xs font-medium flex items-center gap-1", trendColors[trend.direction])}>
                            <span>{trend.value > 0 ? '+' : ''}{trend.value}%</span>
                            <span className="text-text-muted">{trend.label}</span>
                        </div>
                    )}
                </div>

                <div className="space-y-1">
                    <h3 className="text-sm font-medium text-text-secondary text-sm">{title}</h3>
                    <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-text-primary tracking-tight">
                            {typeof value === 'number' ? formatNumber(value) : value}
                        </span>
                        {unit && <span className="text-sm text-text-muted font-medium">{unit}</span>}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
