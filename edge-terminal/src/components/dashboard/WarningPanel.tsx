import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { AlertTriangle, AlertCircle, Info, ChevronRight, CheckCircle2 } from 'lucide-react';
import { cn, formatDate } from '../../lib/utils';
import { Button } from '../ui/Button';
import type { WarningEvent } from '../../types/api';

// 告警等级中文映射
const LEVEL_LABELS: Record<string, string> = {
    Attention: '注意',
    Warning: '警告',
    Alarm: '报警'
};

interface WarningPanelProps {
    warnings: WarningEvent[];
    isLoading?: boolean;
}

export const WarningPanel: React.FC<WarningPanelProps> = ({ warnings, isLoading }) => {
    if (isLoading) {
        return (
            <Card className="h-full flex items-center justify-center min-h-[300px]">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </Card>
        );
    }

    const getIcon = (level: string) => {
        switch (level) {
            case 'Alarm': return <AlertCircle className="w-5 h-5 text-error" />;
            case 'Warning': return <AlertTriangle className="w-5 h-5 text-warning" />;
            default: return <Info className="w-5 h-5 text-primary" />;
        }
    };

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-warning" />
                    实时告警
                </CardTitle>
                <Badge variant={warnings.length > 0 ? "destructive" : "secondary"}>
                    {warnings.length} 条待处理
                </Badge>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto pr-2">
                {warnings.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-text-muted space-y-2 min-h-[200px]">
                        <CheckCircle2 className="w-10 h-10 opacity-20" />
                        <p>系统运行正常</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {warnings.map((warning) => (
                            <div
                                key={warning.warning_id}
                                className="group flex items-start gap-3 p-3 rounded-lg bg-background border border-border hover:border-border/80 transition-colors"
                            >
                                <div className="mt-0.5">{getIcon(warning.warning_level)}</div>
                                <div className="flex-1 min-w-0 space-y-1">
                                    <div className="flex items-center justify-between">
                                        <p className="text-sm font-medium text-text-primary leading-none">
                                            {warning.indicator_type}
                                        </p>
                                        <span className="text-[10px] text-text-muted font-mono">
                                            {formatDate(warning.timestamp).split(',')[1]}
                                        </span>
                                    </div>
                                    <p className="text-xs text-text-secondary line-clamp-1">
                                        {warning.threshold
                                            ? `数值 ${warning.indicator_value} 超过阈值 ${warning.threshold}`
                                            : `第${warning.ring_number}环检测到异常`
                                        }
                                    </p>
                                </div>
                                <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <ChevronRight className="w-4 h-4" />
                                </Button>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};
