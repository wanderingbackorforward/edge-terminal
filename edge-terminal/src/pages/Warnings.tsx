import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { warningApi } from '../services/api';
import { WarningStatus, WarningEvent } from '../types/api';
import {
    Table, TableHeader, TableBody, TableHead, TableRow, TableCell, Pagination
} from '../components/ui/Table';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Dialog } from '../components/ui/Dialog';
import { formatDate, cn } from '../lib/utils';
import { AlertTriangle, AlertCircle, Info, CheckCircle2, RotateCcw } from 'lucide-react';

const PAGE_SIZE = 15;

// 状态标签映射
const STATUS_LABELS: Record<string, string> = {
    active: '待处理',
    acknowledged: '已确认',
    resolved: '已解除',
    all: '全部'
};

// 告警等级映射
const LEVEL_LABELS: Record<string, string> = {
    Attention: '注意',
    Warning: '警告',
    Alarm: '报警'
};

const Warnings: React.FC = () => {
    const [currentPage, setCurrentPage] = useState(1);
    const [activeTab, setActiveTab] = useState<WarningStatus | 'all'>('active');
    const [selectedWarning, setSelectedWarning] = useState<WarningEvent | null>(null);
    const [actionType, setActionType] = useState<'acknowledge' | 'resolve' | null>(null);
    const [notes, setNotes] = useState('');

    const queryClient = useQueryClient();

    // 查询告警列表
    const { data, isLoading, refetch } = useQuery({
        queryKey: ['warnings', 'list', currentPage, activeTab],
        queryFn: () => warningApi.getWarnings({
            page: currentPage,
            page_size: PAGE_SIZE,
            status: activeTab === 'all' ? undefined : activeTab,
            sort_by: 'timestamp',
            sort_order: 'desc'
        }),
        refetchInterval: 10000,
    });

    // 确认告警
    const ackMutation = useMutation({
        mutationFn: ({ id, note }: { id: string; note: string }) =>
            warningApi.acknowledgeWarning(id, { acknowledged_by: '操作员', notes: note }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['warnings'] });
            closeDialog();
        }
    });

    // 解除告警
    const resolveMutation = useMutation({
        mutationFn: ({ id, note }: { id: string; note: string }) =>
            warningApi.resolveWarning(id, { resolved_by: '操作员', action_taken: note }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['warnings'] });
            closeDialog();
        }
    });

    const handleAction = () => {
        if (!selectedWarning) return;
        if (actionType === 'acknowledge') {
            ackMutation.mutate({ id: String(selectedWarning.warning_id), note: notes });
        } else if (actionType === 'resolve') {
            resolveMutation.mutate({ id: String(selectedWarning.warning_id), note: notes });
        }
    };

    const closeDialog = () => {
        setSelectedWarning(null);
        setActionType(null);
        setNotes('');
    };

    const openActionDialog = (warning: WarningEvent, type: 'acknowledge' | 'resolve') => {
        setSelectedWarning(warning);
        setActionType(type);
    };

    const getLevelBadge = (level: string) => {
        switch (level) {
            case 'Alarm': return 'destructive';
            case 'Warning': return 'warning';
            default: return 'default';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'active': return <AlertCircle className="w-4 h-4 text-error" />;
            case 'acknowledged': return <Info className="w-4 h-4 text-warning" />;
            case 'resolved': return <CheckCircle2 className="w-4 h-4 text-success" />;
            default: return null;
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                        告警管理
                    </h1>
                    <p className="text-text-secondary">
                        实时告警与异常信息管理
                    </p>
                </div>
                <div className="flex gap-2">
                    <div className="flex bg-surface rounded-lg p-1 border border-border">
                        {(['active', 'acknowledged', 'resolved', 'all'] as const).map((tab) => (
                            <button
                                key={tab}
                                onClick={() => { setActiveTab(tab); setCurrentPage(1); }}
                                className={cn(
                                    "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                                    activeTab === tab ? "bg-primary text-white" : "text-text-secondary hover:text-text-primary"
                                )}
                            >
                                {STATUS_LABELS[tab]}
                            </button>
                        ))}
                    </div>
                    <Button variant="outline" size="sm" onClick={() => refetch()}>
                        <RotateCcw className="w-4 h-4 mr-2" />
                        刷新
                    </Button>
                </div>
            </div>

            <Card>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>状态</TableHead>
                                <TableHead>等级</TableHead>
                                <TableHead>指标</TableHead>
                                <TableHead>描述</TableHead>
                                <TableHead>环号</TableHead>
                                <TableHead>时间</TableHead>
                                <TableHead className="text-right">操作</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                Array(5).fill(0).map((_, i) => (
                                    <TableRow key={i}><TableCell colSpan={7}><div className="h-8 bg-surface animate-pulse rounded" /></TableCell></TableRow>
                                ))
                            ) : (
                                data?.warnings.map((warning) => (
                                    <TableRow key={warning.warning_id}>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {getStatusIcon(warning.status)}
                                                {STATUS_LABELS[warning.status] || warning.status}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={getLevelBadge(warning.warning_level)}>
                                                {LEVEL_LABELS[warning.warning_level] || warning.warning_level}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="font-medium">{warning.indicator_type}</TableCell>
                                        <TableCell className="max-w-[300px] truncate text-text-secondary">
                                            {warning.threshold ? `数值超过阈值 ${warning.threshold}` : '检测到异常'}
                                        </TableCell>
                                        <TableCell>第{warning.ring_number}环</TableCell>
                                        <TableCell className="text-xs text-text-secondary">
                                            {formatDate(warning.timestamp)}
                                        </TableCell>
                                        <TableCell className="text-right space-x-2">
                                            {warning.status === 'active' && (
                                                <Button
                                                    size="sm"
                                                    variant="secondary"
                                                    onClick={() => openActionDialog(warning, 'acknowledge')}
                                                >
                                                    确认
                                                </Button>
                                            )}
                                            {warning.status !== 'resolved' && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="text-success hover:text-success hover:bg-success/10 border-success/20"
                                                    onClick={() => openActionDialog(warning, 'resolve')}
                                                >
                                                    解除
                                                </Button>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>

                    {data && (
                        <div className="p-4 border-t border-border">
                            <Pagination
                                currentPage={currentPage}
                                totalPages={Math.ceil(data.total / data.page_size)}
                                onPageChange={setCurrentPage}
                            />
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* 操作对话框 */}
            <Dialog
                isOpen={!!selectedWarning}
                onClose={closeDialog}
                title={actionType === 'acknowledge' ? '确认告警' : '解除告警'}
                description={`告警ID: ${selectedWarning?.warning_id} | 第${selectedWarning?.ring_number}环`}
            >
                <div className="space-y-4">
                    <div>
                        <label className="text-sm font-medium mb-1 block text-text-secondary">
                            {actionType === 'acknowledge' ? '备注 (可选)' : '处置措施 (必填)'}
                        </label>
                        <textarea
                            className="w-full h-24 rounded-md border border-border bg-background p-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-text-muted text-text-primary"
                            placeholder={actionType === 'acknowledge' ? "请输入备注..." : "请描述处置措施..."}
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                        />
                    </div>
                    <div className="flex justify-end gap-3">
                        <Button variant="ghost" onClick={closeDialog}>取消</Button>
                        <Button
                            onClick={handleAction}
                            disabled={actionType === 'resolve' && !notes.trim()}
                            isLoading={ackMutation.isPending || resolveMutation.isPending}
                        >
                            确定
                        </Button>
                    </div>
                </div>
            </Dialog>
        </div>
    );
};

export default Warnings;
